from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import calc_chore_pay
from ..utils import get_family_children, verify_child_ownership
from datetime import date
import calendar

bp = Blueprint('chores', __name__, url_prefix='/chores')

def get_target_user_id(db):
    if current_user.is_parent:
        child_id = request.args.get('child_id', type=int) or request.form.get('child_id', type=int)
        if child_id and not verify_child_ownership(db, child_id):
            return None
        return child_id
    return current_user.id

def build_record_map(db, target_id, month_str):
    """日付→家事ID(str)→{checked, count} のマップを返す。キーはすべてstr。"""
    rows = db.execute('''
        SELECT cr.record_date, cr.chore_type_id,
               COUNT(*) OVER (PARTITION BY cr.record_date, cr.chore_type_id) AS checker_count,
               MAX(CASE WHEN cr.user_id = ? THEN 1 ELSE 0 END)
                   OVER (PARTITION BY cr.record_date, cr.chore_type_id) AS my_check
        FROM chore_records cr
        WHERE strftime('%Y-%m', cr.record_date) = ?
        GROUP BY cr.record_date, cr.chore_type_id, cr.user_id
    ''', (target_id, month_str)).fetchall()

    record_map = {}
    for r in rows:
        d = str(r['record_date'])[:10]   # datetime.date → 'YYYY-MM-DD' 文字列に統一
        cid = str(r['chore_type_id'])
        if d not in record_map:
            record_map[d] = {}
        record_map[d][cid] = {
            'checked': bool(r['my_check']),
            'count': int(r['checker_count']),
        }
    return record_map

def build_chore_summary(db, target_id, month_str, chore_types):
    """家事種類ID(str)→件数 のマップ。"""
    summary = {}
    for ct in chore_types:
        row = db.execute('''
            SELECT COUNT(*) AS cnt FROM chore_records
            WHERE user_id=? AND chore_type_id=?
              AND strftime('%Y-%m', record_date)=?
        ''', (target_id, ct['id'], month_str)).fetchone()
        summary[str(ct['id'])] = int(row['cnt'])
    return summary

@bp.route('/')
@login_required
def index():
    db = get_db()
    today = date.today()
    year  = request.args.get('year',  today.year,  type=int)
    month = request.args.get('month', today.month, type=int)

    target_id = get_target_user_id(db)
    if target_id is None and current_user.is_parent:
        children = get_family_children(db)
        if children:
            target_id = children[0]['id']

    if target_id is None:
        flash('ユーザーが見つかりません。', 'danger')
        return redirect(url_for('home.index'))

    target_user  = db.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone()
    chore_types  = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    month_str    = f'{year}-{month:02d}'
    record_map   = build_record_map(db, target_id, month_str)
    chore_summary = build_chore_summary(db, target_id, month_str, chore_types)
    chore_pay    = calc_chore_pay(target_id, year, month)
    cal          = calendar.monthcalendar(year, month)

    children = None
    if current_user.is_parent:
        children = get_family_children(db)

    prev_year,  prev_month  = (year, month - 1) if month > 1  else (year - 1, 12)
    next_year,  next_month  = (year, month + 1) if month < 12 else (year + 1,  1)

    return render_template('chores/index.html',
                           target_user=target_user,
                           target_id=target_id,
                           chore_types=chore_types,
                           calendar=cal,
                           year=year, month=month,
                           today=today,
                           record_map=record_map,
                           chore_pay=chore_pay,
                           chore_summary=chore_summary,
                           children=children,
                           prev_year=prev_year,   prev_month=prev_month,
                           next_year=next_year,   next_month=next_month)

@bp.route('/toggle', methods=['POST'])
@login_required
def toggle():
    db = get_db()
    today = date.today()
    data = request.get_json()
    record_date_str = data.get('date')
    chore_type_id   = data.get('chore_type_id')
    target_id       = data.get('user_id', current_user.id)

    try:
        record_date = date.fromisoformat(record_date_str)
    except Exception:
        return jsonify({'error': '日付が不正です'}), 400

    if current_user.is_child:
        if int(target_id) != current_user.id:
            return jsonify({'error': '権限がありません'}), 403
        if record_date != today:
            return jsonify({'error': '当日分のみ入力できます'}), 403

    if current_user.is_parent:
        prev_year  = today.year if today.month > 1 else today.year - 1
        prev_month = today.month - 1 if today.month > 1 else 12
        is_current = (record_date.year == today.year  and record_date.month == today.month)
        is_prev    = (record_date.year == prev_year   and record_date.month == prev_month)
        if not is_current and not is_prev:
            return jsonify({'error': '当月または前月分のみ編集できます'}), 403

    existing = db.execute('''
        SELECT id FROM chore_records
        WHERE user_id=? AND chore_type_id=? AND record_date=?
    ''', (target_id, chore_type_id, record_date_str)).fetchone()

    if existing:
        db.execute('DELETE FROM chore_records WHERE id=?', (existing['id'],))
        checked = False
    else:
        db.execute('''
            INSERT INTO chore_records (user_id, chore_type_id, record_date, checked_by)
            VALUES (?, ?, ?, ?)
        ''', (target_id, chore_type_id, record_date_str, current_user.id))
        checked = True

    db.commit()

    count = db.execute('''
        SELECT COUNT(*) as cnt FROM chore_records
        WHERE chore_type_id=? AND record_date=?
    ''', (chore_type_id, record_date_str)).fetchone()['cnt']

    # サマリー再計算（月全体）
    month_str = record_date_str[:7]
    chore_types = db.execute('SELECT id FROM chore_types WHERE is_active=1').fetchall()
    summary = {}
    for ct in chore_types:
        row = db.execute('''
            SELECT COUNT(*) AS cnt FROM chore_records
            WHERE user_id=? AND chore_type_id=?
              AND strftime('%Y-%m', record_date)=?
        ''', (target_id, ct['id'], month_str)).fetchone()
        summary[str(ct['id'])] = int(row['cnt'])

    # 獲得金額も再計算
    year_int, month_int = int(month_str[:4]), int(month_str[5:7])
    new_chore_pay = calc_chore_pay(int(target_id), year_int, month_int)

    return jsonify({
        'checked': checked,
        'count': int(count),
        'summary': summary,
        'chore_pay': new_chore_pay,
    })

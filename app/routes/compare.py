from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import calc_chore_pay, calc_monthly_salary
from datetime import date
import calendar

bp = Blueprint('compare', __name__, url_prefix='/compare')

def month_summary(db, user_id, year, month):
    """1人1ヶ月の家事集計を返す。"""
    month_str = f'{year}-{month:02d}'
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    summary = {}
    total_count = 0
    for ct in chore_types:
        row = db.execute('''
            SELECT COUNT(*) AS cnt FROM chore_records
            WHERE user_id=? AND chore_type_id=?
              AND strftime('%Y-%m', record_date)=?
        ''', (user_id, ct['id'], month_str)).fetchone()
        cnt = int(row['cnt'])
        summary[str(ct['id'])] = cnt
        total_count += cnt
    pay = calc_chore_pay(user_id, year, month)
    return {'summary': summary, 'total_count': total_count, 'pay': pay}

# -------------------------------------------------------
# 親専用：3人まとめて比較
# -------------------------------------------------------
@bp.route('/all')
@login_required
def all_children():
    if not current_user.is_parent:
        flash('この画面は親のみ閲覧できます。', 'danger')
        return redirect(url_for('home.index'))

    db = get_db()
    today = date.today()
    year  = request.args.get('year',  today.year,  type=int)
    month = request.args.get('month', today.month, type=int)

    children   = db.execute("SELECT * FROM users WHERE role='child' ORDER BY grade DESC").fetchall()
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()

    data = []
    for child in children:
        ms = month_summary(db, child['id'], year, month)
        salary = calc_monthly_salary(child['id'], year, month)
        data.append({
            'user': child,
            'summary': ms['summary'],
            'total_count': ms['total_count'],
            'chore_pay': ms['pay'],
            'salary': salary,
        })

    prev_year,  prev_month  = (year, month - 1) if month > 1  else (year - 1, 12)
    next_year,  next_month  = (year, month + 1) if month < 12 else (year + 1,  1)

    return render_template('compare/all_children.html',
                           children_data=data,
                           chore_types=chore_types,
                           year=year, month=month,
                           today=today,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month)

# -------------------------------------------------------
# 子供：自分の今月 vs 先月
# -------------------------------------------------------
@bp.route('/monthly')
@login_required
def monthly():
    db = get_db()
    today = date.today()
    year  = request.args.get('year',  today.year,  type=int)
    month = request.args.get('month', today.month, type=int)

    # 親が child_id 指定で閲覧可能
    if current_user.is_parent:
        target_id = request.args.get('child_id', type=int)
        if not target_id:
            children = db.execute("SELECT * FROM users WHERE role='child' ORDER BY grade DESC").fetchall()
            target_id = children[0]['id'] if children else None
    else:
        target_id = current_user.id

    if not target_id:
        return redirect(url_for('home.index'))

    target_user = db.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone()
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()

    # 今月・先月
    if month == 1:
        prev_year2, prev_month2 = year - 1, 12
    else:
        prev_year2, prev_month2 = year, month - 1

    this_data = month_summary(db, target_id, year, month)
    prev_data  = month_summary(db, target_id, prev_year2, prev_month2)

    this_salary = calc_monthly_salary(target_id, year, month)
    prev_salary = calc_monthly_salary(target_id, prev_year2, prev_month2)

    # ナビ用（表示月を1ヶ月ずつ移動）
    if month == 1:
        nav_prev_year, nav_prev_month = year - 1, 12
    else:
        nav_prev_year, nav_prev_month = year, month - 1
    if month == 12:
        nav_next_year, nav_next_month = year + 1, 1
    else:
        nav_next_year, nav_next_month = year, month + 1

    children = None
    if current_user.is_parent:
        children = db.execute("SELECT * FROM users WHERE role='child' ORDER BY grade DESC").fetchall()

    return render_template('compare/monthly.html',
                           target_user=target_user,
                           target_id=target_id,
                           chore_types=chore_types,
                           year=year, month=month,
                           prev_year=prev_year2, prev_month=prev_month2,
                           this_data=this_data,
                           prev_data=prev_data,
                           this_salary=this_salary,
                           prev_salary=prev_salary,
                           today=today,
                           nav_prev_year=nav_prev_year, nav_prev_month=nav_prev_month,
                           nav_next_year=nav_next_year, nav_next_month=nav_next_month,
                           children=children)

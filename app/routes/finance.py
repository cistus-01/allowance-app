from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import calc_balance, get_monthly_finance_summary
from ..utils import get_family_children, verify_child_ownership
from datetime import date
import calendar

bp = Blueprint('finance', __name__, url_prefix='/finance')

def get_target_user_id(db):
    if current_user.is_parent:
        child_id = request.args.get('child_id', type=int) or request.form.get('child_id', type=int)
        if child_id and not verify_child_ownership(db, child_id):
            return None
        return child_id
    return current_user.id

@bp.route('/')
@login_required
def index():
    db = get_db()
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    target_id = get_target_user_id(db)
    if target_id is None and current_user.is_parent:
        children = get_family_children(db)
        if children:
            target_id = children[0]['id']

    target_user = db.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone()

    month_str = f'{year}-{month:02d}'

    # 日付ごとの収支サマリー
    day_records = db.execute('''
        SELECT record_date,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income_total,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense_total
        FROM finance_records
        WHERE user_id=? AND strftime('%Y-%m', record_date)=?
        GROUP BY record_date
    ''', (target_id, month_str)).fetchall()

    day_map = {str(r['record_date'])[:10]: r for r in day_records}

    # カレンダー
    cal = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)

    # 月次サマリー
    summary = get_monthly_finance_summary(target_id, year, month)
    balance = calc_balance(target_id)

    children = None
    if current_user.is_parent:
        children = get_family_children(db)

    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    return render_template('finance/index.html',
                           target_user=target_user,
                           target_id=target_id,
                           calendar=cal,
                           year=year, month=month,
                           today=today,
                           day_map=day_map,
                           summary=summary,
                           balance=balance,
                           children=children,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month)

@bp.route('/day')
@login_required
def day_detail():
    db = get_db()
    record_date = request.args.get('date')
    target_id = get_target_user_id(db)
    if target_id is None:
        target_id = current_user.id

    records = db.execute('''
        SELECT * FROM finance_records
        WHERE user_id=? AND record_date=?
        ORDER BY created_at
    ''', (target_id, record_date)).fetchall()

    income_records = [r for r in records if r['type'] == 'income']
    expense_records = [r for r in records if r['type'] == 'expense']

    return render_template('finance/day_detail.html',
                           target_id=target_id,
                           record_date=record_date,
                           income_records=income_records,
                           expense_records=expense_records)

@bp.route('/add', methods=['POST'])
@login_required
def add():
    db = get_db()
    raw_id = request.form.get('user_id', type=int)
    if raw_id and current_user.is_parent and not verify_child_ownership(db, raw_id):
        flash('権限がありません。', 'danger')
        return redirect(url_for('finance.index'))
    target_id = raw_id or current_user.id
    record_date = request.form.get('record_date')
    rec_type = request.form.get('type')
    category = request.form.get('category', '').strip()
    shop = request.form.get('shop', '').strip() or None
    item = request.form.get('item', '').strip() or None
    amount = request.form.get('amount', type=int)

    if not category or not amount or not record_date:
        flash('入力内容を確認してください。', 'danger')
        return redirect(request.referrer or url_for('finance.index'))

    db.execute('''
        INSERT INTO finance_records (user_id, record_date, type, category, shop, item, amount, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (target_id, record_date, rec_type, category, shop, item, amount, current_user.id))
    db.commit()
    flash('記録しました。', 'success')
    return redirect(url_for('finance.day_detail', date=record_date,
                            child_id=target_id if current_user.is_parent else None))

@bp.route('/delete/<int:record_id>', methods=['POST'])
@login_required
def delete(record_id):
    db = get_db()
    record = db.execute('SELECT * FROM finance_records WHERE id=?', (record_id,)).fetchone()
    if record:
        if current_user.is_parent and not verify_child_ownership(db, record['user_id']):
            flash('権限がありません。', 'danger')
            return redirect(url_for('finance.index'))
        if current_user.is_child and record['user_id'] != current_user.id:
            flash('権限がありません。', 'danger')
            return redirect(url_for('finance.index'))
        record_date = record['record_date']
        target_id = record['user_id']
        db.execute('DELETE FROM finance_records WHERE id=?', (record_id,))
        db.commit()
        flash('削除しました。', 'success')
        return redirect(url_for('finance.day_detail', date=record_date,
                                child_id=target_id if current_user.is_parent else None))
    return redirect(url_for('finance.index'))

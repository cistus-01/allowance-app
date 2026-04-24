from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import current_user
from ..database import get_db
from ..salary import calc_monthly_salary, calc_balance
from ..utils import get_family_children, verify_child_ownership, get_family
from datetime import date, datetime

bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('home/lp.html')

    # Subscription check for parents
    if current_user.role == 'parent':
        db_for_check = get_db()
        family = get_family(db_for_check)
        if family:
            status = family['subscription_status']
            if status == 'trial':
                trial_end = family['trial_ends_at']
                if trial_end and datetime.fromisoformat(trial_end) <= datetime.utcnow():
                    flash('トライアル期間が終了しました。プランにご登録ください。', 'warning')
                    return redirect(url_for('billing.index'))
            elif status not in ('active', 'trial'):
                flash('トライアル期間が終了しました。プランにご登録ください。', 'warning')
                return redirect(url_for('billing.index'))
    # 初回ログイン時はチュートリアルへ
    if not current_user.tutorial_done:
        return redirect(url_for('help.tutorial'))

    db = get_db()
    today = date.today()
    next_month = today.month + 1 if today.month < 12 else 1
    next_year  = today.year if today.month < 12 else today.year + 1

    if current_user.is_parent:
        children = get_family_children(db)
        selected_id = request.args.get('child_id', type=int)
        if selected_id is None and children:
            selected_id = children[0]['id']
        selected_child = None
        salary = None
        balance = None
        if selected_id:
            row = verify_child_ownership(db, selected_id)
            if row:
                from ..models import User
                selected_child = User(row)
                salary = calc_monthly_salary(selected_id, next_year, next_month)
                balance = calc_balance(selected_id)

        # 今日の全子供の家事チェック数（ホーム一覧用）
        today_str = today.isoformat()
        chore_counts_today = {}
        for child in (children or []):
            cnt = db.execute(
                'SELECT COUNT(*) as cnt FROM chore_records WHERE user_id=? AND record_date=?',
                (child['id'], today_str)
            ).fetchone()['cnt']
            chore_counts_today[child['id']] = cnt

        return render_template('home/index_parent.html',
                               children=children,
                               selected_child=selected_child,
                               selected_id=selected_id,
                               salary=salary,
                               balance=balance,
                               today=today,
                               next_month=next_month,
                               chore_counts_today=chore_counts_today)
    else:
        salary = calc_monthly_salary(current_user.id, next_year, next_month)
        balance = calc_balance(current_user.id)
        top_goal = db.execute(
            'SELECT * FROM goals WHERE user_id=? AND is_achieved=0 ORDER BY created_at ASC LIMIT 1',
            (current_user.id,)
        ).fetchone()

        # 全家事の日割り最大報酬（days_to_goal 計算用）
        chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()

        # 目標達成まであと何日？（全家事毎日やった場合の最短日数）
        days_to_goal = None
        if top_goal:
            remaining = top_goal['target_amount'] - balance
            if remaining > 0:
                daily_max = sum(ct['unit_price'] for ct in chore_types) if chore_types else 0
                # 月次固定給（base_pay + grade_pay）を日割り
                import calendar as cal_mod
                days_in_month = cal_mod.monthrange(today.year, today.month)[1]
                daily_fixed = (salary['base_pay'] + salary.get('grade_pay', 0) + salary.get('academic_pay', 0)) / days_in_month
                daily_total = daily_max + daily_fixed
                if daily_total > 0:
                    import math
                    days_to_goal = math.ceil(remaining / daily_total)

        return render_template('home/index_child.html',
                               salary=salary,
                               balance=balance,
                               today=today,
                               next_month=next_month,
                               top_goal=top_goal,
                               days_to_goal=days_to_goal)

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
    db = get_db()
    today = date.today()

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
                salary = calc_monthly_salary(selected_id, today.year, today.month)
                balance = calc_balance(selected_id)
        return render_template('home/index_parent.html',
                               children=children,
                               selected_child=selected_child,
                               selected_id=selected_id,
                               salary=salary,
                               balance=balance,
                               today=today)
    else:
        salary = calc_monthly_salary(current_user.id, today.year, today.month)
        balance = calc_balance(current_user.id)
        top_goal = db.execute(
            'SELECT * FROM goals WHERE user_id=? AND is_achieved=0 ORDER BY created_at ASC LIMIT 1',
            (current_user.id,)
        ).fetchone()
        return render_template('home/index_child.html',
                               salary=salary,
                               balance=balance,
                               today=today,
                               top_goal=top_goal)

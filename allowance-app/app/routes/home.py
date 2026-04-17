from flask import Blueprint, render_template, redirect, url_for, request, session
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import calc_monthly_salary, calc_balance
from datetime import date

bp = Blueprint('home', __name__)

@bp.route('/')
@login_required
def index():
    db = get_db()
    today = date.today()

    if current_user.is_parent:
        # 親：表示する子供を選択できる
        children = db.execute(
            "SELECT * FROM users WHERE role='child' ORDER BY grade DESC"
        ).fetchall()
        selected_id = request.args.get('child_id', type=int)
        if selected_id is None and children:
            selected_id = children[0]['id']
        selected_child = None
        salary = None
        balance = None
        if selected_id:
            row = db.execute('SELECT * FROM users WHERE id=?', (selected_id,)).fetchone()
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
        return render_template('home/index_child.html',
                               salary=salary,
                               balance=balance,
                               today=today)

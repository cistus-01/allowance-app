from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user
from ..database import get_db
from ..salary import calc_monthly_salary, calc_balance
from ..utils import get_family_children, verify_child_ownership
from datetime import date

bp = Blueprint("home", __name__)


@bp.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("home/lp.html")

    # 初回ログイン時はチュートリアルへ
    if not current_user.tutorial_done:
        return redirect(url_for("help.tutorial"))

    db = get_db()
    today = date.today()
    next_month = today.month + 1 if today.month < 12 else 1
    next_year = today.year if today.month < 12 else today.year + 1

    if current_user.is_parent:
        children = get_family_children(db)
        selected_id = request.args.get("child_id", type=int)
        if selected_id is None and children:
            selected_id = children[0]["id"]
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
        for child in children or []:
            cnt = db.execute(
                "SELECT COUNT(*) as cnt FROM chore_records WHERE user_id=? AND record_date=?",
                (child["id"], today_str),
            ).fetchone()["cnt"]
            chore_counts_today[child["id"]] = cnt

        return render_template(
            "home/index_parent.html",
            children=children,
            selected_child=selected_child,
            selected_id=selected_id,
            salary=salary,
            balance=balance,
            today=today,
            next_month=next_month,
            chore_counts_today=chore_counts_today,
        )
    else:
        salary = calc_monthly_salary(current_user.id, next_year, next_month)
        balance = calc_balance(current_user.id)

        open_challenges = db.execute(
            "SELECT * FROM challenges WHERE user_id=? AND status='open' ORDER BY created_at ASC",
            (current_user.id,),
        ).fetchall()

        return render_template(
            "home/index_child.html",
            salary=salary,
            balance=balance,
            today=today,
            next_month=next_month,
            open_challenges=open_challenges,
        )

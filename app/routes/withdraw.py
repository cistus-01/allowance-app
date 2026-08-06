from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user, logout_user
from ..database import get_db
from ..utils import get_family

bp = Blueprint("withdraw", __name__, url_prefix="/withdraw")


def _delete_family_data(db, family_id):
    """ファミリーに属する全データを削除する"""
    child_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM users WHERE family_id=? AND role='child'", (family_id,)
        ).fetchall()
    ]
    all_user_ids = child_ids + [
        r["id"]
        for r in db.execute(
            "SELECT id FROM users WHERE family_id=? AND role='parent'", (family_id,)
        ).fetchall()
    ]

    if all_user_ids:
        ph = ",".join("?" * len(all_user_ids))
        db.execute(f"DELETE FROM chore_records WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM grade_records WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM finance_records WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM salary_payments WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM goals WHERE user_id IN ({ph})", all_user_ids)
        db.execute(
            f"DELETE FROM password_reset_tokens WHERE user_id IN ({ph})", all_user_ids
        )

    db.execute("DELETE FROM challenges WHERE family_id=?", (family_id,))
    db.execute("DELETE FROM grade_input_periods WHERE family_id=?", (family_id,))
    db.execute("DELETE FROM config_presets WHERE family_id=?", (family_id,))
    db.execute("DELETE FROM users WHERE family_id=?", (family_id,))
    db.execute("DELETE FROM families WHERE id=?", (family_id,))
    db.commit()


@bp.route("/")
@login_required
def index():
    if not current_user.is_parent:
        return redirect(url_for("home.index"))
    db = get_db()
    family = get_family(db)
    return render_template("withdraw/index.html", family=family)


@bp.route("/confirm", methods=["POST"])
@login_required
def confirm():
    if not current_user.is_parent:
        return redirect(url_for("home.index"))
    if request.form.get("confirm_text") != "退会する":
        flash("「退会する」と入力してください。", "danger")
        return redirect(url_for("withdraw.index"))

    db = get_db()
    family = get_family(db)
    if not family:
        flash("ファミリー情報が見つかりません。", "danger")
        return redirect(url_for("home.index"))

    family_id = family["id"]
    logout_user()
    _delete_family_data(db, family_id)
    flash("退会が完了しました。ご利用ありがとうございました。", "success")
    return redirect(url_for("home.index"))

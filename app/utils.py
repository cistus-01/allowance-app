from flask_login import current_user
from .database import get_db


def get_family(db):
    if not current_user.family_id:
        return None
    return db.execute(
        "SELECT * FROM families WHERE id = ?", (current_user.family_id,)
    ).fetchone()


def get_family_children(db):
    """現在のファミリーに属する子どものみ返す"""
    if not current_user.family_id:
        return []
    return db.execute(
        "SELECT * FROM users WHERE role='child' AND family_id=? ORDER BY grade DESC",
        (current_user.family_id,),
    ).fetchall()


def verify_child_ownership(db, child_id):
    """child_idが現在のファミリーに属するか確認。属さなければNoneを返す"""
    if not current_user.family_id:
        return None
    return db.execute(
        "SELECT * FROM users WHERE id=? AND role='child' AND family_id=?",
        (child_id, current_user.family_id),
    ).fetchone()

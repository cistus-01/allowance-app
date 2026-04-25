from functools import wraps
from datetime import datetime
from flask import redirect, url_for, flash
from flask_login import current_user
from .database import get_db


def get_family(db):
    if not current_user.family_id:
        return None
    return db.execute('SELECT * FROM families WHERE id = ?', (current_user.family_id,)).fetchone()


def get_family_children(db):
    """現在のファミリーに属する子どものみ返す"""
    if not current_user.family_id:
        return []
    return db.execute(
        "SELECT * FROM users WHERE role='child' AND family_id=? ORDER BY grade DESC",
        (current_user.family_id,)
    ).fetchall()


def verify_child_ownership(db, child_id):
    """child_idが現在のファミリーに属するか確認。属さなければNoneを返す"""
    if not current_user.family_id:
        return None
    return db.execute(
        "SELECT * FROM users WHERE id=? AND role='child' AND family_id=?",
        (child_id, current_user.family_id)
    ).fetchone()


def subscription_required(f):
    """トライアルまたは有効なサブスクリプションを持つファミリーのみアクセス許可"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role == 'child':
            return f(*args, **kwargs)
        db = get_db()
        family = get_family(db)
        if family is None:
            return f(*args, **kwargs)  # デモユーザー等はそのまま通す
        if family['is_lifetime_free']:
            return f(*args, **kwargs)
        status = family['subscription_status']
        if status == 'active':
            return f(*args, **kwargs)
        if status == 'trial':
            trial_end = family['trial_ends_at']
            if trial_end and datetime.fromisoformat(trial_end) > datetime.utcnow():
                return f(*args, **kwargs)
        flash('トライアル期間が終了しました。プランにご登録ください。', 'warning')
        return redirect(url_for('billing.index'))
    return decorated

import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user, logout_user
from ..database import get_db
from ..utils import get_family

bp = Blueprint('withdraw', __name__, url_prefix='/withdraw')

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')


def _get_stripe():
    if not STRIPE_SECRET_KEY:
        return None
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def _delete_family_data(db, family_id):
    """ファミリーに属する全データを削除する"""
    child_ids = [r['id'] for r in db.execute(
        "SELECT id FROM users WHERE family_id=? AND role='child'", (family_id,)
    ).fetchall()]
    all_user_ids = child_ids + [r['id'] for r in db.execute(
        "SELECT id FROM users WHERE family_id=? AND role='parent'", (family_id,)
    ).fetchall()]

    if all_user_ids:
        ph = ','.join('?' * len(all_user_ids))
        db.execute(f"DELETE FROM chore_records WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM grade_records WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM finance_records WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM salary_payments WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM goals WHERE user_id IN ({ph})", all_user_ids)
        db.execute(f"DELETE FROM password_reset_tokens WHERE user_id IN ({ph})", all_user_ids)

    db.execute("DELETE FROM grade_input_periods WHERE family_id=?", (family_id,))
    db.execute("DELETE FROM config_presets WHERE family_id=?", (family_id,))
    db.execute(f"DELETE FROM users WHERE family_id=?", (family_id,))
    db.execute("DELETE FROM families WHERE id=?", (family_id,))
    db.commit()


@bp.route('/')
@login_required
def index():
    if not current_user.is_parent:
        return redirect(url_for('home.index'))
    db = get_db()
    family = get_family(db)
    return render_template('withdraw/index.html', family=family)


@bp.route('/confirm', methods=['POST'])
@login_required
def confirm():
    if not current_user.is_parent:
        return redirect(url_for('home.index'))
    if request.form.get('confirm_text') != '退会する':
        flash('「退会する」と入力してください。', 'danger')
        return redirect(url_for('withdraw.index'))

    db = get_db()
    family = get_family(db)
    if not family:
        flash('ファミリー情報が見つかりません。', 'danger')
        return redirect(url_for('home.index'))

    status = family['subscription_status']
    sub_id = family['stripe_subscription_id']

    # サブスク有効中は期末まで利用継続、それ以外は即時削除
    if status == 'active' and sub_id:
        stripe = _get_stripe()
        period_end = None
        if stripe:
            try:
                sub = stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
                period_end = sub.current_period_end
            except Exception:
                pass

        from datetime import datetime
        if period_end:
            delete_at = datetime.utcfromtimestamp(period_end).isoformat()
        elif family['plan_ends_at']:
            delete_at = family['plan_ends_at']
        else:
            from datetime import timedelta
            delete_at = (datetime.utcnow() + timedelta(days=30)).isoformat()

        db.execute(
            "UPDATE families SET subscription_status='canceling', scheduled_delete_at=? WHERE id=?",
            (delete_at, family['id'])
        )
        db.commit()
        flash('退会手続きを受け付けました。サブスクリプション期間終了後にデータが削除されます。', 'info')
        return redirect(url_for('withdraw.scheduled'))
    else:
        # トライアル中・未契約 → 即時削除
        family_id = family['id']
        logout_user()
        _delete_family_data(db, family_id)
        flash('退会が完了しました。ご利用ありがとうございました。', 'success')
        return redirect(url_for('home.index'))


@bp.route('/scheduled')
@login_required
def scheduled():
    if not current_user.is_parent:
        return redirect(url_for('home.index'))
    db = get_db()
    family = get_family(db)
    if not family or family['subscription_status'] != 'canceling':
        return redirect(url_for('home.index'))
    return render_template('withdraw/scheduled.html', family=family)


@bp.route('/cancel', methods=['POST'])
@login_required
def cancel_withdraw():
    """退会キャンセル（サブスクリプション継続に戻す）"""
    if not current_user.is_parent:
        return redirect(url_for('home.index'))
    db = get_db()
    family = get_family(db)
    if not family or family['subscription_status'] != 'canceling':
        return redirect(url_for('home.index'))

    sub_id = family['stripe_subscription_id']
    stripe = _get_stripe()
    if stripe and sub_id:
        try:
            stripe.Subscription.modify(sub_id, cancel_at_period_end=False)
        except Exception:
            pass

    db.execute(
        "UPDATE families SET subscription_status='active', scheduled_delete_at=NULL WHERE id=?",
        (family['id'],)
    )
    db.commit()
    flash('退会をキャンセルしました。引き続きご利用いただけます。', 'success')
    return redirect(url_for('home.index'))

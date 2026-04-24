import os
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
from ..database import get_db

bp = Blueprint('billing', __name__, url_prefix='/billing')

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
APP_URL = os.environ.get('APP_URL', 'https://allowance-app-98k3.onrender.com')

def get_stripe():
    if not STRIPE_SECRET_KEY:
        return None
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe

def get_family(db):
    return db.execute(
        'SELECT * FROM families WHERE owner_user_id = ?', (current_user.id,)
    ).fetchone()

@bp.route('/')
@login_required
def index():
    if current_user.role != 'parent':
        return redirect(url_for('home.index'))
    db = get_db()
    family = get_family(db)
    now = datetime.utcnow()
    trial_active = False
    trial_days_left = 0
    if family and family['subscription_status'] == 'trial' and family['trial_ends_at']:
        trial_end = datetime.fromisoformat(family['trial_ends_at'])
        trial_active = trial_end > now
        trial_days_left = max(0, (trial_end - now).days)
    return render_template('billing/index.html',
                           family=family,
                           trial_active=trial_active,
                           trial_days_left=trial_days_left,
                           stripe_configured=bool(STRIPE_SECRET_KEY))

@bp.route('/checkout')
@login_required
def checkout():
    if current_user.role != 'parent':
        return redirect(url_for('home.index'))
    stripe = get_stripe()
    if not stripe:
        flash('決済システムの準備中です。しばらくお待ちください。', 'info')
        return redirect(url_for('billing.index'))

    db = get_db()
    family = get_family(db)
    customer_id = family['stripe_customer_id'] if family else None

    if not customer_id:
        customer = stripe.Customer.create(
            metadata={'family_id': family['id'] if family else '', 'username': current_user.username}
        )
        customer_id = customer.id
        db.execute('UPDATE families SET stripe_customer_id = ? WHERE owner_user_id = ?',
                   (customer_id, current_user.id))
        db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
        mode='subscription',
        success_url=APP_URL + url_for('billing.success') + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=APP_URL + url_for('billing.index'),
    )
    return redirect(session.url, code=303)

@bp.route('/success')
@login_required
def success():
    flash('ご登録ありがとうございます！プレミアムプランが有効になりました。', 'success')
    return redirect(url_for('home.index'))

@bp.route('/webhook', methods=['POST'])
def webhook():
    stripe = get_stripe()
    if not stripe:
        return 'ok', 200
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return 'invalid', 400

    db_path = os.environ.get('DATABASE_PATH', '/data/allowance.db')
    import sqlite3
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        sub_id = session.get('subscription')
        if customer_id and sub_id:
            db.execute(
                '''UPDATE families SET stripe_subscription_id=?, subscription_status='active',
                   plan_ends_at=NULL WHERE stripe_customer_id=?''',
                (sub_id, customer_id)
            )
            db.commit()

    elif event['type'] in ('customer.subscription.deleted', 'customer.subscription.paused'):
        sub = event['data']['object']
        customer_id = sub.get('customer')
        family = db.execute(
            "SELECT * FROM families WHERE stripe_customer_id=?", (customer_id,)
        ).fetchone()
        if family and family['subscription_status'] == 'canceling':
            # 退会予約中のサブスク終了 → 全データ削除
            from .withdraw import _delete_family_data
            _delete_family_data(db, family['id'])
        else:
            db.execute(
                "UPDATE families SET subscription_status='expired' WHERE stripe_customer_id=?",
                (customer_id,)
            )
            db.commit()

    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        db.execute(
            "UPDATE families SET subscription_status='active' WHERE stripe_customer_id=?",
            (customer_id,)
        )
        db.commit()

    db.close()
    return 'ok', 200

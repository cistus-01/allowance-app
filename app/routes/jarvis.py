import os, base64, shutil, tempfile
from flask import Blueprint, jsonify, request
from datetime import datetime
from ..database import get_db, DATABASE

bp = Blueprint('jarvis', __name__, url_prefix='/jarvis')

JARVIS_KEY = os.environ.get('JARVIS_KEY', 'jarvis-2026')

def require_key(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.args.get('key') or request.headers.get('X-Jarvis-Key', '')
        if key != JARVIS_KEY:
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@bp.route('/import-db', methods=['POST'])
@require_key
def import_db():
    data = request.get_json(silent=True) or {}
    b64 = data.get('db_b64', '')
    if not b64:
        return jsonify({'error': 'db_b64 required'}), 400
    try:
        import sqlite3 as _sqlite3
        raw = base64.b64decode(b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        tmp.write(raw)
        tmp.close()
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        shutil.move(tmp.name, DATABASE)
        # マイグレーション適用（新コードで追加された列を追加）
        conn = _sqlite3.connect(DATABASE)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(families)").fetchall()]
        if 'scheduled_delete_at' not in cols:
            conn.execute("ALTER TABLE families ADD COLUMN scheduled_delete_at DATETIME")
        if 'is_lifetime_free' not in cols:
            conn.execute("ALTER TABLE families ADD COLUMN is_lifetime_free INTEGER DEFAULT 0")
        ucols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if 'tutorial_done' not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN tutorial_done INTEGER DEFAULT 0")
        conn.execute("UPDATE families SET is_lifetime_free=1 WHERE id=(SELECT family_id FROM users WHERE username='akkun0420')")
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'bytes': len(raw)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/stats')
@require_key
def stats():
    db = get_db()
    now = datetime.utcnow()

    families = db.execute('SELECT * FROM families ORDER BY created_at DESC').fetchall()
    users = db.execute('SELECT * FROM users WHERE role="parent" ORDER BY created_at DESC').fetchall()

    trial_active = []
    trial_expired = []
    paid = []
    expired = []

    for f in families:
        status = f['subscription_status']
        if status == 'trial':
            if f['trial_ends_at'] and datetime.fromisoformat(f['trial_ends_at']) > now:
                trial_active.append(f)
            else:
                trial_expired.append(f)
        elif status == 'active':
            paid.append(f)
        else:
            expired.append(f)

    def family_detail(f):
        days_left = None
        if f['subscription_status'] == 'trial' and f['trial_ends_at']:
            ends = datetime.fromisoformat(f['trial_ends_at'])
            days_left = (ends - now).days
        return {
            'id': f['id'],
            'name': f['name'],
            'status': f['subscription_status'],
            'trial_days_left': days_left,
            'stripe_customer_id': f['stripe_customer_id'],
            'created_at': f['created_at'],
        }

    return jsonify({
        'summary': {
            'total_families': len(families),
            'trial_active': len(trial_active),
            'trial_expired': len(trial_expired),
            'paid': len(paid),
            'expired_or_other': len(expired),
            'monthly_revenue_jpy': len(paid) * 480,
        },
        'recent_signups': [family_detail(f) for f in families[:10]],
        'paid_families': [family_detail(f) for f in paid],
        'checked_at': now.isoformat(),
    })

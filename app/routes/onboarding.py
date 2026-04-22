from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from ..database import get_db
from ..utils import get_family_children

bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

@bp.route('/')
@login_required
def index():
    if current_user.role != 'parent':
        return redirect(url_for('home.index'))
    db = get_db()
    children = get_family_children(db)
    pay_rates = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM pay_rates').fetchall()}
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    return render_template('onboarding/index.html',
                           children=children,
                           pay_rates=pay_rates,
                           chore_types=chore_types,
                           step=request.args.get('step', '1'))

@bp.route('/add-child', methods=['POST'])
@login_required
def add_child():
    if current_user.role != 'parent':
        return redirect(url_for('home.index'))
    db = get_db()
    name     = request.form.get('name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    grade    = request.form.get('grade', type=int)

    if not name or not username or not password:
        flash('全項目を入力してください。', 'danger')
        return redirect(url_for('onboarding.index', step=1))

    existing = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
    if existing:
        flash('そのユーザー名は既に使われています。', 'danger')
        return redirect(url_for('onboarding.index', step=1))

    db.execute('''
        INSERT INTO users (name, username, password_hash, role, grade, family_id)
        VALUES (?, ?, ?, 'child', ?, ?)
    ''', (name, username, generate_password_hash(password), grade, current_user.family_id))
    db.commit()
    flash(f'{name} を追加しました！', 'success')

    next_step = request.form.get('next_step', '1')
    return redirect(url_for('onboarding.index', step=next_step))

@bp.route('/set-rates', methods=['POST'])
@login_required
def set_rates():
    if current_user.role != 'parent':
        return redirect(url_for('home.index'))
    db = get_db()
    for key in ('base_pay', 'grade_pay_multiplier', 'eval_excellent', 'eval_good'):
        val = request.form.get(key, type=int)
        if val is not None:
            db.execute('INSERT INTO pay_rates (key, value, label) VALUES (?,?,?) '
                       'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                       (key, val, key))
    db.commit()
    return redirect(url_for('onboarding.index', step=3))

@bp.route('/add-chore', methods=['POST'])
@login_required
def add_chore():
    if current_user.role != 'parent':
        return redirect(url_for('home.index'))
    db = get_db()
    name  = request.form.get('name', '').strip()
    price = request.form.get('price', type=int)
    if name and price:
        sort_order = (db.execute('SELECT COUNT(*) as c FROM chore_types').fetchone()['c'] + 1)
        db.execute('INSERT INTO chore_types (name, unit_price, sort_order) VALUES (?,?,?)',
                   (name, price, sort_order))
        db.commit()
    return redirect(url_for('onboarding.index', step=2))

@bp.route('/finish')
@login_required
def finish():
    return redirect(url_for('home.index'))

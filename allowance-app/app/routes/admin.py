from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from ..database import get_db

bp = Blueprint('admin', __name__, url_prefix='/admin')

def parent_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_parent:
            flash('親のみアクセスできます。', 'danger')
            return redirect(url_for('home.index'))
        return f(*args, **kwargs)
    return decorated

@bp.route('/')
@login_required
@parent_required
def index():
    db = get_db()
    children = db.execute("SELECT * FROM users WHERE role='child' ORDER BY grade DESC").fetchall()
    pay_rates = db.execute('SELECT * FROM pay_rates ORDER BY id').fetchall()
    chore_types = db.execute('SELECT * FROM chore_types ORDER BY sort_order').fetchall()
    subjects = db.execute('SELECT * FROM subjects ORDER BY sort_order').fetchall()
    return render_template('admin/index.html',
                           children=children,
                           pay_rates=pay_rates,
                           chore_types=chore_types,
                           subjects=subjects)

# ユーザー管理
@bp.route('/user/add', methods=['POST'])
@login_required
@parent_required
def add_user():
    db = get_db()
    name = request.form.get('name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    grade = request.form.get('grade', type=int)

    if not name or not username or not password:
        flash('全項目を入力してください。', 'danger')
        return redirect(url_for('admin.index'))

    existing = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
    if existing:
        flash('そのユーザー名は既に使われています。', 'danger')
        return redirect(url_for('admin.index'))

    db.execute('''
        INSERT INTO users (name, username, password_hash, role, grade)
        VALUES (?, ?, ?, 'child', ?)
    ''', (name, username, generate_password_hash(password), grade))
    db.commit()
    flash(f'{name} を追加しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/user/<int:user_id>/edit', methods=['POST'])
@login_required
@parent_required
def edit_user(user_id):
    db = get_db()
    name = request.form.get('name', '').strip()
    grade = request.form.get('grade', type=int)
    password = request.form.get('password', '').strip()

    if password:
        db.execute('UPDATE users SET name=?, grade=?, password_hash=? WHERE id=?',
                   (name, grade, generate_password_hash(password), user_id))
    else:
        db.execute('UPDATE users SET name=?, grade=? WHERE id=?', (name, grade, user_id))
    db.commit()
    flash('更新しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_user(user_id):
    db = get_db()
    db.execute('DELETE FROM users WHERE id=? AND role="child"', (user_id,))
    db.commit()
    flash('削除しました。', 'success')
    return redirect(url_for('admin.index'))

# 単価設定
@bp.route('/rates/update', methods=['POST'])
@login_required
@parent_required
def update_rates():
    db = get_db()
    for key in ['base_pay', 'grade_pay_multiplier', 'eval_excellent', 'eval_good', 'eval_poor']:
        value = request.form.get(key, type=int)
        if value is not None:
            db.execute('UPDATE pay_rates SET value=? WHERE key=?', (value, key))
    db.commit()
    flash('単価を更新しました。', 'success')
    return redirect(url_for('admin.index'))

# 家事種類管理
@bp.route('/chore/add', methods=['POST'])
@login_required
@parent_required
def add_chore():
    db = get_db()
    name = request.form.get('name', '').strip()
    unit_price = request.form.get('unit_price', type=int)
    if name and unit_price is not None:
        max_order = db.execute('SELECT MAX(sort_order) as m FROM chore_types').fetchone()['m'] or 0
        db.execute('INSERT INTO chore_types (name, unit_price, sort_order) VALUES (?, ?, ?)',
                   (name, unit_price, max_order + 1))
        db.commit()
        flash('家事を追加しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/chore/<int:chore_id>/edit', methods=['POST'])
@login_required
@parent_required
def edit_chore(chore_id):
    db = get_db()
    name = request.form.get('name', '').strip()
    unit_price = request.form.get('unit_price', type=int)
    if name and unit_price is not None:
        db.execute('UPDATE chore_types SET name=?, unit_price=? WHERE id=?',
                   (name, unit_price, chore_id))
        db.commit()
        flash('家事を更新しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/chore/<int:chore_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_chore(chore_id):
    db = get_db()
    has_records = db.execute(
        'SELECT 1 FROM chore_records WHERE chore_type_id=? LIMIT 1', (chore_id,)
    ).fetchone()
    if has_records:
        db.execute('UPDATE chore_types SET is_active=0 WHERE id=?', (chore_id,))
        flash('記録があるため非表示にしました。', 'warning')
    else:
        db.execute('DELETE FROM chore_types WHERE id=?', (chore_id,))
        flash('家事を削除しました。', 'success')
    db.commit()
    return redirect(url_for('admin.index'))

@bp.route('/chore/<int:chore_id>/move', methods=['POST'])
@login_required
@parent_required
def move_chore(chore_id):
    db = get_db()
    direction = request.form.get('direction')
    current = db.execute('SELECT * FROM chore_types WHERE id=?', (chore_id,)).fetchone()
    if not current:
        return redirect(url_for('admin.index'))
    if direction == 'up':
        neighbor = db.execute(
            'SELECT * FROM chore_types WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1',
            (current['sort_order'],)
        ).fetchone()
    else:
        neighbor = db.execute(
            'SELECT * FROM chore_types WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1',
            (current['sort_order'],)
        ).fetchone()
    if neighbor:
        db.execute('UPDATE chore_types SET sort_order=? WHERE id=?',
                   (neighbor['sort_order'], chore_id))
        db.execute('UPDATE chore_types SET sort_order=? WHERE id=?',
                   (current['sort_order'], neighbor['id']))
        db.commit()
    return redirect(url_for('admin.index'))

# 教科管理
@bp.route('/subject/add', methods=['POST'])
@login_required
@parent_required
def add_subject():
    db = get_db()
    name = request.form.get('name', '').strip()
    if name:
        max_order = db.execute('SELECT MAX(sort_order) as m FROM subjects').fetchone()['m'] or 0
        db.execute('INSERT INTO subjects (name, sort_order) VALUES (?, ?)', (name, max_order + 1))
        new_id = db.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        # 全学年に追加
        for grade in range(1, 7):
            db.execute('INSERT OR IGNORE INTO grade_subjects (grade, subject_id) VALUES (?, ?)',
                       (grade, new_id))
        db.commit()
        flash('教科を追加しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/subject/<int:subject_id>/edit', methods=['POST'])
@login_required
@parent_required
def edit_subject(subject_id):
    db = get_db()
    name = request.form.get('name', '').strip()
    if name:
        db.execute('UPDATE subjects SET name=? WHERE id=?', (name, subject_id))
        db.commit()
        flash('教科を更新しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/subject/<int:subject_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_subject(subject_id):
    db = get_db()
    has_records = db.execute(
        'SELECT 1 FROM grade_records WHERE subject_id=? LIMIT 1', (subject_id,)
    ).fetchone()
    if has_records:
        db.execute('UPDATE subjects SET is_active=0 WHERE id=?', (subject_id,))
        flash('記録があるため非表示にしました。', 'warning')
    else:
        db.execute('DELETE FROM grade_subjects WHERE subject_id=?', (subject_id,))
        db.execute('DELETE FROM subjects WHERE id=?', (subject_id,))
        flash('教科を削除しました。', 'success')
    db.commit()
    return redirect(url_for('admin.index'))

@bp.route('/subject/<int:subject_id>/move', methods=['POST'])
@login_required
@parent_required
def move_subject(subject_id):
    db = get_db()
    direction = request.form.get('direction')
    current = db.execute('SELECT * FROM subjects WHERE id=?', (subject_id,)).fetchone()
    if not current:
        return redirect(url_for('admin.index'))
    if direction == 'up':
        neighbor = db.execute(
            'SELECT * FROM subjects WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1',
            (current['sort_order'],)
        ).fetchone()
    else:
        neighbor = db.execute(
            'SELECT * FROM subjects WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1',
            (current['sort_order'],)
        ).fetchone()
    if neighbor:
        db.execute('UPDATE subjects SET sort_order=? WHERE id=?',
                   (neighbor['sort_order'], subject_id))
        db.execute('UPDATE subjects SET sort_order=? WHERE id=?',
                   (current['sort_order'], neighbor['id']))
        db.commit()
    return redirect(url_for('admin.index'))

# 単価表（全員閲覧）
@bp.route('/rates')
@login_required
def rates():
    db = get_db()
    pay_rates = {r['key']: r for r in db.execute('SELECT * FROM pay_rates').fetchall()}
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    return render_template('admin/rates.html', pay_rates=pay_rates, chore_types=chore_types)

# 給料明細印刷（親専用）
@bp.route('/payslip')
@login_required
@parent_required
def payslip():
    from ..salary import calc_chore_pay, calc_academic_pay_for_month, get_pay_rates
    db = get_db()
    today = date.today()
    year  = request.args.get('year',  today.year,  type=int)
    month = request.args.get('month', today.month, type=int)


    children    = db.execute("SELECT * FROM users WHERE role='child' ORDER BY grade DESC").fetchall()
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    rates       = get_pay_rates()

    slips = []
    for child in children:
        grade_pay, academic_pay, _ = calc_academic_pay_for_month(child['id'], year, month)
        base_pay = rates.get('base_pay', 100)

        # 家事別集計
        chore_detail = []
        chore_total  = 0
        month_str    = f'{year}-{month:02d}'
        for ct in chore_types:
            cnt = db.execute('''
                SELECT COUNT(*) AS c FROM chore_records
                WHERE user_id=? AND chore_type_id=?
                  AND strftime('%Y-%m', record_date)=?
            ''', (child['id'], ct['id'], month_str)).fetchone()['c']
            # 分割を考慮した実際の報酬
            pay = 0
            days = db.execute('''
                SELECT record_date FROM chore_records
                WHERE user_id=? AND chore_type_id=?
                  AND strftime('%Y-%m', record_date)=?
            ''', (child['id'], ct['id'], month_str)).fetchall()
            for day in days:
                shared_cnt = db.execute('''
                    SELECT COUNT(*) AS c FROM chore_records
                    WHERE chore_type_id=? AND record_date=?
                ''', (ct['id'], day['record_date'])).fetchone()['c']
                pay += ct['unit_price'] // shared_cnt
            chore_detail.append({'name': ct['name'], 'count': cnt, 'pay': pay})
            chore_total += pay

        total = base_pay + grade_pay + academic_pay + chore_total
        slips.append({
            'user': child,
            'base_pay': base_pay,
            'grade_pay': grade_pay,
            'academic_pay': academic_pay,
            'chore_detail': chore_detail,
            'chore_total': chore_total,
            'total': total,
        })

    prev_year,  prev_month  = (year, month - 1) if month > 1  else (year - 1, 12)
    next_year,  next_month  = (year, month + 1) if month < 12 else (year + 1,  1)

    return render_template('admin/payslip.html',
                           slips=slips,
                           year=year, month=month,
                           today=today,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month)

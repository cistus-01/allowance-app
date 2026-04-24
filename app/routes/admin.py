import json
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from ..database import get_db
from ..utils import get_family_children, verify_child_ownership, subscription_required

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
    from ..utils import get_family
    from datetime import datetime
    db = get_db()
    children = get_family_children(db)
    pay_rates = db.execute('SELECT * FROM pay_rates ORDER BY id').fetchall()
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    subjects = db.execute('SELECT * FROM subjects ORDER BY sort_order').fetchall()
    family = get_family(db)
    parent = db.execute('SELECT * FROM users WHERE id=?', (current_user.id,)).fetchone()

    trial_days_left = None
    plan_ends_str = None
    if family:
        status = family['subscription_status']
        if status == 'trial' and family['trial_ends_at']:
            delta = datetime.fromisoformat(family['trial_ends_at']) - datetime.utcnow()
            trial_days_left = max(0, delta.days)
        if family['plan_ends_at']:
            plan_ends_str = family['plan_ends_at'][:10]

    # プリセット
    presets = {}
    if family:
        rows = db.execute('SELECT * FROM config_presets WHERE family_id=?', (family['id'],)).fetchall()
        for r in rows:
            presets[r['slot']] = r

    return render_template('admin/index.html',
                           children=children,
                           pay_rates=pay_rates,
                           chore_types=chore_types,
                           subjects=subjects,
                           family=family,
                           parent=parent,
                           trial_days_left=trial_days_left,
                           plan_ends_str=plan_ends_str,
                           presets=presets)

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
        INSERT INTO users (name, username, password_hash, role, grade, family_id)
        VALUES (?, ?, ?, 'child', ?, ?)
    ''', (name, username, generate_password_hash(password), grade, current_user.family_id))
    db.commit()
    flash(f'{name} を追加しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/user/<int:user_id>/edit', methods=['POST'])
@login_required
@parent_required
def edit_user(user_id):
    db = get_db()
    if not verify_child_ownership(db, user_id):
        flash('権限がありません。', 'danger')
        return redirect(url_for('admin.index'))
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
    if not verify_child_ownership(db, user_id):
        flash('権限がありません。', 'danger')
        return redirect(url_for('admin.index'))
    db.execute('DELETE FROM users WHERE id=? AND role="child"', (user_id,))
    db.commit()
    flash('削除しました。', 'success')
    return redirect(url_for('admin.index'))

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
        for grade in range(1, 7):
            db.execute('INSERT OR IGNORE INTO grade_subjects (grade, subject_id) VALUES (?, ?)',
                       (grade, new_id))
        db.commit()
        flash('教科を追加しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/chore/<int:chore_id>/edit', methods=['POST'])
@login_required
@parent_required
def edit_chore(chore_id):
    db = get_db()
    name = request.form.get('name', '').strip()
    unit_price = request.form.get('unit_price', type=int)
    if name and unit_price is not None:
        db.execute('UPDATE chore_types SET name=?, unit_price=? WHERE id=?', (name, unit_price, chore_id))
        db.commit()
        flash('家事を更新しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/chore/<int:chore_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_chore(chore_id):
    db = get_db()
    db.execute('UPDATE chore_types SET is_active=0 WHERE id=?', (chore_id,))
    db.commit()
    flash('家事を削除しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/chore/reorder', methods=['POST'])
@login_required
@parent_required
def reorder_chores():
    db = get_db()
    ids = request.get_json()
    for i, chore_id in enumerate(ids):
        db.execute('UPDATE chore_types SET sort_order=? WHERE id=?', (i, chore_id))
    db.commit()
    return '', 204

@bp.route('/subject/<int:subject_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_subject(subject_id):
    db = get_db()
    db.execute('DELETE FROM subjects WHERE id=?', (subject_id,))
    db.commit()
    flash('教科を削除しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/subject/reorder', methods=['POST'])
@login_required
@parent_required
def reorder_subjects():
    db = get_db()
    ids = request.get_json()
    for i, subject_id in enumerate(ids):
        db.execute('UPDATE subjects SET sort_order=? WHERE id=?', (i, subject_id))
    db.commit()
    return '', 204

@bp.route('/subject/<int:subject_id>/move_unused', methods=['POST'])
@login_required
@parent_required
def move_subject(subject_id):
    db = get_db()
    direction = request.form.get('direction')
    current = db.execute('SELECT sort_order FROM subjects WHERE id=?', (subject_id,)).fetchone()
    if not current:
        return redirect(url_for('admin.index'))
    cur_order = current['sort_order']
    if direction == 'up':
        swap = db.execute('SELECT id, sort_order FROM subjects WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1', (cur_order,)).fetchone()
    else:
        swap = db.execute('SELECT id, sort_order FROM subjects WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1', (cur_order,)).fetchone()
    if swap:
        db.execute('UPDATE subjects SET sort_order=? WHERE id=?', (swap['sort_order'], subject_id))
        db.execute('UPDATE subjects SET sort_order=? WHERE id=?', (cur_order, swap['id']))
        db.commit()
    return redirect(url_for('admin.index'))

@bp.route('/profile/edit', methods=['POST'])
@login_required
@parent_required
def edit_profile():
    from werkzeug.security import generate_password_hash
    db = get_db()
    username = request.form.get('username', '').strip()
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    family_name = request.form.get('family_name', '').strip()
    if username and username != current_user.username:
        existing = db.execute('SELECT id FROM users WHERE username=? AND id!=?',
                              (username, current_user.id)).fetchone()
        if existing:
            flash('そのログインIDは既に使われています。', 'danger')
            return redirect(url_for('admin.index'))
        db.execute('UPDATE users SET username=? WHERE id=?', (username, current_user.id))
    if name:
        db.execute('UPDATE users SET name=? WHERE id=?', (name, current_user.id))
    if email:
        db.execute('UPDATE users SET email=? WHERE id=?', (email, current_user.id))
    if password:
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(password), current_user.id))
    if family_name and current_user.family_id:
        db.execute('UPDATE families SET name=? WHERE id=?', (family_name, current_user.family_id))
    db.commit()
    flash('プロフィールを更新しました。', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/rates')
@login_required
@parent_required
def rates():
    db = get_db()
    pay_rates = {r['key']: r for r in db.execute('SELECT * FROM pay_rates').fetchall()}
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    return render_template('admin/rates.html', pay_rates=pay_rates, chore_types=chore_types)

@bp.route('/payslip')
@login_required
@parent_required
def payslip():
    from ..salary import calc_monthly_salary
    db = get_db()
    today = date.today()
    year  = request.args.get('year',  today.year,  type=int)
    month = request.args.get('month', today.month, type=int)

    children    = get_family_children(db)
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()

    # 明細は前月の家事を表示（前月分が今月給料に反映される）
    prev_month = month - 1 if month > 1 else 12
    prev_year  = year if month > 1 else year - 1
    prev_month_str = f'{prev_year}-{prev_month:02d}'

    slips = []
    for child in children:
        salary = calc_monthly_salary(child['id'], year, month)
        chore_detail = []
        for ct in chore_types:
            cnt = db.execute('''
                SELECT COUNT(*) AS c FROM chore_records
                WHERE user_id=? AND chore_type_id=?
                  AND strftime('%Y-%m', record_date)=?
            ''', (child['id'], ct['id'], prev_month_str)).fetchone()['c']
            pay = 0
            days = db.execute('''
                SELECT record_date FROM chore_records
                WHERE user_id=? AND chore_type_id=?
                  AND strftime('%Y-%m', record_date)=?
            ''', (child['id'], ct['id'], prev_month_str)).fetchall()
            for day in days:
                shared_cnt = db.execute('''
                    SELECT COUNT(*) AS c FROM chore_records
                    WHERE chore_type_id=? AND record_date=?
                ''', (ct['id'], day['record_date'])).fetchone()['c']
                pay += ct['unit_price'] // shared_cnt
            chore_detail.append({'name': ct['name'], 'count': cnt, 'pay': pay})

        slips.append({
            'user': child,
            'base_pay':     salary['base_pay'],
            'grade_pay':    salary['grade_pay'],
            'academic_pay': salary['academic_pay'],
            'chore_detail': chore_detail,
            'chore_total':  salary['chore_pay'],
            'bonus_pay':    salary['bonus_pay'],
            'bonus_cnt':    salary['bonus_cnt'],
            'bonus_subjects': salary['bonus_subjects'],
            'total':        salary['total'],
        })

    prev_year,  prev_month  = (year, month - 1) if month > 1  else (year - 1, 12)
    next_year,  next_month  = (year, month + 1) if month < 12 else (year + 1,  1)

    return render_template('admin/payslip.html',
                           slips=slips,
                           year=year, month=month,
                           today=today,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month)

@bp.route('/summer_slip')
@login_required
@parent_required
def summer_slip():
    from ..salary import calc_monthly_salary
    import datetime
    db = get_db()
    today = datetime.date.today()
    start_date_str = request.args.get('start_date', '')
    deadline_str = ''
    is_past_deadline = False

    if start_date_str:
        try:
            start = datetime.date.fromisoformat(start_date_str)
            deadline = start + datetime.timedelta(days=14)
            deadline_str = deadline.strftime('%Y年%m月%d日')
            is_past_deadline = today > deadline
        except ValueError:
            start_date_str = ''

    children = get_family_children(db)
    slips = []

    if start_date_str:
        for child in children:
            # 前月給料（夏休み開始日の前月）
            start = datetime.date.fromisoformat(start_date_str)
            prev_month = start.month - 1 if start.month > 1 else 12
            prev_year  = start.year if start.month > 1 else start.year - 1
            prev_salary = calc_monthly_salary(child['id'], prev_year, prev_month)
            prev_month_label = f'{prev_year}年{prev_month}月'

            # 既に付与済みか確認
            given = db.execute('''
                SELECT id, amount, record_date FROM finance_records
                WHERE user_id=? AND category='summer_bonus'
                  AND strftime('%Y', record_date)=?
                ORDER BY record_date DESC LIMIT 1
            ''', (child['id'], str(start.year))).fetchone()

            slips.append({
                'child': child,
                'prev_total': prev_salary['total'],
                'prev_month_label': prev_month_label,
                'already_given': given is not None,
                'given_id': given['id'] if given else None,
                'given_amount': given['amount'] if given else 0,
                'given_date': given['record_date'] if given else '',
            })

    return render_template('admin/summer_slip.html',
                           slips=slips,
                           start_date=start_date_str,
                           deadline=deadline_str,
                           is_past_deadline=is_past_deadline,
                           today=today)

@bp.route('/summer_bonus/give', methods=['POST'])
@login_required
@parent_required
def give_summer_bonus():
    import datetime
    db = get_db()
    user_id = request.form.get('user_id', type=int)
    amount   = request.form.get('amount', type=int)
    start_date_str = request.form.get('start_date', '')
    if not verify_child_ownership(db, user_id):
        flash('権限がありません。', 'danger')
        return redirect(url_for('admin.summer_slip'))
    if user_id and amount and amount > 0:
        record_date = str(datetime.date.today())
        db.execute('''
            INSERT INTO finance_records (user_id, record_date, type, category, amount, note, created_by)
            VALUES (?, ?, 'income', 'summer_bonus', ?, '夏休みボーナス（全宿題2週間以内完了）', ?)
        ''', (user_id, record_date, amount, current_user.id))
        db.commit()
        flash('夏休みボーナスを付与しました！', 'success')
    return redirect(url_for('admin.summer_slip', start_date=start_date_str))

def _grade_pay_unit(db, user_id):
    """その子の学年給（= テストボーナス1科目の単価）を返す"""
    multiplier = db.execute('SELECT value FROM pay_rates WHERE key="grade_pay_multiplier"').fetchone()
    m = multiplier['value'] if multiplier else 50
    user = db.execute('SELECT grade FROM users WHERE id=?', (user_id,)).fetchone()
    grade = user['grade'] if user and user['grade'] else 1
    return grade * m

@bp.route('/bonus', methods=['GET'])
@login_required
@parent_required
def bonus():
    from datetime import date
    db = get_db()
    children = get_family_children(db)
    subjects = db.execute('SELECT * FROM subjects ORDER BY sort_order').fetchall()
    # 子供ごとの単価（学年給）を辞書で渡す
    unit_prices = {c['id']: _grade_pay_unit(db, c['id']) for c in children}
    child_ids = [c['id'] for c in children]
    bonus_records = []
    if child_ids:
        placeholders = ','.join('?' * len(child_ids))
        rows = db.execute(f'''
            SELECT f.id, f.record_date, f.item, f.amount, f.note, u.name as child_name, u.id as child_id
            FROM finance_records f
            JOIN users u ON f.user_id = u.id
            WHERE f.user_id IN ({placeholders}) AND f.category = 'test_bonus'
            ORDER BY f.record_date DESC, u.name LIMIT 100
        ''', child_ids).fetchall()
        bonus_records = rows
    return render_template('admin/bonus.html', children=children, subjects=subjects,
                           bonus_records=bonus_records, unit_prices=unit_prices,
                           today=date.today())

@bp.route('/bonus/give', methods=['POST'])
@login_required
@parent_required
def give_bonus():
    from datetime import date
    db = get_db()
    user_id = request.form.get('user_id', type=int)
    record_date = request.form.get('record_date') or str(date.today())
    note = request.form.get('note', '').strip()
    subject_names = request.form.getlist('subjects')
    if not verify_child_ownership(db, user_id):
        flash('権限がありません。', 'danger')
        return redirect(url_for('admin.bonus'))
    unit_price = _grade_pay_unit(db, user_id)
    if user_id and subject_names:
        for subject in subject_names:
            db.execute('''
                INSERT INTO finance_records (user_id, record_date, type, category, item, amount, note, created_by)
                VALUES (?, ?, 'income', 'test_bonus', ?, ?, ?, ?)
            ''', (user_id, record_date, subject, unit_price, note or 'テスト満点ボーナス', current_user.id))
        db.commit()
        flash(f'テスト満点ボーナス {len(subject_names)}科目 ¥{unit_price * len(subject_names):,} を記録しました。', 'success')
    return redirect(url_for('admin.bonus'))

@bp.route('/bonus/delete/<int:record_id>', methods=['POST'])
@login_required
@parent_required
def delete_bonus(record_id):
    db = get_db()
    rec = db.execute('''
        SELECT user_id FROM finance_records
        WHERE id=? AND category IN ('test_bonus', 'summer_bonus')
    ''', (record_id,)).fetchone()
    if not rec or not verify_child_ownership(db, rec['user_id']):
        flash('権限がありません。', 'danger')
        return redirect(url_for('admin.bonus'))
    db.execute('DELETE FROM finance_records WHERE id=?', (record_id,))
    db.commit()
    flash('削除しました。', 'success')
    redirect_to = request.form.get('redirect_to', 'bonus')
    if redirect_to == 'summer_slip':
        return redirect(url_for('admin.summer_slip', start_date=request.form.get('start_date', '')))
    return redirect(url_for('admin.bonus'))


@bp.route('/preset/<int:slot>/save', methods=['POST'])
@login_required
@parent_required
def save_preset(slot):
    if slot not in (1, 2, 3):
        flash('無効なスロットです。', 'danger')
        return redirect(url_for('admin.index'))
    from ..utils import get_family
    db = get_db()
    family = get_family(db)
    if not family:
        flash('ファミリーが見つかりません。', 'danger')
        return redirect(url_for('admin.index'))

    label = request.form.get('label', '').strip() or f'設定{slot}'
    pay_rates = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM pay_rates').fetchall()}
    subjects = [{'name': r['name'], 'sort_order': r['sort_order']}
                for r in db.execute('SELECT name, sort_order FROM subjects WHERE is_active=1 ORDER BY sort_order').fetchall()]
    chore_types = [{'name': r['name'], 'unit_price': r['unit_price'], 'sort_order': r['sort_order']}
                   for r in db.execute('SELECT name, unit_price, sort_order FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()]

    db.execute('''
        INSERT INTO config_presets (family_id, slot, label, pay_rates_json, subjects_json, chore_types_json, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(family_id, slot) DO UPDATE SET
            label=excluded.label,
            pay_rates_json=excluded.pay_rates_json,
            subjects_json=excluded.subjects_json,
            chore_types_json=excluded.chore_types_json,
            saved_at=CURRENT_TIMESTAMP
    ''', (family['id'], slot, label, json.dumps(pay_rates, ensure_ascii=False),
          json.dumps(subjects, ensure_ascii=False), json.dumps(chore_types, ensure_ascii=False)))
    db.commit()
    flash(f'「{label}」を保存しました。', 'success')
    return redirect(url_for('admin.index') + '#presets')


@bp.route('/preset/<int:slot>/load', methods=['POST'])
@login_required
@parent_required
def load_preset(slot):
    if slot not in (1, 2, 3):
        flash('無効なスロットです。', 'danger')
        return redirect(url_for('admin.index'))
    from ..utils import get_family
    db = get_db()
    family = get_family(db)
    if not family:
        flash('ファミリーが見つかりません。', 'danger')
        return redirect(url_for('admin.index'))

    preset = db.execute('SELECT * FROM config_presets WHERE family_id=? AND slot=?',
                        (family['id'], slot)).fetchone()
    if not preset:
        flash('保存されたデータがありません。', 'warning')
        return redirect(url_for('admin.index'))

    pay_rates = json.loads(preset['pay_rates_json'])
    subjects = json.loads(preset['subjects_json'])
    chore_types = json.loads(preset['chore_types_json'])

    # 単価を復元
    for key, value in pay_rates.items():
        db.execute('UPDATE pay_rates SET value=? WHERE key=?', (value, key))

    # 教科を復元（既存を一旦非表示、プリセット内容を有効化）
    db.execute('UPDATE subjects SET is_active=0')
    for s in subjects:
        existing = db.execute('SELECT id FROM subjects WHERE name=?', (s['name'],)).fetchone()
        if existing:
            db.execute('UPDATE subjects SET is_active=1, sort_order=? WHERE id=?',
                       (s['sort_order'], existing['id']))
        else:
            db.execute('INSERT INTO subjects (name, sort_order, is_active) VALUES (?, ?, 1)',
                       (s['name'], s['sort_order']))
            new_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            for grade in range(1, 7):
                db.execute('INSERT OR IGNORE INTO grade_subjects (grade, subject_id) VALUES (?, ?)',
                           (grade, new_id))

    # 家事を復元
    db.execute('UPDATE chore_types SET is_active=0')
    for ct in chore_types:
        existing = db.execute('SELECT id FROM chore_types WHERE name=?', (ct['name'],)).fetchone()
        if existing:
            db.execute('UPDATE chore_types SET is_active=1, unit_price=?, sort_order=? WHERE id=?',
                       (ct['unit_price'], ct['sort_order'], existing['id']))
        else:
            db.execute('INSERT INTO chore_types (name, unit_price, sort_order, is_active) VALUES (?, ?, ?, 1)',
                       (ct['name'], ct['unit_price'], ct['sort_order']))

    db.commit()
    flash(f'「{preset["label"]}」を読み込みました。', 'success')
    return redirect(url_for('admin.index') + '#presets')


_DEFAULT_PAY_RATES = {
    'base_pay': 100,
    'grade_pay_multiplier': 50,
    'eval_excellent': 150,
    'eval_good': 20,
    'eval_poor': 0,
}
_DEFAULT_SUBJECTS = [
    {'name': '国語', 'sort_order': 1}, {'name': '算数', 'sort_order': 2},
    {'name': '理科', 'sort_order': 3}, {'name': '社会', 'sort_order': 4},
    {'name': '英語', 'sort_order': 5}, {'name': '音楽', 'sort_order': 6},
    {'name': '体育', 'sort_order': 7}, {'name': '図工', 'sort_order': 8},
    {'name': '道徳', 'sort_order': 9},
]
_DEFAULT_CHORE_TYPES = [
    {'name': '掃除', 'unit_price': 30, 'sort_order': 1},
    {'name': '洗濯', 'unit_price': 10, 'sort_order': 2},
    {'name': '干す',  'unit_price': 30, 'sort_order': 3},
    {'name': '洗い物', 'unit_price': 20, 'sort_order': 4},
    {'name': 'しまう', 'unit_price': 10, 'sort_order': 5},
]


@bp.route('/preset/default/load', methods=['POST'])
@login_required
@parent_required
def load_default_preset():
    db = get_db()

    for key, value in _DEFAULT_PAY_RATES.items():
        db.execute('UPDATE pay_rates SET value=? WHERE key=?', (value, key))

    db.execute('UPDATE subjects SET is_active=0')
    for s in _DEFAULT_SUBJECTS:
        existing = db.execute('SELECT id FROM subjects WHERE name=?', (s['name'],)).fetchone()
        if existing:
            db.execute('UPDATE subjects SET is_active=1, sort_order=? WHERE id=?',
                       (s['sort_order'], existing['id']))
        else:
            db.execute('INSERT INTO subjects (name, sort_order, is_active) VALUES (?, ?, 1)',
                       (s['name'], s['sort_order']))
            new_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            for grade in range(1, 7):
                db.execute('INSERT OR IGNORE INTO grade_subjects (grade, subject_id) VALUES (?, ?)',
                           (grade, new_id))

    db.execute('UPDATE chore_types SET is_active=0')
    for ct in _DEFAULT_CHORE_TYPES:
        existing = db.execute('SELECT id FROM chore_types WHERE name=?', (ct['name'],)).fetchone()
        if existing:
            db.execute('UPDATE chore_types SET is_active=1, unit_price=?, sort_order=? WHERE id=?',
                       (ct['unit_price'], ct['sort_order'], existing['id']))
        else:
            db.execute('INSERT INTO chore_types (name, unit_price, sort_order, is_active) VALUES (?, ?, ?, 1)',
                       (ct['name'], ct['unit_price'], ct['sort_order']))

    db.commit()
    flash('デフォルト設定に戻しました。', 'success')
    return redirect(url_for('admin.index') + '#presets')

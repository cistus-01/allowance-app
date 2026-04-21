from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import get_pay_rates, get_prev_term, month_to_term
from ..utils import get_family_children, verify_child_ownership
from datetime import date

bp = Blueprint('grades', __name__, url_prefix='/grades')

EVAL_VALUES = ['◎', '〇', '△']

def get_target_user_id(db):
    if current_user.is_parent:
        child_id = request.args.get('child_id', type=int) or request.form.get('child_id', type=int)
        if child_id and not verify_child_ownership(db, child_id):
            return None
        return child_id
    return current_user.id

def calc_display_academic_pay(grade_records, rates):
    """表示中の成績レコードから学業給を計算"""
    eval_map = {
        '◎': rates.get('eval_excellent', 150),
        '〇': rates.get('eval_good', 20),
        '△': rates.get('eval_poor', 0),
    }
    total = 0
    for r in grade_records.values():
        for e in [r['eval_1'], r['eval_2'], r['eval_3']]:
            if e:
                total += eval_map.get(e, 0)
    return total

@bp.route('/')
@login_required
def index():
    db = get_db()
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    term = request.args.get('term', 1, type=int)

    target_id = get_target_user_id(db)
    if target_id is None and current_user.is_parent:
        children = get_family_children(db)
        if children:
            target_id = children[0]['id']

    target_user = db.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone()

    period = db.execute(
        'SELECT is_open FROM grade_input_periods WHERE year=? AND term=?', (year, term)
    ).fetchone()
    is_open = period['is_open'] if period else False

    subjects = db.execute('''
        SELECT s.* FROM subjects s
        JOIN grade_subjects gs ON s.id = gs.subject_id
        WHERE gs.grade = ? AND s.is_active = 1
        ORDER BY s.sort_order
    ''', (target_user['grade'],)).fetchall() if target_user else []

    grade_records = {}
    if target_user:
        rows = db.execute(
            'SELECT * FROM grade_records WHERE user_id=? AND year=? AND term=?',
            (target_id, year, term)
        ).fetchall()
        for r in rows:
            grade_records[r['subject_id']] = r

    rates = get_pay_rates()
    academic_pay = calc_display_academic_pay(grade_records, rates)

    # 今学期の成績が何月の給料に反映されるか（表示用ヒント）
    # 今学期 → 次学期の給料に反映
    if term == 3:
        applies_year, applies_term = year + 1, 1
    else:
        applies_year, applies_term = year, term + 1
    applies_label = f'{applies_year}年{applies_term}学期'

    # 今月の給料に反映されている成績（前学期）
    current_term = month_to_term(today.month)
    prev_year_ref, prev_term_ref = get_prev_term(today.year, current_term)
    current_ref_label = f'{prev_year_ref}年{prev_term_ref}学期'

    children = None
    if current_user.is_parent:
        children = get_family_children(db)

    return render_template('grades/index.html',
                           target_user=target_user,
                           target_id=target_id,
                           subjects=subjects,
                           grade_records=grade_records,
                           year=year, term=term,
                           is_open=is_open,
                           academic_pay=academic_pay,
                           eval_values=EVAL_VALUES,
                           children=children,
                           today=today,
                           applies_label=applies_label,
                           current_ref_label=current_ref_label,
                           rates=rates)

@bp.route('/save_ajax', methods=['POST'])
@login_required
def save_ajax():
    """Ajax用：1教科の1観点だけ更新して成績給合計を返す"""
    db = get_db()
    data = request.get_json()
    year       = data.get('year')
    term       = data.get('term')
    target_id  = data.get('user_id')
    subject_id = data.get('subject_id')
    obs_index  = data.get('obs_index')   # 1, 2, 3
    eval_val   = data.get('eval_val')    # '◎','〇','△' or None

    # 権限チェック
    db = get_db()
    if current_user.is_parent and target_id and not verify_child_ownership(db, int(target_id)):
        return jsonify({'error': '権限がありません'}), 403
    if current_user.is_child:
        if int(target_id) != current_user.id:
            return jsonify({'error': '権限がありません'}), 403
        period = db.execute(
            'SELECT is_open FROM grade_input_periods WHERE year=? AND term=?', (year, term)
        ).fetchone()
        if not period or not period['is_open']:
            return jsonify({'error': '成績入力期間ではありません'}), 403

    # 既存レコードを取得（なければデフォルト）
    existing = db.execute(
        'SELECT * FROM grade_records WHERE user_id=? AND subject_id=? AND year=? AND term=?',
        (target_id, subject_id, year, term)
    ).fetchone()

    if existing:
        e1 = existing['eval_1']
        e2 = existing['eval_2']
        e3 = existing['eval_3']
    else:
        e1, e2, e3 = None, None, None

    if obs_index == 1:   e1 = eval_val or None
    elif obs_index == 2: e2 = eval_val or None
    elif obs_index == 3: e3 = eval_val or None

    db.execute('''
        INSERT INTO grade_records (user_id, subject_id, year, term, eval_1, eval_2, eval_3, entered_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, subject_id, year, term) DO UPDATE SET
            eval_1=excluded.eval_1, eval_2=excluded.eval_2, eval_3=excluded.eval_3,
            entered_by=excluded.entered_by, updated_at=CURRENT_TIMESTAMP
    ''', (target_id, subject_id, year, term, e1, e2, e3, current_user.id))
    db.commit()

    # この学期全体の成績給を再計算
    rows = db.execute(
        'SELECT eval_1, eval_2, eval_3 FROM grade_records WHERE user_id=? AND year=? AND term=?',
        (target_id, year, term)
    ).fetchall()
    rates = get_pay_rates()
    eval_map = {
        '◎': rates.get('eval_excellent', 150),
        '〇': rates.get('eval_good', 20),
        '△': 0,
    }
    academic_pay = 0
    subject_pay = 0
    for row in rows:
        row_pay = 0
        for e in [row['eval_1'], row['eval_2'], row['eval_3']]:
            if e: row_pay += eval_map.get(e, 0)
        academic_pay += row_pay

    # この教科だけの給与
    updated = db.execute(
        'SELECT * FROM grade_records WHERE user_id=? AND subject_id=? AND year=? AND term=?',
        (target_id, subject_id, year, term)
    ).fetchone()
    if updated:
        for e in [updated['eval_1'], updated['eval_2'], updated['eval_3']]:
            if e: subject_pay += eval_map.get(e, 0)

    return jsonify({
        'ok': True,
        'eval_1': e1, 'eval_2': e2, 'eval_3': e3,
        'subject_pay': subject_pay,
        'academic_pay': academic_pay,
    })

@bp.route('/toggle_period', methods=['POST'])
@login_required
def toggle_period():
    if not current_user.is_parent:
        flash('権限がありません。', 'danger')
        return redirect(url_for('grades.index'))
    db = get_db()
    year = request.form.get('year', type=int)
    term = request.form.get('term', type=int)
    child_id = request.form.get('child_id', type=int)

    existing = db.execute(
        'SELECT id, is_open FROM grade_input_periods WHERE year=? AND term=?', (year, term)
    ).fetchone()
    if existing:
        new_state = 0 if existing['is_open'] else 1
        db.execute(
            'UPDATE grade_input_periods SET is_open=? WHERE year=? AND term=?',
            (new_state, year, term)
        )
    else:
        db.execute(
            'INSERT INTO grade_input_periods (year, term, is_open, opened_at) VALUES (?, ?, 1, CURRENT_TIMESTAMP)',
            (year, term)
        )
    db.commit()
    return redirect(url_for('grades.index', year=year, term=term, child_id=child_id))

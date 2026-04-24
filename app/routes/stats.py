from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import calc_monthly_salary
from ..utils import get_family_children, verify_child_ownership
from datetime import date

bp = Blueprint('stats', __name__, url_prefix='/stats')

def _get_target_id(db):
    if current_user.is_parent:
        child_id = request.args.get('child_id', type=int)
        if child_id and verify_child_ownership(db, child_id):
            return child_id
        children = get_family_children(db)
        return children[0]['id'] if children else None
    return current_user.id

@bp.route('/')
@login_required
def index():
    db = get_db()
    today = date.today()
    target_id = _get_target_id(db)
    if not target_id:
        return render_template('stats/index.html', error=True)

    target_user = db.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone()

    # 累計家事回数・累計家事収入
    total_chore_count = db.execute(
        'SELECT COUNT(*) as cnt FROM chore_records WHERE user_id=?', (target_id,)
    ).fetchone()['cnt']

    total_chore_pay = db.execute('''
        SELECT COALESCE(SUM(ct.unit_price), 0) as total
        FROM chore_records cr
        JOIN chore_types ct ON ct.id = cr.chore_type_id
        WHERE cr.user_id=?
    ''', (target_id,)).fetchone()['total']

    # テストボーナス累計
    test_bonus_row = db.execute('''
        SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
        FROM finance_records
        WHERE user_id=? AND category='test_bonus'
    ''', (target_id,)).fetchone()
    test_bonus_count = test_bonus_row['cnt']
    test_bonus_total = test_bonus_row['total']

    # 今月・先月の家事日数と種類別件数
    month_str = f'{today.year}-{today.month:02d}'
    prev_m = today.month - 1 if today.month > 1 else 12
    prev_y = today.year if today.month > 1 else today.year - 1
    prev_month_str = f'{prev_y}-{prev_m:02d}'

    chore_days_this_month = db.execute('''
        SELECT COUNT(DISTINCT record_date) as cnt FROM chore_records
        WHERE user_id=? AND strftime('%Y-%m', record_date)=?
    ''', (target_id, month_str)).fetchone()['cnt']

    chore_days_prev_month = db.execute('''
        SELECT COUNT(DISTINCT record_date) as cnt FROM chore_records
        WHERE user_id=? AND strftime('%Y-%m', record_date)=?
    ''', (target_id, prev_month_str)).fetchone()['cnt']

    # 家事種類別：今月 vs 先月
    chore_types = db.execute('SELECT * FROM chore_types WHERE is_active=1 ORDER BY sort_order').fetchall()
    chore_comparison = []
    for ct in chore_types:
        this_cnt = db.execute('''
            SELECT COUNT(*) as cnt FROM chore_records
            WHERE user_id=? AND chore_type_id=? AND strftime('%Y-%m', record_date)=?
        ''', (target_id, ct['id'], month_str)).fetchone()['cnt']
        prev_cnt = db.execute('''
            SELECT COUNT(*) as cnt FROM chore_records
            WHERE user_id=? AND chore_type_id=? AND strftime('%Y-%m', record_date)=?
        ''', (target_id, ct['id'], prev_month_str)).fetchone()['cnt']
        if this_cnt > 0 or prev_cnt > 0:
            chore_comparison.append({
                'name': ct['name'],
                'this': this_cnt,
                'prev': prev_cnt,
                'diff': this_cnt - prev_cnt,
            })

    # 直近6ヶ月の給料推移
    monthly_history = []
    y, m = today.year, today.month
    for _ in range(6):
        sal = calc_monthly_salary(target_id, y, m)
        monthly_history.append({
            'label': f'{m}月',
            'total': sal['total'],
            'chore_pay': sal['chore_pay'],
            'academic_pay': sal.get('academic_pay', 0),
            'bonus_pay': sal.get('bonus_pay', 0),
        })
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    monthly_history.reverse()
    max_total = max((h['total'] for h in monthly_history), default=1) or 1

    # 最新学期の成績内訳
    latest_grade = db.execute('''
        SELECT year, term FROM grade_records
        WHERE user_id=? AND (eval_1 IS NOT NULL OR eval_2 IS NOT NULL OR eval_3 IS NOT NULL)
        ORDER BY year DESC, term DESC LIMIT 1
    ''', (target_id,)).fetchone()

    grade_counts = {'◎': 0, '〇': 0, '△': 0}
    grade_label = None
    if latest_grade:
        grade_label = f'{latest_grade["year"]}年{latest_grade["term"]}学期'
        records = db.execute('''
            SELECT eval_1, eval_2, eval_3 FROM grade_records
            WHERE user_id=? AND year=? AND term=?
        ''', (target_id, latest_grade['year'], latest_grade['term'])).fetchall()
        for r in records:
            for v in [r['eval_1'], r['eval_2'], r['eval_3']]:
                if v in grade_counts:
                    grade_counts[v] += 1

    children = get_family_children(db) if current_user.is_parent else None

    return render_template('stats/index.html',
                           target_user=target_user,
                           target_id=target_id,
                           children=children,
                           today=today,
                           total_chore_count=total_chore_count,
                           total_chore_pay=total_chore_pay,
                           test_bonus_count=test_bonus_count,
                           test_bonus_total=test_bonus_total,
                           chore_days_this_month=chore_days_this_month,
                           chore_days_prev_month=chore_days_prev_month,
                           prev_month=prev_m,
                           chore_comparison=chore_comparison,
                           monthly_history=monthly_history,
                           max_total=max_total,
                           grade_counts=grade_counts,
                           grade_label=grade_label)

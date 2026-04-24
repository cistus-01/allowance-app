from .database import get_db
from datetime import date

def get_pay_rates():
    db = get_db()
    rates = db.execute('SELECT key, value FROM pay_rates').fetchall()
    return {r['key']: r['value'] for r in rates}

def calc_chore_pay(user_id, year, month):
    """その月の家事報酬を計算（分割あり）"""
    db = get_db()
    chore_types = db.execute('SELECT id, unit_price FROM chore_types WHERE is_active=1').fetchall()
    total = 0
    for chore in chore_types:
        records = db.execute('''
            SELECT record_date, COUNT(*) as checker_count
            FROM chore_records
            WHERE chore_type_id = ?
              AND strftime('%Y', record_date) = ?
              AND strftime('%m', record_date) = ?
            GROUP BY record_date
        ''', (chore['id'], str(year), f'{month:02d}')).fetchall()
        for rec in records:
            my_check = db.execute('''
                SELECT id FROM chore_records
                WHERE user_id = ? AND chore_type_id = ? AND record_date = ?
            ''', (user_id, chore['id'], rec['record_date'])).fetchone()
            if my_check:
                total += chore['unit_price'] // rec['checker_count']
    return total

def get_prev_term(year, term):
    """
    前学期の (year, term) を返す。
    成績給は「前学期の成績」が「今学期の給料」に反映される。
      1学期 → 前年3学期
      2学期 → 今年1学期
      3学期 → 今年2学期
    """
    if term == 1:
        return year - 1, 3
    else:
        return year, term - 1

def month_to_term(month):
    """月から学期を返す（日本の一般的な区分）"""
    if month <= 3:
        return 3   # 1〜3月は3学期（前年度）
    elif month <= 7:
        return 1   # 4〜7月は1学期
    elif month <= 12:
        return 2   # 8〜12月は2学期（厳密には9〜）
    return 1

def calc_academic_pay_for_month(user_id, year, month):
    """
    その月の学業給を計算。
    ・学年給：現在の学年 × 倍率（毎月固定）
    ・成績給：「前学期」の成績を参照
    """
    db = get_db()
    rates = get_pay_rates()

    user = db.execute('SELECT grade FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or not user['grade']:
        return 0, 0, 0

    grade_pay = user['grade'] * rates.get('grade_pay_multiplier', 50)

    # 今月が何学期か → 前学期を求める
    current_term = month_to_term(month)
    prev_year, prev_term = get_prev_term(year, current_term)

    eval_map = {
        '◎': rates.get('eval_excellent', 150),
        '〇': rates.get('eval_good', 20),
        '△': rates.get('eval_poor', 0),
    }

    records = db.execute('''
        SELECT eval_1, eval_2, eval_3 FROM grade_records
        WHERE user_id = ? AND year = ? AND term = ?
    ''', (user_id, prev_year, prev_term)).fetchall()

    academic_pay = 0
    for rec in records:
        for eval_val in [rec['eval_1'], rec['eval_2'], rec['eval_3']]:
            if eval_val:
                academic_pay += eval_map.get(eval_val, 0)

    return grade_pay, academic_pay, grade_pay + academic_pay

def calc_academic_pay(user_id, year):
    """後方互換用（年単位の学業給合計）"""
    db = get_db()
    rates = get_pay_rates()
    user = db.execute('SELECT grade FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or not user['grade']:
        return 0, 0, 0
    grade_pay = user['grade'] * rates.get('grade_pay_multiplier', 50)
    eval_map = {
        '◎': rates.get('eval_excellent', 150),
        '〇': rates.get('eval_good', 20),
        '△': rates.get('eval_poor', 0),
    }
    records = db.execute('''
        SELECT eval_1, eval_2, eval_3 FROM grade_records
        WHERE user_id = ? AND year = ?
    ''', (user_id, year)).fetchall()
    academic_pay = 0
    for rec in records:
        for eval_val in [rec['eval_1'], rec['eval_2'], rec['eval_3']]:
            if eval_val:
                academic_pay += eval_map.get(eval_val, 0)
    return grade_pay, academic_pay, grade_pay + academic_pay

def calc_test_bonus(user_id, year, month):
    """テスト満点ボーナスを計算。記録した前月分が今月の給料に反映される。"""
    db = get_db()
    # 前月を計算
    if month == 1:
        ref_year, ref_month = year - 1, 12
    else:
        ref_year, ref_month = year, month - 1
    month_str = f'{ref_year}-{ref_month:02d}'
    rows = db.execute('''
        SELECT item, SUM(amount) as total
        FROM finance_records
        WHERE user_id=? AND category='test_bonus'
          AND strftime('%Y-%m', record_date)=?
        GROUP BY item
    ''', (user_id, month_str)).fetchall()
    total = sum(r['total'] for r in rows)
    subjects = [r['item'] for r in rows if r['item']]
    return total, len(subjects), subjects

def calc_monthly_salary(user_id, year, month):
    """月次給与の全項目を計算"""
    rates = get_pay_rates()
    base_pay = rates.get('base_pay', 100)
    grade_pay, academic_pay, total_academic = calc_academic_pay_for_month(user_id, year, month)
    chore_pay = calc_chore_pay(user_id, year, month)
    bonus_pay, bonus_cnt, bonus_subjects = calc_test_bonus(user_id, year, month)
    total = base_pay + total_academic + chore_pay + bonus_pay
    return {
        'base_pay': base_pay,
        'grade_pay': grade_pay,
        'academic_pay': academic_pay,
        'chore_pay': chore_pay,
        'bonus_pay': bonus_pay,
        'bonus_cnt': bonus_cnt,
        'bonus_subjects': bonus_subjects,
        'total': total
    }

def calc_balance(user_id):
    db = get_db()
    income = db.execute('''
        SELECT COALESCE(SUM(amount), 0) as total FROM finance_records
        WHERE user_id = ? AND type = 'income'
    ''', (user_id,)).fetchone()['total']
    expense = db.execute('''
        SELECT COALESCE(SUM(amount), 0) as total FROM finance_records
        WHERE user_id = ? AND type = 'expense'
    ''', (user_id,)).fetchone()['total']
    return income - expense

def get_monthly_finance_summary(user_id, year, month):
    db = get_db()
    month_str = f'{year}-{month:02d}'
    income = db.execute('''
        SELECT COALESCE(SUM(amount), 0) as total FROM finance_records
        WHERE user_id = ? AND strftime('%Y-%m', record_date) = ? AND type = 'income'
    ''', (user_id, month_str)).fetchone()['total']
    expense = db.execute('''
        SELECT COALESCE(SUM(amount), 0) as total FROM finance_records
        WHERE user_id = ? AND strftime('%Y-%m', record_date) = ? AND type = 'expense'
    ''', (user_id, month_str)).fetchone()['total']
    return {'income': income, 'expense': expense}

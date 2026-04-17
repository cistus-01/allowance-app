"""
デモデータ投入スクリプト
python seed_demo.py で実行
"""
from app import create_app
from app.database import get_db
from werkzeug.security import generate_password_hash
from datetime import date, timedelta
import random

app = create_app()

with app.app_context():
    db = get_db()

    # 既存データチェック
    existing = db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    if existing > 0:
        print("⚠️  データが既に存在します。seed_demo.py は空のDBにのみ使用してください。")
        exit(1)

    # 親アカウント
    db.execute("""
        INSERT INTO users (name, username, password_hash, role)
        VALUES (?, ?, ?, 'parent')
    """, ('お父さん', 'parent', generate_password_hash('demo1234')))

    # 子どもアカウント
    db.execute("""
        INSERT INTO users (name, username, password_hash, role, grade)
        VALUES (?, ?, ?, 'child', ?)
    """, ('たろう', 'taro', generate_password_hash('taro1234'), 4))

    db.execute("""
        INSERT INTO users (name, username, password_hash, role, grade)
        VALUES (?, ?, ?, 'child', ?)
    """, ('はなこ', 'hanako', generate_password_hash('hanako1234'), 2))

    db.commit()

    taro_id = db.execute("SELECT id FROM users WHERE username='taro'").fetchone()['id']
    hanako_id = db.execute("SELECT id FROM users WHERE username='hanako'").fetchone()['id']
    parent_id = db.execute("SELECT id FROM users WHERE username='parent'").fetchone()['id']

    # 給与単価
    rates = [
        ('base_pay', 100, '基本給'),
        ('grade_pay_multiplier', 50, '学年給（学年×この金額）'),
        ('eval_excellent', 150, '成績◎'),
        ('eval_good', 20, '成績〇'),
        ('eval_poor', 0, '成績△'),
    ]
    for key, val, label in rates:
        db.execute("INSERT OR IGNORE INTO pay_rates (key, value, label) VALUES (?,?,?)", (key, val, label))

    # 家事の種類
    chores = [
        ('お皿洗い', 50, 1),
        ('掃除機がけ', 80, 2),
        ('洗濯物たたみ', 30, 3),
        ('ゴミ出し', 60, 4),
        ('風呂掃除', 70, 5),
    ]
    for name, price, order in chores:
        db.execute("INSERT OR IGNORE INTO chore_types (name, unit_price, sort_order) VALUES (?,?,?)",
                   (name, price, order))
    db.commit()

    chore_rows = db.execute("SELECT id FROM chore_types").fetchall()
    chore_ids = [r['id'] for r in chore_rows]

    # 今月の家事記録（過去20日分をランダムに）
    today = date.today()
    for days_ago in range(20, 0, -1):
        record_date = today - timedelta(days=days_ago)
        for chore_id in chore_ids:
            if random.random() < 0.5:
                try:
                    db.execute("""
                        INSERT INTO chore_records (user_id, chore_type_id, record_date, checked_by)
                        VALUES (?, ?, ?, ?)
                    """, (taro_id, chore_id, record_date.isoformat(), parent_id))
                except Exception:
                    pass
            if random.random() < 0.4:
                try:
                    db.execute("""
                        INSERT INTO chore_records (user_id, chore_type_id, record_date, checked_by)
                        VALUES (?, ?, ?, ?)
                    """, (hanako_id, chore_id, record_date.isoformat(), parent_id))
                except Exception:
                    pass

    # 教科
    subjects = ['国語', '算数', '理科', '社会', '体育', '音楽', '図工']
    for i, name in enumerate(subjects):
        db.execute("INSERT OR IGNORE INTO subjects (name, sort_order) VALUES (?,?)", (name, i))
    db.commit()

    subject_rows = db.execute("SELECT id FROM subjects").fetchall()
    subject_ids = [r['id'] for r in subject_rows]

    # 成績記録（前学期）
    evals = ['◎', '〇', '△']
    for subject_id in subject_ids:
        eval_val = random.choice(evals)
        try:
            db.execute("""
                INSERT OR IGNORE INTO grade_records (user_id, subject_id, year, term, eval_1, entered_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (taro_id, subject_id, today.year, 1, eval_val, parent_id))
        except Exception:
            pass

    # 収支記録
    income_items = [('おこづかい', 1000), ('お年玉', 500), ('お手伝い特別', 200)]
    expense_items = [('ガチャ', 200), ('お菓子', 150), ('文房具', 300)]
    for days_ago in [15, 10, 5]:
        rec_date = (today - timedelta(days=days_ago)).isoformat()
        cat, amt = random.choice(income_items)
        db.execute("""
            INSERT INTO finance_records (user_id, record_date, type, category, amount, created_by)
            VALUES (?, ?, 'income', ?, ?, ?)
        """, (taro_id, rec_date, cat, amt, parent_id))
        cat, amt = random.choice(expense_items)
        db.execute("""
            INSERT INTO finance_records (user_id, record_date, type, category, amount, created_by)
            VALUES (?, ?, 'expense', ?, ?, ?)
        """, (taro_id, rec_date, cat, amt, parent_id))

    # ほしいものリスト
    db.execute("""
        INSERT INTO goals (user_id, name, target_amount, emoji)
        VALUES (?, ?, ?, ?)
    """, (taro_id, 'ポケモンカードパック', 3000, '🎮'))
    db.execute("""
        INSERT INTO goals (user_id, name, target_amount, emoji)
        VALUES (?, ?, ?, ?)
    """, (taro_id, '新しい色鉛筆セット', 1500, '🎨'))
    db.execute("""
        INSERT INTO goals (user_id, name, target_amount, emoji)
        VALUES (?, ?, ?, ?)
    """, (hanako_id, 'かわいい消しゴムセット', 800, '🌈'))

    db.commit()
    print("✅ デモデータを投入しました")
    print()
    print("【ログイン情報】")
    print("  親アカウント: parent / demo1234")
    print("  たろう（4年生）: taro / taro1234")
    print("  はなこ（2年生）: hanako / hanako1234")

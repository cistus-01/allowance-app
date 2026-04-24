import sqlite3
import os
from flask import g, current_app

DATABASE = os.environ.get('DATABASE_PATH', '/data/allowance.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')

    # テーブル作成（CREATE TABLE IF NOT EXISTSなので冪等）
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()

    # 初期データは各テーブルが空の時だけ挿入
    _seed_if_empty(db)

    # 列がなければ追加（既存DB対応）
    cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    if 'family_id' not in cols:
        db.execute("ALTER TABLE users ADD COLUMN family_id INTEGER")
    if 'email' not in cols:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT")

    # パスワードリセットトークンテーブル
    db.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at DATETIME NOT NULL,
            used_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 設定プリセットテーブル
    db.execute('''
        CREATE TABLE IF NOT EXISTS config_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            slot INTEGER NOT NULL CHECK(slot IN (1, 2, 3)),
            label TEXT DEFAULT '',
            pay_rates_json TEXT NOT NULL DEFAULT '{}',
            subjects_json TEXT NOT NULL DEFAULT '[]',
            chore_types_json TEXT NOT NULL DEFAULT '[]',
            saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(family_id, slot)
        )
    ''')
    db.commit()

    db.close()
    current_app.teardown_appcontext(close_db)

def _seed_if_empty(db):
    """初期マスタデータを空の時だけ投入する。既にデータがあれば何もしない。"""

    # 家事
    if db.execute("SELECT COUNT(*) FROM chore_types").fetchone()[0] == 0:
        db.executemany(
            "INSERT OR IGNORE INTO chore_types (name, unit_price, sort_order) VALUES (?, ?, ?)",
            [('掃除', 30, 1), ('洗濯', 10, 2), ('干す', 30, 3), ('洗い物', 20, 4), ('しまう', 10, 5)]
        )

    # 教科
    if db.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0:
        db.executemany(
            "INSERT OR IGNORE INTO subjects (name, sort_order) VALUES (?, ?)",
            [('国語',1),('算数',2),('理科',3),('社会',4),('英語',5),
             ('音楽',6),('体育',7),('図工',8),('道徳',9)]
        )
        # 全学年に割り当て
        subjects = db.execute("SELECT id FROM subjects").fetchall()
        for grade in range(1, 7):
            for s in subjects:
                db.execute(
                    "INSERT OR IGNORE INTO grade_subjects (grade, subject_id) VALUES (?, ?)",
                    (grade, s['id'])
                )

    # 単価
    if db.execute("SELECT COUNT(*) FROM pay_rates").fetchone()[0] == 0:
        db.executemany(
            "INSERT OR IGNORE INTO pay_rates (key, value, label) VALUES (?, ?, ?)",
            [('base_pay', 100, '基本給'),
             ('grade_pay_multiplier', 50, '学年給（学年×）'),
             ('eval_excellent', 150, '成績給◎'),
             ('eval_good', 20, '成績給〇'),
             ('eval_poor', 0, '成績給△'),
             ]
        )

    db.commit()

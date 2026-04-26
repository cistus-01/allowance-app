import os
import sqlite3
from flask import g, current_app

DATABASE_URL = os.environ.get('DATABASE_URL')
DATABASE     = os.environ.get('DATABASE_PATH', '/data/allowance.db')

USE_PG = bool(DATABASE_URL)
_pg_available = False
_pg_pool = None   # ThreadedConnectionPool（起動時に1回だけ作成）


# ---- 接続取得 ----

def get_db():
    if 'db' not in g:
        if _pg_available and _pg_pool:
            from .db_compat import ConnWrapper
            conn = _pg_pool.getconn()
            conn.autocommit = False
            g.db = ConnWrapper(conn)
            g._pg_conn = conn   # close_db で返却するために保持
        else:
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys = ON')
            g.db = conn
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        if _pg_pool and hasattr(g, '_pg_conn'):
            try:
                g._pg_conn.rollback()   # 未コミットをロールバック
                _pg_pool.putconn(g._pg_conn)
            except Exception:
                pass
            g.pop('_pg_conn', None)
        else:
            db.close()


# ---- 初期化 ----

def init_db():
    global _pg_available, _pg_pool
    if USE_PG:
        try:
            import psycopg2.pool
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5, dsn=DATABASE_URL, connect_timeout=10
            )
            _init_pg()
            _pg_available = True
            print('[DB] PostgreSQL 接続OK（接続プール確立）', flush=True)
        except Exception as e:
            print(f'[DB] PostgreSQL 接続失敗: {e}', flush=True)
            print('[DB] SQLite フォールバックで起動します', flush=True)
            _pg_available = False
            _pg_pool = None
            _init_sqlite()
    else:
        _pg_available = False
        _init_sqlite()
    current_app.teardown_appcontext(close_db)


def _init_pg():
    from .db_compat import ConnWrapper
    conn = _pg_pool.getconn()
    conn.autocommit = False
    db = ConnWrapper(conn)

    schema_path = os.path.join(os.path.dirname(__file__), 'schema_pg.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.executescript(f.read())

    _seed_if_empty(db)

    # オーナー永久無料
    db.execute("""
        UPDATE families SET is_lifetime_free=1
        WHERE id=(SELECT family_id FROM users WHERE username='akkun0420')
    """)
    # eval 単価修正
    db.execute("UPDATE pay_rates SET value=50 WHERE key='eval_excellent' AND value!=50")
    db.execute("UPDATE pay_rates SET value=15 WHERE key='eval_good' AND value!=15")

    db.commit()
    _pg_pool.putconn(conn)


def _init_sqlite():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')

    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()

    _seed_if_empty(db)

    # 列追加（既存DB対応）
    for col, ddl in [('family_id', 'INTEGER'), ('email', 'TEXT'), ('tutorial_done', 'INTEGER DEFAULT 0')]:
        cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
        if col not in cols:
            db.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")

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

    gip_cols = [r[1] for r in db.execute("PRAGMA table_info(grade_input_periods)").fetchall()]
    if 'family_id' not in gip_cols:
        db.execute("ALTER TABLE grade_input_periods ADD COLUMN family_id INTEGER")

    db.execute('''
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            condition TEXT,
            reward_amount INTEGER NOT NULL,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'done', 'cancelled')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (family_id) REFERENCES families(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    fam_cols = [r[1] for r in db.execute("PRAGMA table_info(families)").fetchall()]
    if 'scheduled_delete_at' not in fam_cols:
        db.execute("ALTER TABLE families ADD COLUMN scheduled_delete_at DATETIME")
    if 'is_lifetime_free' not in fam_cols:
        db.execute("ALTER TABLE families ADD COLUMN is_lifetime_free INTEGER DEFAULT 0")

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

    db.execute("""
        UPDATE families SET is_lifetime_free=1
        WHERE id=(SELECT family_id FROM users WHERE username='akkun0420')
    """)
    db.execute("UPDATE pay_rates SET value=50 WHERE key='eval_excellent' AND value!=50")
    db.execute("UPDATE pay_rates SET value=15 WHERE key='eval_good' AND value!=15")

    db.commit()
    db.close()


# ---- シードデータ ----

def _seed_if_empty(db):
    if db.execute("SELECT COUNT(*) FROM chore_types").fetchone()[0] == 0:
        db.executemany(
            "INSERT OR IGNORE INTO chore_types (name, unit_price, sort_order) VALUES (?, ?, ?)",
            [('掃除', 30, 1), ('洗濯', 10, 2), ('干す', 30, 3), ('洗い物', 20, 4), ('しまう', 10, 5)]
        )

    if db.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0:
        db.executemany(
            "INSERT OR IGNORE INTO subjects (name, sort_order) VALUES (?, ?)",
            [('国語',1),('算数',2),('理科',3),('社会',4),('英語',5),
             ('音楽',6),('体育',7),('図工',8),('道徳',9)]
        )
        subjects = db.execute("SELECT id FROM subjects").fetchall()
        for grade in range(1, 7):
            for s in subjects:
                db.execute(
                    "INSERT OR IGNORE INTO grade_subjects (grade, subject_id) VALUES (?, ?)",
                    (grade, s['id'])
                )

    if db.execute("SELECT COUNT(*) FROM pay_rates").fetchone()[0] == 0:
        db.executemany(
            "INSERT OR IGNORE INTO pay_rates (key, value, label) VALUES (?, ?, ?)",
            [('base_pay', 100, '基本給'),
             ('grade_pay_multiplier', 50, '学年給（学年×）'),
             ('eval_excellent', 50, '成績給◎'),
             ('eval_good', 15, '成績給〇'),
             ('eval_poor', 0, '成績給△'),
             ]
        )

    db.commit()

"""
ローカル SQLite → Supabase PostgreSQL データ移行スクリプト

使い方:
  DATABASE_URL="postgresql://..." python3 migrate_to_pg.py

実行前に:
  pip install psycopg2-binary
"""

import os
import sys
import sqlite3
import psycopg2
import psycopg2.extras

SQLITE_PATH = os.environ.get('DATABASE_PATH', '/data/allowance.db')
PG_URL      = os.environ.get('DATABASE_URL')

if not PG_URL:
    sys.exit("ERROR: DATABASE_URL 環境変数が未設定")

# テーブルごとの移行設定（順番はFK制約に合わせる）
TABLES = [
    'users',
    'families',
    'chore_types',
    'chore_records',
    'subjects',
    'grade_subjects',
    'grade_records',
    'grade_input_periods',
    'finance_records',
    'salary_payments',
    'goals',
    'pay_rates',
    'password_reset_tokens',
    'bonus_records',
    'config_presets',
    'challenges',
]

def migrate():
    print(f"SQLite: {SQLITE_PATH}")
    print(f"PG    : {PG_URL[:40]}...")

    src = sqlite3.connect(SQLITE_PATH)
    src.row_factory = sqlite3.Row

    dst = psycopg2.connect(PG_URL)
    dst.autocommit = False
    cur = dst.cursor()

    for table in TABLES:
        # テーブルの存在確認
        exists = src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            print(f"  skip {table} (not in SQLite)")
            continue

        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  skip {table} (empty)")
            continue

        keys = rows[0].keys()
        # PostgreSQL側にある列だけに絞る
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name=%s AND table_schema='public'
        """, (table,))
        pg_cols = {r[0] for r in cur.fetchall()}
        keys = [k for k in keys if k in pg_cols]

        placeholders = ', '.join(['%s'] * len(keys))
        cols_str = ', '.join(keys)
        sql = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        data = [tuple(row[k] for k in keys) for row in rows]
        psycopg2.extras.execute_batch(cur, sql, data)
        print(f"  {table}: {len(data)} rows")

    # SERIAL シーケンスをリセット（idの最大値に合わせる）
    for table in TABLES:
        try:
            cur.execute(f"SELECT MAX(id) FROM {table}")
            max_id = cur.fetchone()[0]
            if max_id:
                cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), %s)", (max_id,))
        except Exception:
            dst.rollback()

    dst.commit()
    print("\n移行完了！")
    src.close()
    dst.close()


if __name__ == '__main__':
    migrate()

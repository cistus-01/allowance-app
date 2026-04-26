"""psycopg2 を sqlite3 と同じインターフェースで使うための互換レイヤー"""
import re
import datetime as _dt
import decimal as _decimal


def _normalize(v):
    """psycopg2が返すPythonオブジェクトをsqlite3互換の型に変換"""
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        return int(v)
    return v


class Row:
    """sqlite3.Row 互換: row['key'] も row[0] も使える"""
    def __init__(self, keys, values):
        self._keys = keys
        self._values = [_normalize(v) for v in values]
        self._dict = dict(zip(keys, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def __iter__(self):
        return iter(self._values)

    def keys(self):
        return self._keys

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def __repr__(self):
        return f"Row({self._dict})"


class CursorWrapper:
    def __init__(self, cur):
        self._cur = cur

    def _make_row(self, raw):
        if raw is None:
            return None
        keys = [d[0] for d in self._cur.description]
        return Row(keys, list(raw))

    def fetchone(self):
        return self._make_row(self._cur.fetchone())

    def fetchall(self):
        if self._cur.description is None:
            return []
        rows = self._cur.fetchall()
        keys = [d[0] for d in self._cur.description]
        return [Row(keys, list(r)) for r in rows]

    def __iter__(self):
        keys = [d[0] for d in self._cur.description]
        for row in self._cur:
            yield Row(keys, list(row))


class ConnWrapper:
    """psycopg2 接続を sqlite3 接続風に使えるラッパー"""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        sql, params = _adapt(sql, params)
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return CursorWrapper(cur)

    def executemany(self, sql, params_list):
        import psycopg2.extras
        sql, _ = _adapt(sql, None)
        cur = self._conn.cursor()
        psycopg2.extras.execute_batch(cur, sql, list(params_list))
        return CursorWrapper(cur)

    def executescript(self, sql):
        """複数SQL文を順番に実行（schema適用用）"""
        cur = self._conn.cursor()
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(_pg_schema(stmt))
                    self._conn.commit()
                except Exception:
                    self._conn.rollback()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ---- SQL 変換 ----

def _adapt(sql, params):
    """SQLite 方言 → PostgreSQL 方言に変換"""
    sql = sql.replace('?', '%s')

    if re.search(r'INSERT\s+OR\s+IGNORE\s+INTO', sql, re.IGNORECASE):
        sql = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql, flags=re.IGNORECASE)
        sql = sql.rstrip('; \t\n') + ' ON CONFLICT DO NOTHING'

    sql = re.sub(r'last_insert_rowid\s*\(\s*\)', 'lastval()', sql, flags=re.IGNORECASE)
    sql = re.sub(r"datetime\s*\(\s*'now'\s*\)", 'NOW()', sql, flags=re.IGNORECASE)
    sql = re.sub(r"date\s*\(\s*'now'\s*\)", 'CURRENT_DATE', sql, flags=re.IGNORECASE)

    # strftime → TO_CHAR（長い形式を先に変換）
    sql = re.sub(r"strftime\s*\(\s*'%Y-%m-%d'\s*,\s*([\w.]+)\s*\)", r"TO_CHAR(\1, 'YYYY-MM-DD')", sql, flags=re.IGNORECASE)
    sql = re.sub(r"strftime\s*\(\s*'%Y-%m'\s*,\s*([\w.]+)\s*\)",    r"TO_CHAR(\1, 'YYYY-MM')",    sql, flags=re.IGNORECASE)
    sql = re.sub(r"strftime\s*\(\s*'%Y'\s*,\s*([\w.]+)\s*\)",        r"TO_CHAR(\1, 'YYYY')",       sql, flags=re.IGNORECASE)
    sql = re.sub(r"strftime\s*\(\s*'%m'\s*,\s*([\w.]+)\s*\)",        r"TO_CHAR(\1, 'MM')",         sql, flags=re.IGNORECASE)

    return sql, params


def _pg_schema(stmt):
    """schema.sql をそのまま PostgreSQL 用に変換する（schema適用時のみ使用）"""
    stmt = re.sub(r'INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY', stmt, flags=re.IGNORECASE)
    stmt = re.sub(r'\bDATETIME\b', 'TIMESTAMP', stmt, flags=re.IGNORECASE)
    return stmt

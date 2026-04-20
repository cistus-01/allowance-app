-- ユーザーテーブル
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('parent', 'child')),
    grade INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 家事定義テーブル（nameにUNIQUE制約を追加）
CREATE TABLE IF NOT EXISTS chore_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    unit_price INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

-- 家事チェック記録テーブル
CREATE TABLE IF NOT EXISTS chore_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chore_type_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    checked_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (chore_type_id) REFERENCES chore_types(id),
    UNIQUE(user_id, chore_type_id, record_date)
);

-- 教科テーブル（nameにUNIQUE制約を追加）
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

-- 学年別教科設定テーブル
CREATE TABLE IF NOT EXISTS grade_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grade INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    UNIQUE(grade, subject_id)
);

-- 成績記録テーブル
CREATE TABLE IF NOT EXISTS grade_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    term INTEGER NOT NULL CHECK(term IN (1, 2, 3)),
    eval_1 TEXT CHECK(eval_1 IN ('◎', '〇', '△', NULL)),
    eval_2 TEXT CHECK(eval_2 IN ('◎', '〇', '△', NULL)),
    eval_3 TEXT CHECK(eval_3 IN ('◎', '〇', '△', NULL)),
    entered_by INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    UNIQUE(user_id, subject_id, year, term)
);

-- 成績入力開放設定テーブル
CREATE TABLE IF NOT EXISTS grade_input_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    term INTEGER NOT NULL CHECK(term IN (1, 2, 3)),
    is_open BOOLEAN DEFAULT 0,
    opened_at DATETIME,
    closed_at DATETIME,
    UNIQUE(year, term)
);

-- 収支記録テーブル
CREATE TABLE IF NOT EXISTS finance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    category TEXT NOT NULL,
    shop TEXT,
    item TEXT,
    amount INTEGER NOT NULL,
    note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 給与支払い記録テーブル
CREATE TABLE IF NOT EXISTS salary_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    base_pay INTEGER DEFAULT 100,
    grade_pay INTEGER DEFAULT 0,
    academic_pay INTEGER DEFAULT 0,
    chore_pay INTEGER DEFAULT 0,
    total_pay INTEGER DEFAULT 0,
    paid_at DATETIME,
    paid_by INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, year, month)
);

-- ほしいものリスト（目標貯金）テーブル
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    target_amount INTEGER NOT NULL,
    emoji TEXT DEFAULT '🎯',
    is_achieved BOOLEAN DEFAULT 0,
    achieved_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 給与単価設定テーブル
CREATE TABLE IF NOT EXISTS pay_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value INTEGER NOT NULL,
    label TEXT NOT NULL
);

-- ファミリー（課金単位）テーブル
CREATE TABLE IF NOT EXISTS families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT DEFAULT 'trial',
    trial_ends_at DATETIME,
    plan_ends_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

-- users テーブルにfamily_id列を追加（ALTER TABLE - 既存DB対応）
-- CREATE TABLE側には含めず、init_db()でALTERする

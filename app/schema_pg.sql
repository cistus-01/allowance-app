-- PostgreSQL schema for こどもの給与帳
-- すべての列を含む完全版（ALTER TABLEで追加したものも含む）

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('parent', 'child')),
    grade INTEGER,
    family_id INTEGER,
    tutorial_done INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS families (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT DEFAULT 'trial',
    trial_ends_at TIMESTAMP,
    plan_ends_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_delete_at TIMESTAMP,
    is_lifetime_free INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chore_types (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    unit_price INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chore_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    chore_type_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checked_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (chore_type_id) REFERENCES chore_types(id),
    UNIQUE(user_id, chore_type_id, record_date)
);

CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS grade_subjects (
    id SERIAL PRIMARY KEY,
    grade INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    UNIQUE(grade, subject_id)
);

CREATE TABLE IF NOT EXISTS grade_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    term INTEGER NOT NULL CHECK(term IN (1, 2, 3)),
    eval_1 TEXT CHECK(eval_1 IN ('◎', '〇', '△')),
    eval_2 TEXT CHECK(eval_2 IN ('◎', '〇', '△')),
    eval_3 TEXT CHECK(eval_3 IN ('◎', '〇', '△')),
    entered_by INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    UNIQUE(user_id, subject_id, year, term)
);

CREATE TABLE IF NOT EXISTS grade_input_periods (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    term INTEGER NOT NULL CHECK(term IN (1, 2, 3)),
    is_open INTEGER DEFAULT 0,
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    family_id INTEGER,
    UNIQUE(year, term)
);

CREATE TABLE IF NOT EXISTS finance_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    category TEXT NOT NULL,
    shop TEXT,
    item TEXT,
    amount INTEGER NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS salary_payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    base_pay INTEGER DEFAULT 100,
    grade_pay INTEGER DEFAULT 0,
    academic_pay INTEGER DEFAULT 0,
    chore_pay INTEGER DEFAULT 0,
    total_pay INTEGER DEFAULT 0,
    paid_at TIMESTAMP,
    paid_by INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, year, month)
);

CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    target_amount INTEGER NOT NULL,
    emoji TEXT DEFAULT '🎯',
    is_achieved INTEGER DEFAULT 0,
    achieved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS pay_rates (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value INTEGER NOT NULL,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS bonus_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    family_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    item TEXT,
    amount INTEGER NOT NULL,
    target_month INTEGER,
    target_year INTEGER,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS config_presets (
    id SERIAL PRIMARY KEY,
    family_id INTEGER NOT NULL,
    slot INTEGER NOT NULL CHECK(slot IN (1, 2, 3)),
    label TEXT DEFAULT '',
    pay_rates_json TEXT NOT NULL DEFAULT '{}',
    subjects_json TEXT NOT NULL DEFAULT '[]',
    chore_types_json TEXT NOT NULL DEFAULT '[]',
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(family_id, slot)
);

CREATE TABLE IF NOT EXISTS challenges (
    id SERIAL PRIMARY KEY,
    family_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    condition TEXT,
    reward_amount INTEGER NOT NULL,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'done', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

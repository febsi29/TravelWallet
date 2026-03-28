
-- PART 1: Users & Trips

CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    base_currency TEXT DEFAULT 'TWD',
    line_user_id  TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    trip_name     TEXT NOT NULL,
    destination   TEXT NOT NULL,
    currency_code TEXT NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    total_budget  REAL,
    status        TEXT DEFAULT 'planning',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS trip_members (
    trip_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    nickname  TEXT,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trip_id, user_id),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PART 2: Transactions

CREATE TABLE IF NOT EXISTS categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE,
    icon          TEXT,
    color_hex     TEXT
);

INSERT OR IGNORE INTO categories (category_name, icon, color_hex) VALUES
    ('餐飲', '🍜', '#FF6B6B'),
    ('交通', '🚃', '#4ECDC4'),
    ('住宿', '🏨', '#45B7D1'),
    ('購物', '🛍️', '#96CEB4'),
    ('娛樂', '🎮', '#FFEAA7'),
    ('其他', '📦', '#DFE6E9');

CREATE TABLE IF NOT EXISTS transactions (
    txn_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id         INTEGER NOT NULL,
    paid_by         INTEGER NOT NULL,
    amount          REAL NOT NULL,
    currency_code   TEXT NOT NULL,
    amount_twd      REAL NOT NULL,
    exchange_rate   REAL NOT NULL,
    category        TEXT NOT NULL,
    subcategory     TEXT,
    description     TEXT,
    payment_method  TEXT DEFAULT 'cash',
    txn_datetime    DATETIME NOT NULL,
    location        TEXT,
    split_type      TEXT DEFAULT 'none',
    is_anomaly      BOOLEAN DEFAULT 0,
    anomaly_score   REAL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    FOREIGN KEY (paid_by) REFERENCES users(user_id)
);

-- PART 3: Split Bill

CREATE TABLE IF NOT EXISTS split_details (
    split_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id        INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    share_amount  REAL NOT NULL,
    share_twd     REAL NOT NULL,
    share_ratio   REAL,
    is_settled    BOOLEAN DEFAULT 0,
    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id         INTEGER NOT NULL,
    from_user       INTEGER NOT NULL,
    to_user         INTEGER NOT NULL,
    amount          REAL NOT NULL,
    currency_code   TEXT NOT NULL,
    amount_twd      REAL NOT NULL,
    exchange_rate   REAL NOT NULL,
    status          TEXT DEFAULT 'pending',
    settled_at      DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    FOREIGN KEY (from_user) REFERENCES users(user_id),
    FOREIGN KEY (to_user) REFERENCES users(user_id)
);

-- PART 4: Exchange Rates

CREATE TABLE IF NOT EXISTS exchange_rates (
    rate_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency   TEXT NOT NULL DEFAULT 'TWD',
    target_currency TEXT NOT NULL,
    rate            REAL NOT NULL,
    recorded_date   DATE NOT NULL,
    source          TEXT DEFAULT 'ExchangeRate-API',
    UNIQUE(base_currency, target_currency, recorded_date)
);

-- PART 5: Government Open Data

CREATE TABLE IF NOT EXISTS gov_outbound_stats (
    stat_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    year                    INTEGER NOT NULL UNIQUE,
    total_outbound_trips    INTEGER,
    avg_stay_nights         REAL,
    avg_spending_twd        REAL,
    avg_spending_usd        REAL,
    total_spending_twd_100m REAL,
    total_spending_usd_100m REAL
);

-- PART 6: Budget Tracking

CREATE TABLE IF NOT EXISTS daily_budget_summary (
    summary_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id          INTEGER NOT NULL,
    summary_date     DATE NOT NULL,
    total_spent      REAL NOT NULL DEFAULT 0,
    budget_remaining REAL,
    daily_avg        REAL,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    UNIQUE(trip_id, summary_date)
);

-- PART 7: Trip Planning

CREATE TABLE IF NOT EXISTS trip_plans (
    plan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    destination       TEXT NOT NULL,
    currency_code     TEXT NOT NULL,
    planned_days      INTEGER NOT NULL,
    num_travelers     INTEGER DEFAULT 1,
    suggested_budget  REAL,
    user_budget       REAL,
    budget_breakdown  TEXT,
    data_source       TEXT DEFAULT 'gov_stats',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PART 8: Credit Score (Nice to Have)

CREATE TABLE IF NOT EXISTS credit_scores (
    score_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    trip_id         INTEGER,
    overall_score   INTEGER NOT NULL,
    budget_score    INTEGER,
    anomaly_score   INTEGER,
    settle_score    INTEGER,
    category_score  INTEGER,
    evaluated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);

-- PART 9: Rate Alerts (匯率到價提醒)

CREATE TABLE IF NOT EXISTS rate_alerts (
    alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    base_currency   TEXT NOT NULL DEFAULT 'TWD',
    target_currency TEXT NOT NULL,
    target_rate     REAL NOT NULL,
    direction       TEXT NOT NULL DEFAULT 'above',
    current_rate    REAL,
    is_triggered    BOOLEAN DEFAULT 0,
    triggered_at    DATETIME,
    is_active       BOOLEAN DEFAULT 1,
    note            TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PART 10: Virtual Wallet (多幣別電子錢包)

CREATE TABLE IF NOT EXISTS wallets (
    wallet_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    currency_code   TEXT NOT NULL,
    balance         REAL NOT NULL DEFAULT 0,
    locked_balance  REAL NOT NULL DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, currency_code),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    wtxn_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id       INTEGER NOT NULL,
    txn_type        TEXT NOT NULL,
    amount          REAL NOT NULL,
    currency_code   TEXT NOT NULL,
    related_wtxn_id INTEGER,
    exchange_rate   REAL,
    locked_rate     REAL,
    note            TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallets(wallet_id)
);

-- PART 11: Spending Alerts (智慧提醒)

CREATE TABLE IF NOT EXISTS spending_alerts (
    alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id         INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    alert_type      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'info',
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    is_read         BOOLEAN DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PART 12: Risk Assessment (風險評估)

CREATE TABLE IF NOT EXISTS risk_assessments (
    assessment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    trip_id         INTEGER NOT NULL,
    overall_risk    REAL NOT NULL,
    fx_risk         REAL NOT NULL,
    budget_risk     REAL NOT NULL,
    anomaly_risk    REAL NOT NULL,
    credit_risk     REAL NOT NULL,
    health_index    TEXT NOT NULL,
    assessed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);

-- PART 13: Credit Cards & Rewards (信用卡推薦)

CREATE TABLE IF NOT EXISTS credit_cards (
    card_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name       TEXT NOT NULL,
    issuer          TEXT NOT NULL,
    card_type       TEXT NOT NULL,
    annual_fee      REAL DEFAULT 0,
    overseas_fee_pct REAL DEFAULT 1.5,
    is_active       BOOLEAN DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS card_rewards (
    reward_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         INTEGER NOT NULL,
    category        TEXT NOT NULL,
    region          TEXT DEFAULT 'all',
    reward_type     TEXT NOT NULL,
    reward_rate     REAL NOT NULL,
    reward_cap      REAL,
    min_spend       REAL DEFAULT 0,
    valid_from      DATE,
    valid_to        DATE,
    FOREIGN KEY (card_id) REFERENCES credit_cards(card_id)
);

-- PART 14: OCR Receipts (收據掃描)

CREATE TABLE IF NOT EXISTS ocr_receipts (
    receipt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    trip_id         INTEGER,
    image_path      TEXT NOT NULL,
    raw_text        TEXT,
    extracted_amount REAL,
    extracted_currency TEXT,
    extracted_merchant TEXT,
    extracted_category TEXT,
    extracted_date   TEXT,
    confidence       REAL,
    status          TEXT DEFAULT 'pending',
    linked_txn_id   INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PART 15: Community Stats (社群排行榜)

CREATE TABLE IF NOT EXISTS community_stats (
    stat_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    destination     TEXT NOT NULL,
    trip_days       INTEGER NOT NULL,
    num_travelers   INTEGER NOT NULL,
    total_spent_twd REAL NOT NULL,
    per_person_daily REAL NOT NULL,
    category_breakdown TEXT,
    user_id         INTEGER NOT NULL,
    trip_id         INTEGER NOT NULL,
    is_anonymous    BOOLEAN DEFAULT 1,
    shared_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, trip_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PART 16: Payment Links (付款整合)

CREATE TABLE IF NOT EXISTS payment_links (
    link_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id   INTEGER NOT NULL,
    provider        TEXT NOT NULL,
    payment_url     TEXT,
    qr_code_data    TEXT,
    amount          REAL NOT NULL,
    currency_code   TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    expires_at      DATETIME,
    paid_at         DATETIME,
    provider_ref    TEXT,
    from_name       TEXT,
    to_name         TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (settlement_id) REFERENCES settlements(settlement_id)
);

-- Indexes

CREATE INDEX IF NOT EXISTS idx_txn_trip ON transactions(trip_id);
CREATE INDEX IF NOT EXISTS idx_txn_paid_by ON transactions(paid_by);
CREATE INDEX IF NOT EXISTS idx_txn_datetime ON transactions(txn_datetime);
CREATE INDEX IF NOT EXISTS idx_split_txn ON split_details(txn_id);
CREATE INDEX IF NOT EXISTS idx_split_user ON split_details(user_id);
CREATE INDEX IF NOT EXISTS idx_settle_trip ON settlements(trip_id);
CREATE INDEX IF NOT EXISTS idx_fx_date ON exchange_rates(target_currency, recorded_date);

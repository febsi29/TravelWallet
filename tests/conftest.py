"""
conftest.py - 共用測試 fixtures

提供：
- db_path: 使用臨時檔案的測試資料庫路徑
- 自動建立 schema + 種子資料（users/trips/trip_members/transactions/split_details/settlements/exchange_rates）
"""

import sqlite3
import os
import pytest

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    base_currency TEXT DEFAULT 'TWD',
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
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    rate_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency   TEXT NOT NULL DEFAULT 'TWD',
    target_currency TEXT NOT NULL,
    rate            REAL NOT NULL,
    recorded_date   DATE NOT NULL,
    source          TEXT DEFAULT 'ExchangeRate-API',
    UNIQUE(base_currency, target_currency, recorded_date)
);

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
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

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
"""

SEED_SQL = """
-- 使用者
INSERT INTO users (username, display_name) VALUES ('alice', '小美');
INSERT INTO users (username, display_name) VALUES ('bob',   '阿博');
INSERT INTO users (username, display_name) VALUES ('carol', '小嘉');

-- 旅行（trip_id=1, 日本 5 天, 預算 NT$40000/人）
INSERT INTO trips (user_id, trip_name, destination, currency_code, start_date, end_date, total_budget)
VALUES (1, '東京之旅', '日本', 'JPY', '2025-03-01', '2025-03-05', 40000);

-- 旅行成員
INSERT INTO trip_members (trip_id, user_id) VALUES (1, 1);
INSERT INTO trip_members (trip_id, user_id) VALUES (1, 2);
INSERT INTO trip_members (trip_id, user_id) VALUES (1, 3);

-- 交易（日幣匯率 1 TWD ≈ 4.61 JPY，exchange_rate = TWD/外幣 = 1/4.61 ≈ 0.2169）
-- Day 1: 2025-03-01
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 1, 3000, 'JPY', 651,  0.2169, '餐飲', '拉麵午餐', 'cash',        '2025-03-01 12:00:00', 'equal');
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 2, 8000, 'JPY', 1735, 0.2169, '住宿', '東京民宿 Day1', 'credit_card', '2025-03-01 15:00:00', 'equal');

-- Day 2: 2025-03-02
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 1, 2000, 'JPY', 434,  0.2169, '交通', '地鐵一日券', 'mobile_pay', '2025-03-02 09:00:00', 'equal');
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 3, 5000, 'JPY', 1085, 0.2169, '購物', '藥妝購物', 'cash',        '2025-03-02 14:00:00', 'equal');
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 2, 8000, 'JPY', 1735, 0.2169, '住宿', '東京民宿 Day2', 'credit_card', '2025-03-02 22:00:00', 'equal');

-- Day 3: 2025-03-03 (異常大額交易)
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 1, 30000, 'JPY', 6507, 0.2169, '購物', '名牌包（異常大額）', 'credit_card', '2025-03-03 11:00:00', 'equal');
INSERT INTO transactions (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate, category, description, payment_method, txn_datetime, split_type)
VALUES (1, 3, 8000, 'JPY', 1735, 0.2169, '住宿', '東京民宿 Day3', 'credit_card', '2025-03-03 22:00:00', 'equal');

-- 分帳明細（txn_id=1 的均分）
INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio) VALUES (1, 1, 1000, 217, 0.3333);
INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio) VALUES (1, 2, 1000, 217, 0.3333);
INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio) VALUES (1, 3, 1000, 217, 0.3333);

-- 結算記錄（pending）
INSERT INTO settlements (trip_id, from_user, to_user, amount, currency_code, amount_twd, exchange_rate, status)
VALUES (1, 3, 1, 1000, 'JPY', 217, 0.2169, 'pending');

-- 政府統計資料
INSERT INTO gov_outbound_stats (year, total_outbound_trips, avg_stay_nights, avg_spending_twd, avg_spending_usd)
VALUES (2023, 12000000, 7.84, 60481, 1907);
INSERT INTO gov_outbound_stats (year, total_outbound_trips, avg_stay_nights, avg_spending_twd, avg_spending_usd)
VALUES (2022, 10000000, 7.50, 55000, 1750);

-- 匯率資料（多日，供 FxStrategy 測試）
INSERT INTO exchange_rates (base_currency, target_currency, rate, recorded_date) VALUES ('TWD', 'JPY', 4.61, '2025-02-10');
INSERT INTO exchange_rates (base_currency, target_currency, rate, recorded_date) VALUES ('TWD', 'JPY', 4.65, '2025-02-15');
INSERT INTO exchange_rates (base_currency, target_currency, rate, recorded_date) VALUES ('TWD', 'JPY', 4.58, '2025-02-20');
INSERT INTO exchange_rates (base_currency, target_currency, rate, recorded_date) VALUES ('TWD', 'JPY', 4.70, '2025-02-25');
INSERT INTO exchange_rates (base_currency, target_currency, rate, recorded_date) VALUES ('TWD', 'JPY', 4.61, '2025-03-01');
INSERT INTO exchange_rates (base_currency, target_currency, rate, recorded_date) VALUES ('TWD', 'USD', 0.031, '2025-03-01');
"""


@pytest.fixture
def db_path(tmp_path):
    """建立含 schema 與種子資料的測試資料庫，回傳路徑字串"""
    db_file = tmp_path / "test_travel_wallet.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SEED_SQL)
    conn.commit()
    conn.close()
    return str(db_file)

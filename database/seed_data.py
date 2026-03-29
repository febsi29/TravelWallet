"""
seed_data.py - 種子資料生成腳本

8 位使用者，5 趟不同組合的旅行：
  Trip 1: 東京自由行    - 俊名、品伃、宏育、品澄（4人）
  Trip 2: 首爾追星之旅  - 漢威、晨云、筠慧、迺芯（4人）
  Trip 3: 清邁探索之旅  - 俊名、宏育、漢威、晨云（4人）
  Trip 4: 沖繩海島行    - 品伃、品澄、筠慧、迺芯（4人）
  Trip 5: 大阪美食之旅  - 全員 8 人
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

random.seed(42)

# ================================================================
# 使用者
# ================================================================
USERS = [
    {"username": "junming",   "display_name": "俊名"},  # 0
    {"username": "pinyu",     "display_name": "品伃"},  # 1
    {"username": "hongyu",    "display_name": "宏育"},  # 2
    {"username": "pincheng",  "display_name": "品澄"},  # 3
    {"username": "hanwei",    "display_name": "漢威"},  # 4
    {"username": "chenyun",   "display_name": "晨云"},  # 5
    {"username": "yunhui",    "display_name": "筠慧"},  # 6
    {"username": "naixin",    "display_name": "迺芯"},  # 7
]

# ================================================================
# Trip 1：東京自由行（俊名、品伃、宏育、品澄）
# ================================================================
TRIP1 = {
    "trip_name": "114/03/15 東京",
    "destination": "日本",
    "currency_code": "JPY",
    "start_date": "2025-03-15",
    "end_date":   "2025-03-19",
    "total_budget": 120000,
    "status": "completed",
    "members": [0, 1, 2, 3],
    "creator": 0,
    "rate": 0.217,
}
# (day, hour, min, payer_idx_in_members, amount, category, desc, location, split_type)
TRIP1_TXN = [
    (0, 14, 30, 0, 3200,  "交通", "成田機場→新宿 N'EX",      "成田機場", "equal"),
    (0, 18, 30, 2, 40000, "住宿", "新宿旅館 第1晚",           "新宿",     "equal"),
    (0, 20,  0, 3,  2400, "餐飲", "便利商店宵夜",             "新宿",     "equal"),
    (1,  8,  0, 0,  4800, "餐飲", "飯店早餐",                 "新宿",     "equal"),
    (1,  9, 30, 1,  1200, "交通", "地鐵到淺草",               "淺草",     "equal"),
    (1, 12,  0, 2,  8000, "餐飲", "淺草炸蝦天丼 4人",         "淺草",     "equal"),
    (1, 14,  0, 3,  8800, "娛樂", "晴空塔門票 4人",           "晴空塔",   "equal"),
    (1, 19,  0, 0, 16000, "餐飲", "居酒屋晚餐 4人",           "淺草",     "equal"),
    (1, 21,  0, 1, 40000, "住宿", "新宿旅館 第2晚",           "新宿",     "equal"),
    (2,  9,  0, 2,  3600, "餐飲", "原宿鬆餅早午餐",           "原宿",     "equal"),
    (2, 11,  0, 3, 15000, "購物", "竹下通逛街",               "原宿",     "custom"),
    (2, 13,  0, 0,  6000, "餐飲", "澀谷拉麵午餐",             "澀谷",     "equal"),
    (2, 15,  0, 1, 28000, "購物", "藥妝店採購",               "澀谷",     "custom"),
    (2, 19,  0, 2, 24000, "餐飲", "燒肉晚餐 4人",             "澀谷",     "equal"),
    (2, 21,  0, 3, 40000, "住宿", "新宿旅館 第3晚",           "新宿",     "equal"),
    (3, 10,  0, 0, 35000, "購物", "秋葉原電器/公仔",          "秋葉原",   "custom"),
    (3, 13,  0, 1,  5200, "餐飲", "秋葉原咖哩飯 4人",         "秋葉原",   "equal"),
    (3, 19,  0, 2, 20000, "餐飲", "壽司晚餐 4人",             "上野",     "equal"),
    (3, 21,  0, 3, 40000, "住宿", "新宿旅館 第4晚",           "新宿",     "equal"),
    (4,  8,  0, 0,  4000, "餐飲", "最後早餐",                 "新宿",     "equal"),
    (4, 10, 30, 1, 18000, "購物", "東京車站伴手禮",            "東京車站", "custom"),
    (4, 12,  0, 2,  3200, "交通", "新宿→成田機場",            "成田機場", "equal"),
    # 異常交易（供異常偵測展示）
    (3, 22,  0, 0, 98000, "購物", "秋葉原限定版公仔（個人）", "秋葉原",  "custom"),
]
TRIP1_CUSTOM = {
    10: {0: 8000, 1: 3000, 2: 2000, 3: 2000},
    12: {0: 5000, 1: 8000, 2: 10000, 3: 5000},
    15: {0: 30000, 1: 2000, 2: 2000, 3: 1000},
    21: {0: 4000, 1: 6000, 2: 4000, 3: 4000},
    22: {0: 98000},
}

# ================================================================
# Trip 2：首爾追星之旅（漢威、晨云、筠慧、迺芯）
# ================================================================
TRIP2 = {
    "trip_name": "114/05/01 首爾",
    "destination": "韓國",
    "currency_code": "KRW",
    "start_date": "2025-05-01",
    "end_date":   "2025-05-04",
    "total_budget": 50000,
    "status": "completed",
    "members": [4, 5, 6, 7],
    "creator": 4,
    "rate": 0.024,
}
TRIP2_TXN = [
    (0, 15,  0, 0, 180000, "交通", "仁川機場→明洞 機場鐵路", "仁川機場", "equal"),
    (0, 18,  0, 1, 320000, "住宿", "明洞旅館 第1晚",          "明洞",     "equal"),
    (0, 20,  0, 2,  48000, "餐飲", "弘大燒烤晚餐 4人",        "弘大",     "equal"),
    (1,  9,  0, 3,  32000, "餐飲", "早餐飯捲",                "明洞",     "equal"),
    (1, 11,  0, 0, 120000, "娛樂", "SM Entertainment 導覽",   "清潭洞",   "equal"),
    (1, 14,  0, 1,  56000, "餐飲", "江南炸雞午餐 4人",        "江南",     "equal"),
    (1, 16,  0, 2, 240000, "購物", "K-beauty 保養品",         "明洞",     "custom"),
    (1, 19,  0, 3, 320000, "住宿", "明洞旅館 第2晚",          "明洞",     "equal"),
    (2,  9,  0, 0,  28000, "餐飲", "蔘雞湯早餐",              "仁寺洞",   "equal"),
    (2, 11,  0, 1,  80000, "娛樂", "樂天世界門票 4人",        "蠶室",     "equal"),
    (2, 14,  0, 2,  45000, "餐飲", "部隊鍋午餐",              "蠶室",     "equal"),
    (2, 17,  0, 3, 160000, "購物", "東大門服飾採購",           "東大門",   "custom"),
    (2, 19,  0, 0, 320000, "住宿", "明洞旅館 第3晚",          "明洞",     "equal"),
    (3,  8,  0, 1,  24000, "餐飲", "出發前早餐",              "明洞",     "equal"),
    (3, 10,  0, 2,  90000, "購物", "機場免稅店",               "仁川機場", "custom"),
    # 異常交易
    (2, 22,  0, 3, 980000, "購物", "限量聯名球鞋（個人）",    "明洞",     "custom"),
]
TRIP2_CUSTOM = {
    6:  {0: 40000, 1: 60000, 2: 80000, 3: 60000},
    11: {0: 50000, 1: 30000, 2: 40000, 3: 40000},
    14: {0: 20000, 1: 30000, 2: 40000},
    15: {3: 980000},
}

# ================================================================
# Trip 3：清邁探索之旅（俊名、宏育、漢威、晨云）
# ================================================================
TRIP3 = {
    "trip_name": "114/07/10 清邁",
    "destination": "泰國",
    "currency_code": "THB",
    "start_date": "2025-07-10",
    "end_date":   "2025-07-14",
    "total_budget": 30000,
    "status": "completed",
    "members": [0, 2, 4, 5],
    "creator": 0,
    "rate": 0.91,
}
TRIP3_TXN = [
    # members local: 0=俊名, 1=宏育, 2=漢威, 3=晨云
    (0, 13,  0, 0,  800, "交通", "清邁機場→古城 Grab",     "清邁機場", "equal"),
    (0, 15,  0, 1, 2400, "住宿", "古城民宿 第1晚",          "清邁古城", "equal"),
    (0, 18,  0, 2,  480, "餐飲", "夜市小吃 4人",            "週六夜市", "equal"),
    (1,  8,  0, 3,  360, "餐飲", "咖啡廳早午餐",            "清邁古城", "equal"),
    (1, 10,  0, 0, 1800, "娛樂", "大象保護園區門票 4人",    "清邁郊區", "equal"),
    (1, 14,  0, 1,  320, "餐飲", "泰式炒河粉午餐",          "清邁",     "equal"),
    (1, 16,  0, 2, 2400, "住宿", "古城民宿 第2晚",          "清邁古城", "equal"),
    (1, 18,  0, 3, 1200, "娛樂", "泰拳表演門票 4人",        "尼曼路",   "equal"),
    (2,  9,  0, 0,  280, "餐飲", "豬腳飯早餐",              "清邁",     "equal"),
    (2, 10, 30, 1, 2400, "娛樂", "泰式古法按摩 4人",        "清邁古城", "equal"),
    (2, 14,  0, 2,  560, "餐飲", "素食餐廳午餐",            "尼曼路",   "equal"),
    (2, 16,  0, 3, 3600, "購物", "夜市手工藝品",            "週日夜市", "custom"),
    (2, 19,  0, 0, 2400, "住宿", "古城民宿 第3晚",          "清邁古城", "equal"),
    (3,  8,  0, 1,  400, "餐飲", "最後早餐 Khao Tom",       "清邁",     "equal"),
    (3, 10,  0, 2,  800, "交通", "古城→機場 Grab",          "清邁機場", "equal"),
]
TRIP3_CUSTOM = {
    11: {0: 800, 1: 1200, 2: 1000, 3: 600},
}

# ================================================================
# Trip 4：沖繩海島行（品伃、品澄、筠慧、迺芯）
# ================================================================
TRIP4 = {
    "trip_name": "114/08/15 沖繩",
    "destination": "日本",
    "currency_code": "JPY",
    "start_date": "2025-08-15",
    "end_date":   "2025-08-18",
    "total_budget": 80000,
    "status": "completed",
    "members": [1, 3, 6, 7],
    "creator": 1,
    "rate": 0.215,
}
TRIP4_TXN = [
    # members local: 0=品伃, 1=品澄, 2=筠慧, 3=迺芯
    (0, 14,  0, 0, 2400, "交通", "那霸機場→國際通 巴士",    "那霸機場", "equal"),
    (0, 16,  0, 1,35000, "住宿", "美浜飯店 第1晚",           "北谷",     "equal"),
    (0, 18,  0, 2, 8800, "餐飲", "沖繩料理晚餐 4人",         "國際通",   "equal"),
    (1,  8,  0, 3, 3600, "餐飲", "飯店早餐",                 "北谷",     "equal"),
    (1, 10,  0, 0,14000, "娛樂", "美麗海水族館門票 4人",     "本部",     "equal"),
    (1, 13,  0, 1, 6400, "餐飲", "海景餐廳午餐 4人",         "本部",     "equal"),
    (1, 16,  0, 2,35000, "住宿", "美浜飯店 第2晚",           "北谷",     "equal"),
    (1, 18,  0, 3,12000, "餐飲", "美國村燒烤晚餐 4人",       "北谷",     "equal"),
    (2,  9,  0, 0, 9600, "娛樂", "浮潛體驗 4人",             "恩納",     "equal"),
    (2, 13,  0, 1, 4800, "餐飲", "塔可飯午餐 4人",           "恩納",     "equal"),
    (2, 15,  0, 2,18000, "購物", "國際通伴手禮＋藥妝",       "國際通",   "custom"),
    (2, 19,  0, 3,35000, "住宿", "美浜飯店 第3晚",           "北谷",     "equal"),
    (3,  8,  0, 0, 4000, "餐飲", "最後早餐 沖繩麵",          "那霸",     "equal"),
    (3, 10,  0, 1, 2400, "交通", "北谷→那霸機場 接駁",       "那霸機場", "equal"),
]
TRIP4_CUSTOM = {
    10: {0: 6000, 1: 4000, 2: 5000, 3: 3000},
}

# ================================================================
# Trip 5：大阪美食之旅（全員 8 人）
# ================================================================
TRIP5 = {
    "trip_name": "114/10/01 大阪",
    "destination": "日本",
    "currency_code": "JPY",
    "start_date": "2025-10-01",
    "end_date":   "2025-10-05",
    "total_budget": 250000,
    "status": "planning",
    "members": [0, 1, 2, 3, 4, 5, 6, 7],
    "creator": 0,
    "rate": 0.213,
}
TRIP5_TXN = [
    (0, 13,  0, 0,  4800, "交通", "關西機場→難波 HARUKA",   "關西機場", "equal"),
    (0, 16,  0, 1, 80000, "住宿", "道頓堀旅館 第1晚 8人",    "道頓堀",   "equal"),
    (0, 19,  0, 2, 32000, "餐飲", "道頓堀章魚燒+大阪燒 8人", "道頓堀",   "equal"),
    (1,  8,  0, 3,  9600, "餐飲", "黑門市場早餐 8人",        "黑門市場", "equal"),
    (1, 10,  0, 4, 24000, "娛樂", "大阪城入場券 8人",        "大阪城",   "equal"),
    (1, 13,  0, 5, 20000, "餐飲", "心齋橋串炸午餐 8人",      "心齋橋",   "equal"),
    (1, 16,  0, 6, 56000, "購物", "心齋橋藥妝採購",           "心齋橋",   "custom"),
    (1, 19,  0, 7, 48000, "餐飲", "難波燒肉晚餐 8人",        "難波",     "equal"),
    (1, 21,  0, 0, 80000, "住宿", "道頓堀旅館 第2晚 8人",    "道頓堀",   "equal"),
    (2,  8,  0, 1,  8000, "餐飲", "天滿橋早市",              "天滿橋",   "equal"),
    (2, 10,  0, 2, 16000, "娛樂", "海遊館水族館 8人",        "大阪港",   "equal"),
    (2, 14,  0, 3, 16000, "餐飲", "天保山海鮮午餐 8人",      "大阪港",   "equal"),
    (2, 17,  0, 4, 32000, "娛樂", "萬聖節夜間活動（環球）",  "USJ",      "equal"),
    (2, 21,  0, 5, 80000, "住宿", "道頓堀旅館 第3晚 8人",    "道頓堀",   "equal"),
    (3,  9,  0, 6, 12000, "餐飲", "梅田早午餐",              "梅田",     "equal"),
    (3, 11,  0, 7, 40000, "購物", "梅田 HEP FIVE 購物",      "梅田",     "custom"),
    (3, 14,  0, 0, 24000, "餐飲", "梅田拉麵激戰區 8人",      "梅田",     "equal"),
    (3, 17,  0, 1, 18000, "餐飲", "北新地居酒屋 8人",        "北新地",   "equal"),
    (3, 21,  0, 2, 80000, "住宿", "道頓堀旅館 第4晚 8人",    "道頓堀",   "equal"),
    (4,  8,  0, 3,  9600, "餐飲", "最後早餐 難波拉麵",       "難波",     "equal"),
    (4, 10,  0, 4, 32000, "購物", "關西機場免稅店",           "關西機場", "custom"),
    (4, 11,  0, 5,  4800, "交通", "難波→關西機場 HARUKA",    "關西機場", "equal"),
]
TRIP5_CUSTOM = {
    6:  {0: 8000, 1: 10000, 2: 6000, 3: 8000, 4: 8000, 5: 6000, 6: 5000, 7: 5000},
    15: {0: 6000, 1: 5000, 2: 4000, 3: 8000, 4: 5000, 5: 4000, 6: 4000, 7: 4000},
    20: {0: 5000, 1: 4000, 2: 4000, 3: 5000, 4: 4000, 5: 3000, 6: 4000, 7: 3000},
}

ALL_TRIPS = [
    (TRIP1, TRIP1_TXN, TRIP1_CUSTOM),
    (TRIP2, TRIP2_TXN, TRIP2_CUSTOM),
    (TRIP3, TRIP3_TXN, TRIP3_CUSTOM),
    (TRIP4, TRIP4_TXN, TRIP4_CUSTOM),
    (TRIP5, TRIP5_TXN, TRIP5_CUSTOM),
]


# ================================================================
# 工具函式
# ================================================================

def calculate_settlements(cursor, trip_id, user_ids, rate):
    balances = {}
    for uid in user_ids:
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE trip_id=? AND paid_by=?",
            (trip_id, uid)
        )
        paid = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COALESCE(SUM(sd.share_amount), 0)
            FROM split_details sd JOIN transactions t ON sd.txn_id = t.txn_id
            WHERE t.trip_id=? AND sd.user_id=?
        """, (trip_id, uid))
        owed = cursor.fetchone()[0]
        balances[uid] = paid - owed

    creditors = sorted([(u, a) for u, a in balances.items() if a > 0], key=lambda x: -x[1])
    debtors   = sorted([(u, -a) for u, a in balances.items() if a < 0], key=lambda x: -x[1])

    transfers = []
    i = j = 0
    while i < len(creditors) and j < len(debtors):
        cid, credit = creditors[i]
        did, debt   = debtors[j]
        amt = min(credit, debt)
        transfers.append({"from": did, "to": cid, "amount": round(amt), "amount_twd": round(amt * rate)})
        creditors[i] = (cid, credit - amt)
        debtors[j]   = (did, debt - amt)
        if creditors[i][1] < 0.5: i += 1
        if debtors[j][1] < 0.5:   j += 1
    return transfers


# ================================================================
# 主流程
# ================================================================

def seed_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("清除舊資料...")
    for tbl in ("settlements", "split_details", "transactions", "trip_members", "trips", "wallets", "users"):
        c.execute(f"DELETE FROM {tbl}")

    # --- 使用者 ---
    print("建立 8 位使用者...")
    user_ids = []
    for u in USERS:
        c.execute("INSERT INTO users (username, display_name) VALUES (?, ?)",
                  (u["username"], u["display_name"]))
        user_ids.append(c.lastrowid)

    # --- 錢包 ---
    for uid in user_ids:
        for cur, bal in [("TWD", round(random.uniform(5000, 30000), 0)),
                         ("JPY", round(random.uniform(5000, 50000), 0))]:
            c.execute("INSERT INTO wallets (user_id, currency_code, balance, locked_balance) VALUES (?, ?, ?, 0)",
                      (uid, cur, bal))

    # --- 旅行 ---
    for trip_def, txns, customs in ALL_TRIPS:
        member_global_ids = [user_ids[i] for i in trip_def["members"]]
        creator_id = user_ids[trip_def["creator"]]
        rate = trip_def["rate"]
        start_dt = datetime.strptime(trip_def["start_date"], "%Y-%m-%d")

        c.execute("""INSERT INTO trips (user_id, trip_name, destination, currency_code,
                     start_date, end_date, total_budget, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (creator_id, trip_def["trip_name"], trip_def["destination"],
                   trip_def["currency_code"], trip_def["start_date"],
                   trip_def["end_date"], trip_def["total_budget"], trip_def["status"]))
        trip_id = c.lastrowid
        print(f"  旅行：{trip_def['trip_name']} (id={trip_id}, {len(member_global_ids)} 人)")

        for gid in member_global_ids:
            c.execute("INSERT OR IGNORE INTO trip_members (trip_id, user_id) VALUES (?, ?)",
                      (trip_id, gid))

        for i, txn in enumerate(txns):
            day, hour, minute, payer_local, amount, category, desc, location, split_type = txn
            payer_id = member_global_ids[payer_local]
            dt_str   = (start_dt + timedelta(days=day, hours=hour, minutes=minute)).strftime("%Y-%m-%d %H:%M:%S")
            amount_twd = round(amount * rate)
            payment    = random.choice(["cash", "credit_card", "credit_card", "mobile_pay"])

            c.execute("""INSERT INTO transactions
                         (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate,
                          category, description, payment_method, txn_datetime, location, split_type)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (trip_id, payer_id, amount, trip_def["currency_code"], amount_twd, rate,
                       category, desc, payment, dt_str, location, split_type))
            txn_id = c.lastrowid

            if split_type == "equal":
                n = len(member_global_ids)
                share = round(amount / n, 2)
                share_twd = round(share * rate)
                ratio = round(1 / n, 4)
                for gid in member_global_ids:
                    c.execute("""INSERT INTO split_details
                                 (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                                 VALUES (?, ?, ?, ?, ?, 1)""",
                              (txn_id, gid, share, share_twd, ratio))
            elif split_type == "custom" and i in customs:
                for local_idx, share_amt in customs[i].items():
                    gid = member_global_ids[local_idx]
                    share_twd = round(share_amt * rate)
                    ratio = round(share_amt / amount, 4) if amount else 0
                    c.execute("""INSERT INTO split_details
                                 (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                                 VALUES (?, ?, ?, ?, ?, 1)""",
                              (txn_id, gid, share_amt, share_twd, ratio))

        # 結算（只對已完成的旅行）
        if trip_def["status"] == "completed":
            settled_at = (start_dt + timedelta(days=len(set(t[0] for t in txns)) + 1)).strftime("%Y-%m-%d 12:00:00")
            for s in calculate_settlements(c, trip_id, member_global_ids, rate):
                c.execute("""INSERT INTO settlements
                             (trip_id, from_user, to_user, amount, currency_code, amount_twd, exchange_rate, status, settled_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)""",
                          (trip_id, s["from"], s["to"], s["amount"], trip_def["currency_code"],
                           s["amount_twd"], rate, settled_at))

    conn.commit()
    conn.close()

    # 信用卡種子資料
    try:
        from src.card_recommend import seed_cards
        seed_cards(DB_PATH)
    except Exception:
        pass

    print("\n種子資料生成完成！")
    _verify()


def _verify():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    print("=" * 40)
    for tbl, label in [("users", "使用者"), ("trips", "旅行"),
                        ("transactions", "交易"), ("split_details", "分帳明細"),
                        ("settlements", "結算")]:
        c.execute(f"SELECT COUNT(*) FROM {tbl}")
        print(f"  {label}: {c.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    random.seed(42)
    seed_all()

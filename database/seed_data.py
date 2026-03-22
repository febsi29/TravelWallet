"""
seed_data.py - 種子資料生成腳本

生成模擬的使用者、旅行、交易、分帳資料供開發與展示用
情境：4 個好朋友 2025 年去日本東京 5 天自由行
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

# 路徑設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample")


# === 模擬資料 ===

USERS = [
    {"username": "jaychou", "display_name": "周杰倫"},
    {"username": "jjlin", "display_name": "林俊傑"},
    {"username": "weibird", "display_name": "韋禮安"},
    {"username": "jolin", "display_name": "蔡依林"},
]

TRIP = {
    "trip_name": "2025 東京自由行",
    "destination": "日本",
    "currency_code": "JPY",
    "start_date": "2025-03-15",
    "end_date": "2025-03-19",
    "total_budget": 120000,   # NT$120,000
    "status": "completed",
}

# 匯率：1 JPY = 0.217 TWD（模擬值）
JPY_TO_TWD = 0.217

# 模擬交易資料（真實感的東京旅行消費）
# (日期偏移, 時, 分, 付款人index, 金額JPY, 類別, 說明, 地點, 分帳方式)
TRANSACTIONS = [
    # === Day 1 (3/15) 抵達東京 ===
    (0, 14, 30, 0, 3200, "交通", "成田機場到新宿 N'EX", "成田機場", "equal"),
    (0, 17, 0, 1, 12000, "餐飲", "一蘭拉麵 4人", "新宿", "equal"),
    (0, 18, 30, 2, 40000, "住宿", "新宿旅館 第1晚", "新宿", "equal"),
    (0, 20, 0, 3, 2400, "餐飲", "便利商店宵夜", "新宿", "equal"),

    # === Day 2 (3/16) 淺草 + 晴空塔 ===
    (1, 8, 0, 0, 4800, "餐飲", "飯店附近早餐", "新宿", "equal"),
    (1, 9, 30, 1, 1200, "交通", "地鐵到淺草", "淺草", "equal"),
    (1, 12, 0, 2, 8000, "餐飲", "淺草炸蝦天丼 4人", "淺草", "equal"),
    (1, 14, 0, 3, 8800, "娛樂", "晴空塔門票 4人", "晴空塔", "equal"),
    (1, 16, 0, 0, 3500, "餐飲", "晴空塔咖啡廳", "晴空塔", "equal"),
    (1, 18, 30, 1, 16000, "餐飲", "居酒屋晚餐 4人", "淺草", "equal"),
    (1, 20, 0, 2, 40000, "住宿", "新宿旅館 第2晚", "新宿", "equal"),

    # === Day 3 (3/17) 原宿 + 澀谷 ===
    (2, 9, 0, 3, 3600, "餐飲", "原宿鬆餅早午餐", "原宿", "equal"),
    (2, 11, 0, 0, 15000, "購物", "竹下通逛街", "原宿", "custom"),
    (2, 13, 0, 1, 6000, "餐飲", "澀谷拉麵午餐 4人", "澀谷", "equal"),
    (2, 15, 0, 2, 28000, "購物", "藥妝店採購", "澀谷", "custom"),
    (2, 17, 0, 3, 4000, "餐飲", "澀谷甜點下午茶", "澀谷", "equal"),
    (2, 19, 0, 0, 24000, "餐飲", "燒肉晚餐 4人", "澀谷", "equal"),
    (2, 21, 0, 1, 40000, "住宿", "新宿旅館 第3晚", "新宿", "equal"),

    # === Day 4 (3/18) 秋葉原 + 上野 ===
    (3, 8, 30, 2, 3200, "餐飲", "旅館附近吉野家", "新宿", "equal"),
    (3, 10, 0, 3, 1200, "交通", "地鐵到秋葉原", "秋葉原", "equal"),
    (3, 11, 0, 0, 35000, "購物", "秋葉原電器/公仔", "秋葉原", "custom"),
    (3, 13, 0, 1, 5200, "餐飲", "秋葉原咖哩飯 4人", "秋葉原", "equal"),
    (3, 15, 0, 2, 2400, "娛樂", "上野公園散步+抹茶", "上野", "equal"),
    (3, 17, 30, 3, 9000, "購物", "上野阿美橫丁零食", "上野", "equal"),
    (3, 19, 0, 0, 20000, "餐飲", "壽司晚餐 4人", "上野", "equal"),
    (3, 21, 0, 1, 40000, "住宿", "新宿旅館 第4晚", "新宿", "equal"),
    (3, 22, 0, 2, 6800, "餐飲", "新宿歌舞伎町宵夜串燒", "新宿", "equal"),

    # === Day 5 (3/19) 最後一天 + 回程 ===
    (4, 8, 0, 3, 4000, "餐飲", "最後早餐 吃好一點", "新宿", "equal"),
    (4, 9, 0, 0, 40000, "住宿", "新宿旅館 第5晚", "新宿", "equal"),
    (4, 10, 30, 1, 18000, "購物", "車站伴手禮 東京芭奈奈+薯條三兄弟", "東京車站", "custom"),
    (4, 12, 0, 2, 3200, "交通", "新宿到成田機場", "成田機場", "equal"),
]

# 自訂分帳的金額分配（購物類，每人買不同東西）
CUSTOM_SPLITS = {
    # (交易index): {user_index: JPY金額}
    12: {0: 8000, 1: 3000, 2: 2000, 3: 2000},    # 竹下通逛街
    14: {0: 5000, 1: 8000, 2: 10000, 3: 5000},    # 藥妝店
    20: {0: 20000, 1: 5000, 2: 5000, 3: 5000},    # 秋葉原（小明買最多）
    29: {0: 4000, 1: 5000, 2: 4000, 3: 5000},     # 伴手禮
}


# === 寫入資料庫 ===

def seed_all():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 清除舊的種子資料（保留政府統計資料）
    print("清除舊的種子資料...")
    cursor.execute("DELETE FROM settlements")
    cursor.execute("DELETE FROM split_details")
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM trip_members")
    cursor.execute("DELETE FROM trips")
    cursor.execute("DELETE FROM users")

    # --- 1. 建立使用者 ---
    print("建立使用者...")
    user_ids = []
    for u in USERS:
        cursor.execute(
            "INSERT INTO users (username, display_name) VALUES (?, ?)",
            (u["username"], u["display_name"])
        )
        user_ids.append(cursor.lastrowid)
        print(f"   {u['display_name']} (id={cursor.lastrowid})")

    # --- 2. 建立旅行 ---
    print("建立旅行...")
    cursor.execute("""
        INSERT INTO trips (user_id, trip_name, destination, currency_code,
                          start_date, end_date, total_budget, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_ids[0],   # 小明建立的旅行
        TRIP["trip_name"], TRIP["destination"], TRIP["currency_code"],
        TRIP["start_date"], TRIP["end_date"], TRIP["total_budget"], TRIP["status"]
    ))
    trip_id = cursor.lastrowid
    print(f"   {TRIP['trip_name']} (id={trip_id})")

    # --- 3. 加入旅行成員 ---
    print("加入旅行成員...")
    for uid, u in zip(user_ids, USERS):
        cursor.execute(
            "INSERT INTO trip_members (trip_id, user_id, nickname) VALUES (?, ?, ?)",
            (trip_id, uid, u["display_name"])
        )

    # --- 4. 建立交易紀錄 + 分帳 ---
    print("建立交易紀錄與分帳...")
    start_date = datetime(2025, 3, 15)
    txn_count = 0
    split_count = 0

    for i, txn in enumerate(TRANSACTIONS):
        day_offset, hour, minute, payer_idx, amount_jpy, category, desc, location, split_type = txn

        txn_datetime = start_date + timedelta(days=day_offset, hours=hour, minutes=minute)
        amount_twd = round(amount_jpy * JPY_TO_TWD)
        payer_id = user_ids[payer_idx]

        # 隨機付款方式
        payment = random.choice(["cash", "credit_card", "credit_card", "mobile_pay"])

        cursor.execute("""
            INSERT INTO transactions
            (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate,
             category, description, payment_method, txn_datetime, location, split_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_id, payer_id, amount_jpy, "JPY", amount_twd, JPY_TO_TWD,
            category, desc, payment, txn_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            location, split_type
        ))
        txn_id = cursor.lastrowid
        txn_count += 1

        # --- 建立分帳明細 ---
        if split_type == "equal":
            # 均分 4 人
            share_jpy = round(amount_jpy / 4, 2)
            share_twd = round(share_jpy * JPY_TO_TWD)
            for uid in user_ids:
                cursor.execute("""
                    INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (txn_id, uid, share_jpy, share_twd, 0.25, 1))
                split_count += 1

        elif split_type == "custom" and i in CUSTOM_SPLITS:
            # 自訂金額分帳
            splits = CUSTOM_SPLITS[i]
            for uid_idx, share_jpy in splits.items():
                share_twd = round(share_jpy * JPY_TO_TWD)
                ratio = round(share_jpy / amount_jpy, 4)
                cursor.execute("""
                    INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (txn_id, user_ids[uid_idx], share_jpy, share_twd, ratio, 1))
                split_count += 1

    print(f" {txn_count} 筆交易, {split_count} 筆分帳明細")

    # --- 5. 計算最終結算 ---
    print("計算最終結算...")
    settlements = calculate_settlements(cursor, trip_id, user_ids)
    for s in settlements:
        cursor.execute("""
            INSERT INTO settlements
            (trip_id, from_user, to_user, amount, currency_code, amount_twd, exchange_rate, status, settled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_id, s["from"], s["to"], s["amount_jpy"], "JPY",
            s["amount_twd"], JPY_TO_TWD, "completed",
            "2025-03-20 12:00:00"
        ))
    print(f"   {len(settlements)} 筆結算紀錄")

    conn.commit()
    conn.close()
    print(f"\n種子資料生成完成！")


def calculate_settlements(cursor, trip_id, user_ids):
    """
    計算每人淨餘額，並用貪心演算法最小化轉帳次數
    """
    balances = {}

    for uid in user_ids:
        # 這個人總共付了多少
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE trip_id=? AND paid_by=?",
            (trip_id, uid)
        )
        total_paid = cursor.fetchone()[0]

        # 這個人總共該分攤多少
        cursor.execute("""
            SELECT COALESCE(SUM(sd.share_amount), 0)
            FROM split_details sd
            JOIN transactions t ON sd.txn_id = t.txn_id
            WHERE t.trip_id=? AND sd.user_id=?
        """, (trip_id, uid))
        total_owed = cursor.fetchone()[0]

        balances[uid] = total_paid - total_owed

    # 取得使用者名稱（用於 print）
    names = {}
    for uid in user_ids:
        cursor.execute("SELECT display_name FROM users WHERE user_id=?", (uid,))
        names[uid] = cursor.fetchone()[0]

    # 印出淨餘額
    print("   --- 淨餘額（正=被欠, 負=欠人）---")
    for uid, balance in balances.items():
        twd = round(balance * JPY_TO_TWD)
        symbol = "被欠" if balance > 0 else "欠人"
        print(f"{names[uid]}: ¥{balance:,.0f} (NT${twd:,}) {symbol}")

    # 貪心演算法：最小化轉帳次數
    creditors = sorted(
        [(uid, amt) for uid, amt in balances.items() if amt > 0],
        key=lambda x: -x[1]
    )
    debtors = sorted(
        [(uid, -amt) for uid, amt in balances.items() if amt < 0],
        key=lambda x: -x[1]
    )

    transfers = []
    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        creditor_id, credit = creditors[i]
        debtor_id, debt = debtors[j]
        amount = min(credit, debt)

        transfers.append({
            "from": debtor_id,
            "to": creditor_id,
            "amount_jpy": round(amount),
            "amount_twd": round(amount * JPY_TO_TWD),
        })
        print(f"{names[debtor_id]} → {names[creditor_id]}: ¥{amount:,.0f} (NT${round(amount * JPY_TO_TWD):,})")

        creditors[i] = (creditor_id, credit - amount)
        debtors[j] = (debtor_id, debt - amount)

        if creditors[i][1] < 0.5:
            i += 1
        if debtors[j][1] < 0.5:
            j += 1

    return transfers


# === 驗證 ===

def verify_seed_data():
    """印出種子資料摘要"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n種子資料驗證")
    print("=" * 50)

    cursor.execute("SELECT COUNT(*) FROM users")
    print(f"使用者: {cursor.fetchone()[0]} 人")

    cursor.execute("SELECT COUNT(*) FROM trips")
    print(f"旅行: {cursor.fetchone()[0]} 趟")

    cursor.execute("SELECT COUNT(*) FROM transactions")
    print(f"交易紀錄: {cursor.fetchone()[0]} 筆")

    cursor.execute("SELECT COUNT(*) FROM split_details")
    print(f"分帳明細: {cursor.fetchone()[0]} 筆")

    cursor.execute("SELECT COUNT(*) FROM settlements")
    print(f"結算紀錄: {cursor.fetchone()[0]} 筆")

    # 各類別消費統計
    print("\n各類別消費（日圓）")
    print("-" * 40)
    cursor.execute("""
        SELECT category, COUNT(*) as cnt, SUM(amount) as total_jpy, SUM(amount_twd) as total_twd
        FROM transactions WHERE trip_id=1
        GROUP BY category ORDER BY total_jpy DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} 筆, ¥{row[2]:,.0f} (NT${row[3]:,})")

    # 各人代墊統計
    print("\n各人代墊金額")
    print("-" * 40)
    cursor.execute("""
        SELECT u.display_name, COUNT(*) as cnt, SUM(t.amount) as paid_jpy, SUM(t.amount_twd) as paid_twd
        FROM transactions t JOIN users u ON t.paid_by = u.user_id
        WHERE t.trip_id=1
        GROUP BY t.paid_by ORDER BY paid_jpy DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: 代墊 {row[1]} 次, ¥{row[2]:,.0f} (NT${row[3]:,})")

    conn.close()


# === 主程式 ===

if __name__ == "__main__":
    print("TravelWallet - 種子資料生成")
    print("=" * 40)

    random.seed(42)   # 固定隨機種子，確保每次結果一致
    seed_all()
    verify_seed_data()

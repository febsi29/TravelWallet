"""
seed_data.py - 


4  2025  5 
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

# 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample")


# ===  ===

USERS = [
    {"username": "ming", "display_name": ""},
    {"username": "hua", "display_name": ""},
    {"username": "mei", "display_name": ""},
    {"username": "jie", "display_name": ""},
]

TRIP = {
    "trip_name": "2025 ",
    "destination": "",
    "currency_code": "JPY",
    "start_date": "2025-03-15",
    "end_date": "2025-03-19",
    "total_budget": 120000,   # NT$120,000
    "status": "completed",
}

# 1 JPY = 0.217 TWD
JPY_TO_TWD = 0.217

# 
# (, , , index, JPY, , , , )
TRANSACTIONS = [
    # === Day 1 (3/15)  ===
    (0, 14, 30, 0, 3200, "", " N'EX", "", "equal"),
    (0, 17, 0, 1, 12000, "", " 4", "", "equal"),
    (0, 18, 30, 2, 40000, "", " 1", "", "equal"),
    (0, 20, 0, 3, 2400, "", "", "", "equal"),

    # === Day 2 (3/16)  +  ===
    (1, 8, 0, 0, 4800, "", "", "", "equal"),
    (1, 9, 30, 1, 1200, "", "", "", "equal"),
    (1, 12, 0, 2, 8000, "", " 4", "", "equal"),
    (1, 14, 0, 3, 8800, "", " 4", "", "equal"),
    (1, 16, 0, 0, 3500, "", "", "", "equal"),
    (1, 18, 30, 1, 16000, "", " 4", "", "equal"),
    (1, 20, 0, 2, 40000, "", " 2", "", "equal"),

    # === Day 3 (3/17)  +  ===
    (2, 9, 0, 3, 3600, "", "", "", "equal"),
    (2, 11, 0, 0, 15000, "", "", "", "custom"),
    (2, 13, 0, 1, 6000, "", " 4", "", "equal"),
    (2, 15, 0, 2, 28000, "", "", "", "custom"),
    (2, 17, 0, 3, 4000, "", "", "", "equal"),
    (2, 19, 0, 0, 24000, "", " 4", "", "equal"),
    (2, 21, 0, 1, 40000, "", " 3", "", "equal"),

    # === Day 4 (3/18)  +  ===
    (3, 8, 30, 2, 3200, "", "", "", "equal"),
    (3, 10, 0, 3, 1200, "", "", "", "equal"),
    (3, 11, 0, 0, 35000, "", "/", "", "custom"),
    (3, 13, 0, 1, 5200, "", " 4", "", "equal"),
    (3, 15, 0, 2, 2400, "", "+", "", "equal"),
    (3, 17, 30, 3, 9000, "", "", "", "equal"),
    (3, 19, 0, 0, 20000, "", " 4", "", "equal"),
    (3, 21, 0, 1, 40000, "", " 4", "", "equal"),
    (3, 22, 0, 2, 6800, "", "", "", "equal"),

    # === Day 5 (3/19)  +  ===
    (4, 8, 0, 3, 4000, "", " ", "", "equal"),
    (4, 9, 0, 0, 40000, "", " 5", "", "equal"),
    (4, 10, 30, 1, 18000, "", " +", "", "custom"),
    (4, 12, 0, 2, 3200, "", "", "", "equal"),
]

# 
CUSTOM_SPLITS = {
    # (index): {user_index: JPY}
    10: {0: 8000, 1: 3000, 2: 2000, 3: 2000},    # 
    14: {0: 5000, 1: 8000, 2: 10000, 3: 5000},    # 
    20: {0: 20000, 1: 5000, 2: 5000, 3: 5000},    # 
    29: {0: 4000, 1: 5000, 2: 4000, 3: 5000},     # 
}


# ===  ===

def seed_all():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 
    print("  ...")
    cursor.execute("DELETE FROM settlements")
    cursor.execute("DELETE FROM split_details")
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM trip_members")
    cursor.execute("DELETE FROM trips")
    cursor.execute("DELETE FROM users")

    # --- 1.  ---
    print(" ...")
    user_ids = []
    for u in USERS:
        cursor.execute(
            "INSERT INTO users (username, display_name) VALUES (?, ?)",
            (u["username"], u["display_name"])
        )
        user_ids.append(cursor.lastrowid)
        print(f"   {u['display_name']} (id={cursor.lastrowid})")

    # --- 2.  ---
    print("  ...")
    cursor.execute("""
        INSERT INTO trips (user_id, trip_name, destination, currency_code,
                          start_date, end_date, total_budget, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_ids[0],   # 
        TRIP["trip_name"], TRIP["destination"], TRIP["currency_code"],
        TRIP["start_date"], TRIP["end_date"], TRIP["total_budget"], TRIP["status"]
    ))
    trip_id = cursor.lastrowid
    print(f"   {TRIP['trip_name']} (id={trip_id})")

    # --- 3.  ---
    print(" ...")
    for uid, u in zip(user_ids, USERS):
        cursor.execute(
            "INSERT INTO trip_members (trip_id, user_id, nickname) VALUES (?, ?, ?)",
            (trip_id, uid, u["display_name"])
        )

    # --- 4.  +  ---
    print(" ...")
    start_date = datetime(2025, 3, 15)
    txn_count = 0
    split_count = 0

    for i, txn in enumerate(TRANSACTIONS):
        day_offset, hour, minute, payer_idx, amount_jpy, category, desc, location, split_type = txn

        txn_datetime = start_date + timedelta(days=day_offset, hours=hour, minutes=minute)
        amount_twd = round(amount_jpy * JPY_TO_TWD)
        payer_id = user_ids[payer_idx]

        # 
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

        # ---  ---
        if split_type == "equal":
            #  4 
            share_jpy = round(amount_jpy / 4, 2)
            share_twd = round(share_jpy * JPY_TO_TWD)
            for uid in user_ids:
                cursor.execute("""
                    INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (txn_id, uid, share_jpy, share_twd, 0.25, 1))
                split_count += 1

        elif split_type == "custom" and i in CUSTOM_SPLITS:
            # 
            splits = CUSTOM_SPLITS[i]
            for uid_idx, share_jpy in splits.items():
                share_twd = round(share_jpy * JPY_TO_TWD)
                ratio = round(share_jpy / amount_jpy, 4)
                cursor.execute("""
                    INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (txn_id, user_ids[uid_idx], share_jpy, share_twd, ratio, 1))
                split_count += 1

    print(f"    {txn_count} , {split_count} ")

    # --- 5.  ---
    print(" ...")
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
    print(f"    {len(settlements)} ")

    conn.commit()
    conn.close()
    print(f"\n ")


def calculate_settlements(cursor, trip_id, user_ids):
    """
    
    """
    balances = {}

    for uid in user_ids:
        # 
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE trip_id=? AND paid_by=?",
            (trip_id, uid)
        )
        total_paid = cursor.fetchone()[0]

        # 
        cursor.execute("""
            SELECT COALESCE(SUM(sd.share_amount), 0)
            FROM split_details sd
            JOIN transactions t ON sd.txn_id = t.txn_id
            WHERE t.trip_id=? AND sd.user_id=?
        """, (trip_id, uid))
        total_owed = cursor.fetchone()[0]

        balances[uid] = total_paid - total_owed

    #  print
    names = {}
    for uid in user_ids:
        cursor.execute("SELECT display_name FROM users WHERE user_id=?", (uid,))
        names[uid] = cursor.fetchone()[0]

    # 
    print("   --- =, =---")
    for uid, balance in balances.items():
        twd = round(balance * JPY_TO_TWD)
        symbol = " " if balance > 0 else " "
        print(f"   {names[uid]}: ¥{balance:,.0f} (NT${twd:,}) {symbol}")

    # 
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
        print(f"    {names[debtor_id]} → {names[creditor_id]}: ¥{amount:,.0f} (NT${round(amount * JPY_TO_TWD):,})")

        creditors[i] = (creditor_id, credit - amount)
        debtors[j] = (debtor_id, debt - amount)

        if creditors[i][1] < 0.5:
            i += 1
        if debtors[j][1] < 0.5:
            j += 1

    return transfers


# ===  ===

def verify_seed_data():
    """"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n ")
    print("=" * 50)

    cursor.execute("SELECT COUNT(*) FROM users")
    print(f": {cursor.fetchone()[0]} ")

    cursor.execute("SELECT COUNT(*) FROM trips")
    print(f": {cursor.fetchone()[0]} ")

    cursor.execute("SELECT COUNT(*) FROM transactions")
    print(f": {cursor.fetchone()[0]} ")

    cursor.execute("SELECT COUNT(*) FROM split_details")
    print(f": {cursor.fetchone()[0]} ")

    cursor.execute("SELECT COUNT(*) FROM settlements")
    print(f": {cursor.fetchone()[0]} ")

    # 
    print("\n ")
    print("-" * 40)
    cursor.execute("""
        SELECT category, COUNT(*) as cnt, SUM(amount) as total_jpy, SUM(amount_twd) as total_twd
        FROM transactions WHERE trip_id=1
        GROUP BY category ORDER BY total_jpy DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} , ¥{row[2]:,.0f} (NT${row[3]:,})")

    # 
    print("\n ")
    print("-" * 40)
    cursor.execute("""
        SELECT u.display_name, COUNT(*) as cnt, SUM(t.amount) as paid_jpy, SUM(t.amount_twd) as paid_twd
        FROM transactions t JOIN users u ON t.paid_by = u.user_id
        WHERE t.trip_id=1
        GROUP BY t.paid_by ORDER BY paid_jpy DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}:  {row[1]} , ¥{row[2]:,.0f} (NT${row[3]:,})")

    conn.close()


# ===  ===

if __name__ == "__main__":
    print(" TravelWallet - ")
    print("=" * 40)

    random.seed(42)   # 
    seed_all()
    verify_seed_data()

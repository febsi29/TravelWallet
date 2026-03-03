"""
split.py - 分帳核心引擎

功能：
- 均分 / 依比例 / 自訂金額分帳
- 代墊記錄管理
- 最小化轉帳次數演算法（Greedy Netting）
- 多幣別換算結算
- 淨餘額計算

使用方式：
  from src.split import SplitEngine
  engine = SplitEngine(db_path)
  engine.add_equal_split(txn_id, user_ids)
  result = engine.settle_trip(trip_id)
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


class SplitEngine:
    """分帳核心引擎"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ============================================================
    #  分帳方式
    # ============================================================

    def add_equal_split(self, txn_id, user_ids):
        """
        均分：將一筆交易平均分給指定的使用者們

        參數：
            txn_id: 交易 ID
            user_ids: 要分攤的使用者 ID 列表
        回傳：
            list[dict]: 每個人的分帳明細
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 取得交易資訊
        txn = self._get_transaction(cursor, txn_id)
        if not txn:
            conn.close()
            raise ValueError(f"找不到交易 ID={txn_id}")

        amount = txn["amount"]
        amount_twd = txn["amount_twd"]
        n = len(user_ids)
        share_amount = round(amount / n, 2)
        share_twd = round(amount_twd / n)
        ratio = round(1 / n, 4)

        # 更新交易的分帳類型
        cursor.execute("UPDATE transactions SET split_type='equal' WHERE txn_id=?", (txn_id,))

        # 寫入分帳明細
        details = []
        for uid in user_ids:
            cursor.execute("""
                INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (txn_id, uid, share_amount, share_twd, ratio))
            details.append({
                "split_id": cursor.lastrowid,
                "user_id": uid,
                "share_amount": share_amount,
                "share_twd": share_twd,
                "ratio": ratio,
            })

        conn.commit()
        conn.close()
        return details

    def add_ratio_split(self, txn_id, user_ratios):
        """
        依比例分帳

        參數：
            txn_id: 交易 ID
            user_ratios: dict，{user_id: 比例}，例如 {1: 0.5, 2: 0.3, 3: 0.2}
                         比例總和必須為 1.0
        """
        # 驗證比例總和
        total_ratio = sum(user_ratios.values())
        if abs(total_ratio - 1.0) > 0.01:
            raise ValueError(f"比例總和必須為 1.0，目前為 {total_ratio}")

        conn = self._connect()
        cursor = conn.cursor()

        txn = self._get_transaction(cursor, txn_id)
        if not txn:
            conn.close()
            raise ValueError(f"找不到交易 ID={txn_id}")

        cursor.execute("UPDATE transactions SET split_type='ratio' WHERE txn_id=?", (txn_id,))

        details = []
        for uid, ratio in user_ratios.items():
            share_amount = round(txn["amount"] * ratio, 2)
            share_twd = round(txn["amount_twd"] * ratio)
            cursor.execute("""
                INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (txn_id, uid, share_amount, share_twd, round(ratio, 4)))
            details.append({
                "split_id": cursor.lastrowid,
                "user_id": uid,
                "share_amount": share_amount,
                "share_twd": share_twd,
                "ratio": ratio,
            })

        conn.commit()
        conn.close()
        return details

    def add_custom_split(self, txn_id, user_amounts):
        """
        自訂金額分帳

        參數：
            txn_id: 交易 ID
            user_amounts: dict，{user_id: 原幣金額}，例如 {1: 5000, 2: 3000, 3: 2000}
                          金額總和必須等於交易金額
        """
        conn = self._connect()
        cursor = conn.cursor()

        txn = self._get_transaction(cursor, txn_id)
        if not txn:
            conn.close()
            raise ValueError(f"找不到交易 ID={txn_id}")

        # 驗證金額總和
        total = sum(user_amounts.values())
        if abs(total - txn["amount"]) > 0.01:
            raise ValueError(f"分帳金額總和 {total} 不等於交易金額 {txn['amount']}")

        cursor.execute("UPDATE transactions SET split_type='custom' WHERE txn_id=?", (txn_id,))

        details = []
        for uid, amount in user_amounts.items():
            ratio = round(amount / txn["amount"], 4)
            share_twd = round(amount * txn["exchange_rate"])
            cursor.execute("""
                INSERT INTO split_details (txn_id, user_id, share_amount, share_twd, share_ratio, is_settled)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (txn_id, uid, amount, share_twd, ratio))
            details.append({
                "split_id": cursor.lastrowid,
                "user_id": uid,
                "share_amount": amount,
                "share_twd": share_twd,
                "ratio": ratio,
            })

        conn.commit()
        conn.close()
        return details

    # ============================================================
    #  淨餘額計算
    # ============================================================

    def get_net_balances(self, trip_id):
        """
        計算某趟旅行每個人的淨餘額

        淨餘額 = 這個人付出的總額 - 這個人該分攤的總額
        正數 = 別人欠他錢（債權人）
        負數 = 他欠別人錢（債務人）

        回傳：
            dict: {user_id: {"name": str, "paid": float, "owed": float, "balance": float}}
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 取得旅行成員
        cursor.execute("""
            SELECT tm.user_id, u.display_name
            FROM trip_members tm
            JOIN users u ON tm.user_id = u.user_id
            WHERE tm.trip_id = ?
        """, (trip_id,))
        members = {row[0]: row[1] for row in cursor.fetchall()}

        balances = {}
        for uid, name in members.items():
            # 這個人付了多少（原幣）
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE trip_id = ? AND paid_by = ?
            """, (trip_id, uid))
            total_paid = cursor.fetchone()[0]

            # 這個人該分攤多少（原幣）
            cursor.execute("""
                SELECT COALESCE(SUM(sd.share_amount), 0)
                FROM split_details sd
                JOIN transactions t ON sd.txn_id = t.txn_id
                WHERE t.trip_id = ? AND sd.user_id = ?
            """, (trip_id, uid))
            total_owed = cursor.fetchone()[0]

            balances[uid] = {
                "name": name,
                "paid": total_paid,
                "owed": total_owed,
                "balance": total_paid - total_owed,
            }

        conn.close()
        return balances

    # ============================================================
    #  最終結算（最小化轉帳次數）
    # ============================================================

    def settle_trip(self, trip_id, exchange_rate=None, currency_code="JPY"):
        """
        計算最終結算方案（最小化轉帳次數）

        使用貪心演算法：
        1. 算出每人淨餘額
        2. 分成債權人（正餘額）和債務人（負餘額）
        3. 每次讓最大債務人付給最大債權人
        4. 重複直到全部清零

        參數：
            trip_id: 旅行 ID
            exchange_rate: 結算匯率（原幣→TWD），None 則從交易紀錄取
            currency_code: 幣別代碼

        回傳：
            list[dict]: 結算方案，每筆包含 from/to/amount 等資訊
        """
        balances = self.get_net_balances(trip_id)

        # 取得匯率（如果沒指定，用該旅行最後一筆交易的匯率）
        if exchange_rate is None:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT exchange_rate FROM transactions
                WHERE trip_id = ? ORDER BY txn_datetime DESC LIMIT 1
            """, (trip_id,))
            row = cursor.fetchone()
            exchange_rate = row[0] if row else 1.0
            conn.close()

        # 分成債權人和債務人
        creditors = sorted(
            [(uid, info["balance"]) for uid, info in balances.items() if info["balance"] > 0.5],
            key=lambda x: -x[1]
        )
        debtors = sorted(
            [(uid, -info["balance"]) for uid, info in balances.items() if info["balance"] < -0.5],
            key=lambda x: -x[1]
        )

        # 貪心演算法
        transfers = []
        i, j = 0, 0
        while i < len(creditors) and j < len(debtors):
            creditor_id, credit = creditors[i]
            debtor_id, debt = debtors[j]
            amount = min(credit, debt)

            transfers.append({
                "from_user": debtor_id,
                "from_name": balances[debtor_id]["name"],
                "to_user": creditor_id,
                "to_name": balances[creditor_id]["name"],
                "amount": round(amount, 2),
                "amount_twd": round(amount * exchange_rate),
                "currency_code": currency_code,
                "exchange_rate": exchange_rate,
            })

            creditors[i] = (creditor_id, credit - amount)
            debtors[j] = (debtor_id, debt - amount)

            if creditors[i][1] < 0.5:
                i += 1
            if debtors[j][1] < 0.5:
                j += 1

        return transfers

    def save_settlements(self, trip_id, transfers):
        """
        將結算方案寫入資料庫

        參數：
            trip_id: 旅行 ID
            transfers: settle_trip() 回傳的結算列表
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 清除該旅行的舊結算紀錄
        cursor.execute("DELETE FROM settlements WHERE trip_id = ?", (trip_id,))

        for t in transfers:
            cursor.execute("""
                INSERT INTO settlements
                (trip_id, from_user, to_user, amount, currency_code, amount_twd, exchange_rate, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                trip_id, t["from_user"], t["to_user"],
                t["amount"], t["currency_code"], t["amount_twd"], t["exchange_rate"]
            ))

        # 標記所有分帳明細為未結清
        cursor.execute("""
            UPDATE split_details SET is_settled = 0
            WHERE txn_id IN (SELECT txn_id FROM transactions WHERE trip_id = ?)
        """, (trip_id,))

        conn.commit()
        conn.close()
        return len(transfers)

    def mark_settled(self, settlement_id):
        """
        標記某筆結算為已完成

        參數：
            settlement_id: 結算紀錄 ID
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE settlements
            SET status = 'completed', settled_at = datetime('now')
            WHERE settlement_id = ?
        """, (settlement_id,))
        conn.commit()
        conn.close()

    # ============================================================
    #  查詢功能
    # ============================================================

    def get_trip_summary(self, trip_id):
        """
        取得某趟旅行的分帳摘要

        回傳：
            dict: 包含總花費、各人代墊、各類別消費等摘要
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 總花費
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(SUM(amount_twd), 0)
            FROM transactions WHERE trip_id = ?
        """, (trip_id,))
        txn_count, total_amount, total_twd = cursor.fetchone()

        # 各人代墊
        cursor.execute("""
            SELECT u.display_name, COUNT(*), SUM(t.amount), SUM(t.amount_twd)
            FROM transactions t
            JOIN users u ON t.paid_by = u.user_id
            WHERE t.trip_id = ?
            GROUP BY t.paid_by ORDER BY SUM(t.amount) DESC
        """, (trip_id,))
        payers = [
            {"name": r[0], "count": r[1], "amount": r[2], "amount_twd": r[3]}
            for r in cursor.fetchall()
        ]

        # 各類別消費
        cursor.execute("""
            SELECT category, COUNT(*), SUM(amount), SUM(amount_twd)
            FROM transactions WHERE trip_id = ?
            GROUP BY category ORDER BY SUM(amount) DESC
        """, (trip_id,))
        categories = [
            {"category": r[0], "count": r[1], "amount": r[2], "amount_twd": r[3]}
            for r in cursor.fetchall()
        ]

        # 未結清金額
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount_twd), 0)
            FROM settlements
            WHERE trip_id = ? AND status = 'pending'
        """, (trip_id,))
        pending_count, pending_twd = cursor.fetchone()

        conn.close()

        return {
            "txn_count": txn_count,
            "total_amount": total_amount,
            "total_twd": total_twd,
            "payers": payers,
            "categories": categories,
            "pending_settlements": pending_count,
            "pending_twd": pending_twd,
        }

    # ============================================================
    #  工具函式
    # ============================================================

    def _get_transaction(self, cursor, txn_id):
        """取得單筆交易資訊"""
        cursor.execute("""
            SELECT txn_id, trip_id, paid_by, amount, currency_code,
                   amount_twd, exchange_rate, category, split_type
            FROM transactions WHERE txn_id = ?
        """, (txn_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "txn_id": row[0], "trip_id": row[1], "paid_by": row[2],
            "amount": row[3], "currency_code": row[4],
            "amount_twd": row[5], "exchange_rate": row[6],
            "category": row[7], "split_type": row[8],
        }


# ============================================================
#  測試 / Demo
# ============================================================

if __name__ == "__main__":
    print("🧳 TravelWallet - 分帳引擎測試")
    print("=" * 50)

    engine = SplitEngine()

    # 用種子資料的旅行 (trip_id=1) 測試
    trip_id = 1

    # --- 淨餘額 ---
    print("\n💰 淨餘額計算:")
    print("-" * 40)
    balances = engine.get_net_balances(trip_id)
    for uid, info in balances.items():
        symbol = "💚" if info["balance"] > 0 else "🔴"
        print(f"  {info['name']}: 付了 ¥{info['paid']:,.0f}, 該付 ¥{info['owed']:,.0f}, "
              f"淨額 ¥{info['balance']:,.0f} {symbol}")

    # --- 最終結算 ---
    print("\n🧮 最終結算（最小化轉帳）:")
    print("-" * 40)
    transfers = engine.settle_trip(trip_id)
    for t in transfers:
        print(f"  💸 {t['from_name']} → {t['to_name']}: "
              f"¥{t['amount']:,.0f} (NT${t['amount_twd']:,})")
    print(f"\n  只需要 {len(transfers)} 筆轉帳！")

    # --- 旅行摘要 ---
    print("\n📊 旅行摘要:")
    print("-" * 40)
    summary = engine.get_trip_summary(trip_id)
    print(f"  總交易: {summary['txn_count']} 筆")
    print(f"  總花費: ¥{summary['total_amount']:,.0f} (NT${summary['total_twd']:,.0f})")
    print(f"\n  各類別:")
    for c in summary["categories"]:
        pct = c["amount"] / summary["total_amount"] * 100
        print(f"    {c['category']}: ¥{c['amount']:,.0f} ({pct:.1f}%)")
    print(f"\n  各人代墊:")
    for p in summary["payers"]:
        print(f"    {p['name']}: {p['count']} 次, ¥{p['amount']:,.0f}")

    print("\n🎉 分帳引擎測試完成！")

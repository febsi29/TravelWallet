"""
split.py - 


-  /  / 
- 
- Greedy Netting
- 
- 


  from src.split import SplitEngine
  engine = SplitEngine(db_path)
  engine.add_equal_split(txn_id, user_ids)
  result = engine.settle_trip(trip_id)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


class SplitEngine:
    """"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn, conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ============================================================
    #  
    # ============================================================

    def add_equal_split(self, txn_id: int, user_ids: list) -> list:
        """
        

        
            txn_id:  ID
            user_ids:  ID 
        
            list[dict]: 
        """
        if not isinstance(txn_id, int) or txn_id <= 0:
            raise ValueError(f"txn_id : {txn_id!r}")
        if not user_ids:
            raise ValueError("user_ids ")

        with self._db() as (conn, cursor):
            txn = self._get_transaction(cursor, txn_id)
            if not txn:
                raise ValueError(f" ID={txn_id}")

            amount = txn["amount"]
            amount_twd = txn["amount_twd"]
            n = len(user_ids)
            share_amount = round(amount / n, 2)
            share_twd = round(amount_twd / n)
            ratio = round(1 / n, 4)

            cursor.execute("UPDATE transactions SET split_type='equal' WHERE txn_id=?", (txn_id,))

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

        return details

    def add_ratio_split(self, txn_id: int, user_ratios: dict) -> list:
        """
        

        
            txn_id:  ID
            user_ratios: dict{user_id: } {1: 0.5, 2: 0.3, 3: 0.2}
                          1.0
        """
        if not isinstance(txn_id, int) or txn_id <= 0:
            raise ValueError(f"txn_id : {txn_id!r}")
        if not user_ratios:
            raise ValueError("user_ratios ")

        total_ratio = sum(user_ratios.values())
        if abs(total_ratio - 1.0) > 0.01:
            raise ValueError(f" 1.0 {total_ratio}")

        with self._db() as (conn, cursor):
            txn = self._get_transaction(cursor, txn_id)
            if not txn:
                raise ValueError(f" ID={txn_id}")

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

        return details

    def add_custom_split(self, txn_id: int, user_amounts: dict) -> list:
        """
        

        
            txn_id:  ID
            user_amounts: dict{user_id: } {1: 5000, 2: 3000, 3: 2000}
                          
        """
        if not isinstance(txn_id, int) or txn_id <= 0:
            raise ValueError(f"txn_id : {txn_id!r}")
        if not user_amounts:
            raise ValueError("user_amounts ")

        with self._db() as (conn, cursor):
            txn = self._get_transaction(cursor, txn_id)
            if not txn:
                raise ValueError(f" ID={txn_id}")

            total = sum(user_amounts.values())
            if abs(total - txn["amount"]) > 0.01:
                raise ValueError(f" {total}  {txn['amount']}")

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

        return details

    # ============================================================
    #  
    # ============================================================

    def get_net_balances(self, trip_id: int) -> dict:
        """
        

         =  - 
         = 
         = 

        
            dict: {user_id: {"name": str, "paid": float, "owed": float, "balance": float}}
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT tm.user_id, u.display_name
                FROM trip_members tm
                JOIN users u ON tm.user_id = u.user_id
                WHERE tm.trip_id = ?
            """, (trip_id,))
            members = {row[0]: row[1] for row in cursor.fetchall()}

            balances = {}
            for uid, name in members.items():
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE trip_id = ? AND paid_by = ?
                """, (trip_id, uid))
                total_paid = cursor.fetchone()[0]

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

        return balances

    # ============================================================
    #  
    # ============================================================

    def settle_trip(self, trip_id: int, exchange_rate: float = None, currency_code: str = "JPY") -> list:
        """
        

        
        1. 
        2. 
        3. 
        4. 

        
            trip_id:  ID
            exchange_rate: →TWDNone 
            currency_code: 

        
            list[dict]:  from/to/amount 
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        balances = self.get_net_balances(trip_id)

        if exchange_rate is None:
            with self._db() as (conn, cursor):
                cursor.execute("""
                    SELECT exchange_rate FROM transactions
                    WHERE trip_id = ? ORDER BY txn_datetime DESC LIMIT 1
                """, (trip_id,))
                row = cursor.fetchone()
                exchange_rate = row[0] if row else 1.0

        creditors = sorted(
            [(uid, info["balance"]) for uid, info in balances.items() if info["balance"] > 0.5],
            key=lambda x: -x[1]
        )
        debtors = sorted(
            [(uid, -info["balance"]) for uid, info in balances.items() if info["balance"] < -0.5],
            key=lambda x: -x[1]
        )

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

    def save_settlements(self, trip_id: int, transfers: list) -> int:
        """
        

        
            trip_id:  ID
            transfers: settle_trip() 
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
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

            cursor.execute("""
                UPDATE split_details SET is_settled = 0
                WHERE txn_id IN (SELECT txn_id FROM transactions WHERE trip_id = ?)
            """, (trip_id,))

        return len(transfers)

    def mark_settled(self, settlement_id: int) -> None:
        """
        

        
            settlement_id:  ID
        """
        if not isinstance(settlement_id, int) or settlement_id <= 0:
            raise ValueError(f"settlement_id : {settlement_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                UPDATE settlements
                SET status = 'completed', settled_at = datetime('now')
                WHERE settlement_id = ?
            """, (settlement_id,))

    # ============================================================
    #  
    # ============================================================

    def get_trip_summary(self, trip_id: int) -> dict:
        """
        

        
            dict: 
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(SUM(amount_twd), 0)
                FROM transactions WHERE trip_id = ?
            """, (trip_id,))
            txn_count, total_amount, total_twd = cursor.fetchone()

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

            cursor.execute("""
                SELECT category, COUNT(*), SUM(amount), SUM(amount_twd)
                FROM transactions WHERE trip_id = ?
                GROUP BY category ORDER BY SUM(amount) DESC
            """, (trip_id,))
            categories = [
                {"category": r[0], "count": r[1], "amount": r[2], "amount_twd": r[3]}
                for r in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(amount_twd), 0)
                FROM settlements
                WHERE trip_id = ? AND status = 'pending'
            """, (trip_id,))
            pending_count, pending_twd = cursor.fetchone()

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
    #  
    # ============================================================

    def _get_transaction(self, cursor, txn_id: int) -> dict | None:
        """"""
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


if __name__ == "__main__":
    print("TravelWallet - ")
    print("=" * 50)

    engine = SplitEngine()
    trip_id = 1

    print("\n:")
    balances = engine.get_net_balances(trip_id)
    for uid, info in balances.items():
        symbol = "+" if info["balance"] > 0 else "-"
        print(f"  {info['name']}:  {info['paid']:,.0f},  {info['owed']:,.0f},  {info['balance']:,.0f} {symbol}")

    print("\n:")
    transfers = engine.settle_trip(trip_id)
    for t in transfers:
        print(f"  {t['from_name']} -> {t['to_name']}: {t['amount']:,.0f} (NT${t['amount_twd']:,})")
    print(f"\n   {len(transfers)} ")

    print("\nDone!")

"""
credit_score.py - 


-  0-100
- budget_score
- anomaly_score
- settle_score
- category_score
- 


  from src.credit_score import CreditScoreEngine
  engine = CreditScoreEngine(db_path)
  result = engine.evaluate(user_id=1, trip_id=1)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

#  = 1.0
SCORE_WEIGHTS = {
    "budget":   0.35,
    "anomaly":  0.25,
    "settle":   0.25,
    "category": 0.15,
}

# 
NATIONAL_CATEGORY_RATIOS = {
    "": 0.28,
    "": 0.25,
    "": 0.18,
    "": 0.18,
    "": 0.06,
    "": 0.05,
}


class CreditScoreEngine:
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

    def _score_budget(self, trip_id: int) -> int:
        """
         (0-100)

         /  1 
        """
        with self._db() as (conn, cursor):
            cursor.execute("SELECT total_budget FROM trips WHERE trip_id = ?", (trip_id,))
            row = cursor.fetchone()
            if not row or not row[0]:
                return 60  # 

            budget = row[0]

            cursor.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,))
            num_members = cursor.fetchone()[0] or 1

            cursor.execute(
                "SELECT COALESCE(SUM(amount_twd), 0) FROM transactions WHERE trip_id = ?",
                (trip_id,)
            )
            total_spent = cursor.fetchone()[0]

        per_person_spent = total_spent / num_members
        usage_ratio = per_person_spent / budget if budget > 0 else 1.0

        if usage_ratio <= 0.7:
            return 100
        elif usage_ratio <= 0.85:
            return 90
        elif usage_ratio <= 1.0:
            return 75
        elif usage_ratio <= 1.1:
            return 55
        elif usage_ratio <= 1.3:
            return 35
        else:
            return 10

    def _score_anomaly(self, trip_id: int) -> int:
        """
         (0-100)

        
        """
        with self._db() as (conn, cursor):
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE trip_id = ?", (trip_id,))
            total = cursor.fetchone()[0]

            if total == 0:
                return 100

            cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE trip_id = ? AND is_anomaly = 1",
                (trip_id,)
            )
            anomaly_count = cursor.fetchone()[0]

        anomaly_rate = anomaly_count / total

        if anomaly_rate == 0:
            return 100
        elif anomaly_rate <= 0.05:
            return 85
        elif anomaly_rate <= 0.10:
            return 70
        elif anomaly_rate <= 0.20:
            return 50
        elif anomaly_rate <= 0.30:
            return 30
        else:
            return 10

    def _score_settle(self, trip_id: int) -> int:
        """
         (0-100)

         /  
        """
        with self._db() as (conn, cursor):
            cursor.execute("SELECT COUNT(*) FROM settlements WHERE trip_id = ?", (trip_id,))
            total_settlements = cursor.fetchone()[0]

            if total_settlements == 0:
                return 100  # 

            cursor.execute(
                "SELECT COUNT(*) FROM settlements WHERE trip_id = ? AND status = 'completed'",
                (trip_id,)
            )
            completed = cursor.fetchone()[0]

        return round(completed / total_settlements * 100)

    def _score_category(self, trip_id: int) -> int:
        """
         (0-100)

        1 - 
        """
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT category, SUM(amount_twd) FROM transactions
                WHERE trip_id = ?
                GROUP BY category
            """, (trip_id,))
            rows = cursor.fetchall()

        if not rows:
            return 60

        total = sum(r[1] for r in rows)
        personal_ratios = {r[0]: r[1] / total for r in rows}

        total_diff = sum(
            abs(personal_ratios.get(cat, 0.0) - national_ratio)
            for cat, national_ratio in NATIONAL_CATEGORY_RATIOS.items()
        )

        # total_diff  2.0 0
        similarity = max(0.0, 1.0 - total_diff)
        return round(similarity * 100)

    # ============================================================
    #  
    # ============================================================

    def evaluate(self, user_id: int, trip_id: int) -> dict:
        """
        

        
            user_id:  ID
            trip_id:  ID

        
            dict: 
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id : {user_id!r}")
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        budget_score   = self._score_budget(trip_id)
        anomaly_score  = self._score_anomaly(trip_id)
        settle_score   = self._score_settle(trip_id)
        category_score = self._score_category(trip_id)

        overall = round(
            budget_score   * SCORE_WEIGHTS["budget"]   +
            anomaly_score  * SCORE_WEIGHTS["anomaly"]  +
            settle_score   * SCORE_WEIGHTS["settle"]   +
            category_score * SCORE_WEIGHTS["category"]
        )

        if overall >= 90:
            grade, label = "A", ""
        elif overall >= 75:
            grade, label = "B", ""
        elif overall >= 60:
            grade, label = "C", ""
        elif overall >= 40:
            grade, label = "D", ""
        else:
            grade, label = "F", ""

        result = {
            "user_id": user_id,
            "trip_id": trip_id,
            "overall_score": overall,
            "grade": grade,
            "label": label,
            "details": {
                "budget_score":   budget_score,
                "anomaly_score":  anomaly_score,
                "settle_score":   settle_score,
                "category_score": category_score,
            },
            "weights": SCORE_WEIGHTS,
        }

        self._save_score(result)
        return result

    def _save_score(self, result: dict) -> None:
        """"""
        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT INTO credit_scores
                (user_id, trip_id, overall_score, budget_score, anomaly_score,
                 settle_score, category_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result["user_id"],
                result["trip_id"],
                result["overall_score"],
                result["details"]["budget_score"],
                result["details"]["anomaly_score"],
                result["details"]["settle_score"],
                result["details"]["category_score"],
            ))

    def get_history(self, user_id: int, limit: int = 10) -> list:
        """
        

        
            user_id:  ID
            limit: 

        
            list[dict]: 
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id : {user_id!r}")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit : {limit!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT cs.score_id, cs.trip_id, t.destination,
                       cs.overall_score, cs.budget_score, cs.anomaly_score,
                       cs.settle_score, cs.category_score, cs.evaluated_at
                FROM credit_scores cs
                LEFT JOIN trips t ON cs.trip_id = t.trip_id
                WHERE cs.user_id = ?
                ORDER BY cs.evaluated_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

        return [
            {
                "score_id":      r[0],
                "trip_id":       r[1],
                "destination":   r[2],
                "overall_score": r[3],
                "budget_score":  r[4],
                "anomaly_score": r[5],
                "settle_score":  r[6],
                "category_score":r[7],
                "evaluated_at":  r[8],
            }
            for r in rows
        ]


if __name__ == "__main__":
    print("TravelWallet - ")
    print("=" * 55)

    engine = CreditScoreEngine()
    result = engine.evaluate(user_id=1, trip_id=1)

    print(f"\n #{result['user_id']} -  #{result['trip_id']}")
    print(f": {result['overall_score']}/100  [{result['grade']}] {result['label']}")
    print(f"\n:")
    for dim, score in result["details"].items():
        key = dim.replace("_score", "")
        weight = result["weights"].get(key, 0)
        print(f"  {dim:20s}: {score:3d}/100  ( {weight:.0%})")

    print("\nDone!")

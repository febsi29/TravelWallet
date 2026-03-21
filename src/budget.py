"""
budget.py - Budget Management and Prediction Module

Features:
- Budget burndown chart data
- Remaining spending prediction (linear regression)
- Daily spending limit suggestion
- Budget health assessment

Usage:
  from src.budget import BudgetManager
  bm = BudgetManager(db_path)
  burndown = bm.get_burndown(trip_id=1)
  prediction = bm.predict_remaining(trip_id=1)
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


class BudgetManager:

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

    def _get_trip_info(self, trip_id: int) -> dict:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT trip_name, destination, start_date, end_date, total_budget,
                       julianday(end_date) - julianday(start_date) + 1 AS total_days
                FROM trips WHERE trip_id = ?
            """, (trip_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"Trip ID={trip_id} not found")
        return {
            "name": row[0], "destination": row[1],
            "start_date": row[2], "end_date": row[3],
            "budget": row[4], "total_days": int(row[5]),
        }

    # ============================================================
    #  Budget Burndown
    # ============================================================

    def get_burndown(self, trip_id: int) -> dict:
        """
        Generate budget burndown chart data.

        Returns a list of daily entries showing:
        - planned budget remaining (linear decrease)
        - actual budget remaining
        - daily spending
        """
        trip = self._get_trip_info(trip_id)
        budget = trip["budget"]
        total_days = trip["total_days"]
        daily_planned = budget / total_days if total_days > 0 else 0

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT DATE(txn_datetime) AS day, SUM(amount_twd) AS daily_total
                FROM transactions WHERE trip_id = ?
                GROUP BY DATE(txn_datetime) ORDER BY day
            """, (trip_id,))
            daily_spending = {r[0]: r[1] for r in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,))
            num_members = cursor.fetchone()[0] or 1

        start = datetime.strptime(trip["start_date"], "%Y-%m-%d")
        burndown = []
        actual_remaining = budget
        cumulative_spent = 0

        for i in range(total_days):
            current_date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            planned_remaining = budget - daily_planned * (i + 1)

            day_spent_total = daily_spending.get(current_date, 0)
            day_spent_per_person = round(day_spent_total / num_members)
            actual_remaining -= day_spent_per_person
            cumulative_spent += day_spent_per_person

            burndown.append({
                "day": i + 1,
                "date": current_date,
                "planned_remaining": round(planned_remaining),
                "actual_remaining": round(actual_remaining),
                "daily_spent": day_spent_per_person,
                "cumulative_spent": cumulative_spent,
                "on_track": actual_remaining >= planned_remaining,
            })

        return {
            "trip": trip,
            "num_members": num_members,
            "daily_planned": round(daily_planned),
            "burndown": burndown,
        }

    # ============================================================
    #  Spending Prediction
    # ============================================================

    def predict_remaining(self, trip_id: int, current_day: int = None) -> dict:
        """
        Predict total spending using linear regression on daily spending data.

        Uses least squares: y = a + b*x
        where x = day number, y = cumulative spending
        """
        burndown_data = self.get_burndown(trip_id)
        trip = burndown_data["trip"]
        burndown = burndown_data["burndown"]
        total_days = trip["total_days"]

        if current_day is None:
            current_day = total_days
        elif not isinstance(current_day, int) or current_day < 1:
            raise ValueError(f"current_day 必須為正整數，收到: {current_day!r}")

        points = [(b["day"], b["cumulative_spent"]) for b in burndown[:current_day]]
        if len(points) < 2:
            return {"error": "Need at least 2 days of data"}

        n = len(points)
        sum_x = sum(p[0] for p in points)
        sum_y = sum(p[1] for p in points)
        sum_xy = sum(p[0] * p[1] for p in points)
        sum_x2 = sum(p[0] ** 2 for p in points)

        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            b = 0
            a = sum_y / n
        else:
            b = (n * sum_xy - sum_x * sum_y) / denominator
            a = (sum_y - b * sum_x) / n

        predicted_total = a + b * total_days
        actual_so_far = points[-1][1]
        predicted_remaining = max(0, predicted_total - actual_so_far)
        daily_rate = round(b)

        prediction_line = [
            {"day": day, "predicted_cumulative": round(a + b * day)}
            for day in range(1, total_days + 1)
        ]

        return {
            "current_day": current_day,
            "days_remaining": total_days - current_day,
            "actual_spent": round(actual_so_far),
            "predicted_total": round(predicted_total),
            "predicted_remaining": round(predicted_remaining),
            "daily_rate": daily_rate,
            "budget": trip["budget"],
            "predicted_vs_budget": round(predicted_total - trip["budget"]),
            "will_exceed": predicted_total > trip["budget"],
            "prediction_line": prediction_line,
        }

    # ============================================================
    #  Daily Limit Suggestion
    # ============================================================

    def suggest_daily_limit(self, trip_id: int, current_day: int = None) -> dict:
        """
        Suggest a daily spending limit for remaining days
        to stay within budget.
        """
        burndown_data = self.get_burndown(trip_id)
        trip = burndown_data["trip"]
        burndown = burndown_data["burndown"]
        total_days = trip["total_days"]

        if current_day is None:
            current_day = total_days
        elif not isinstance(current_day, int) or current_day < 1:
            raise ValueError(f"current_day 必須為正整數，收到: {current_day!r}")

        if current_day >= total_days:
            spent = burndown[-1]["cumulative_spent"] if burndown else 0
            return {
                "status": "trip_completed",
                "total_spent": spent,
                "budget": trip["budget"],
                "remaining": trip["budget"] - spent,
            }

        spent_so_far = burndown[current_day - 1]["cumulative_spent"] if current_day > 0 else 0
        remaining_budget = trip["budget"] - spent_so_far
        remaining_days = total_days - current_day
        suggested_limit = round(remaining_budget / remaining_days) if remaining_days > 0 else 0

        original_daily = round(trip["budget"] / total_days)

        return {
            "current_day": current_day,
            "days_remaining": remaining_days,
            "spent_so_far": spent_so_far,
            "remaining_budget": round(remaining_budget),
            "suggested_daily_limit": max(0, suggested_limit),
            "original_daily_budget": original_daily,
            "limit_vs_original": suggested_limit - original_daily,
            "status": "on_track" if remaining_budget >= 0 else "over_budget",
        }

    # ============================================================
    #  Budget Health Assessment
    # ============================================================

    def assess_health(self, trip_id: int) -> dict:
        """
        Overall budget health assessment.
        Score from 0-100.
        """
        burndown_data = self.get_burndown(trip_id)
        trip = burndown_data["trip"]
        burndown = burndown_data["burndown"]

        if not burndown:
            return {"score": 100, "status": "no data"}

        budget = trip["budget"]
        total_spent = burndown[-1]["cumulative_spent"]
        usage_ratio = total_spent / budget if budget > 0 else 0

        if usage_ratio <= 0.7:
            score = 100
            status = "Excellent - well under budget"
        elif usage_ratio <= 0.9:
            score = 85
            status = "Good - within budget"
        elif usage_ratio <= 1.0:
            score = 70
            status = "OK - close to budget limit"
        elif usage_ratio <= 1.1:
            score = 50
            status = "Warning - slightly over budget"
        elif usage_ratio <= 1.3:
            score = 30
            status = "Over budget"
        else:
            score = 10
            status = "Significantly over budget"

        daily_amounts = [b["daily_spent"] for b in burndown if b["daily_spent"] > 0]
        if len(daily_amounts) >= 2:
            mean = sum(daily_amounts) / len(daily_amounts)
            variance = sum((x - mean) ** 2 for x in daily_amounts) / len(daily_amounts)
            cv = (variance ** 0.5) / mean if mean > 0 else 0
            consistency_bonus = max(0, 10 - int(cv * 10))
            score = min(100, score + consistency_bonus)

        on_track_days = sum(1 for b in burndown if b["on_track"])
        on_track_pct = round(on_track_days / len(burndown) * 100)

        return {
            "score": score,
            "status": status,
            "budget": budget,
            "total_spent": total_spent,
            "usage_ratio": round(usage_ratio * 100, 1),
            "on_track_days": on_track_days,
            "on_track_pct": on_track_pct,
            "total_days": len(burndown),
        }


if __name__ == "__main__":
    print("TravelWallet - Budget Management Test")
    print("=" * 60)

    bm = BudgetManager()
    trip_id = 1

    print("\n[1] Budget Burndown Chart")
    bd = bm.get_burndown(trip_id)
    trip = bd["trip"]
    print(f"  Trip: {trip['name']}  Budget: NT${trip['budget']:,} / {trip['total_days']} days")
    for b in bd["burndown"]:
        status = "OK" if b["on_track"] else "OVER"
        print(f"  Day {b['day']} {b['date']}: NT${b['daily_spent']:>7,}  cum NT${b['cumulative_spent']:>9,}  {status}")

    print("\n[2] Health Assessment")
    health = bm.assess_health(trip_id)
    print(f"  Score: {health['score']}/100  Status: {health['status']}")

    print("\nDone!")

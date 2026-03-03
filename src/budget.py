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
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


class BudgetManager:

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _get_trip_info(self, trip_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT trip_name, destination, start_date, end_date, total_budget,
                   julianday(end_date) - julianday(start_date) + 1 AS total_days
            FROM trips WHERE trip_id = ?
        """, (trip_id,))
        row = cursor.fetchone()
        conn.close()
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

    def get_burndown(self, trip_id):
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

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE(txn_datetime) AS day, SUM(amount_twd) AS daily_total
            FROM transactions WHERE trip_id = ?
            GROUP BY DATE(txn_datetime) ORDER BY day
        """, (trip_id,))
        daily_spending = {r[0]: r[1] for r in cursor.fetchall()}

        # Per-person spending (divide by member count)
        cursor.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,))
        num_members = cursor.fetchone()[0] or 1
        conn.close()

        # Generate burndown data
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

    def predict_remaining(self, trip_id, current_day=None):
        """
        Predict total spending using linear regression on daily spending data.

        Uses least squares: y = a + b*x
        where x = day number, y = cumulative spending
        """
        burndown_data = self.get_burndown(trip_id)
        trip = burndown_data["trip"]
        burndown = burndown_data["burndown"]
        total_days = trip["total_days"]

        # Determine current day
        if current_day is None:
            current_day = total_days  # assume trip is complete

        # Get data points up to current day
        points = [(b["day"], b["cumulative_spent"]) for b in burndown[:current_day]]
        if len(points) < 2:
            return {"error": "Need at least 2 days of data"}

        # Linear regression (least squares)
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
            b = (n * sum_xy - sum_x * sum_y) / denominator  # slope (daily rate)
            a = (sum_y - b * sum_x) / n  # intercept

        # Predict for remaining days
        predicted_total = a + b * total_days
        actual_so_far = points[-1][1]
        predicted_remaining = max(0, predicted_total - actual_so_far)
        daily_rate = round(b)

        # Generate prediction line
        prediction_line = []
        for day in range(1, total_days + 1):
            prediction_line.append({
                "day": day,
                "predicted_cumulative": round(a + b * day),
            })

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

    def suggest_daily_limit(self, trip_id, current_day=None):
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

    def assess_health(self, trip_id):
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

        # Score based on budget usage
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

        # Check daily consistency (lower variance = higher bonus)
        daily_amounts = [b["daily_spent"] for b in burndown if b["daily_spent"] > 0]
        if len(daily_amounts) >= 2:
            mean = sum(daily_amounts) / len(daily_amounts)
            variance = sum((x - mean) ** 2 for x in daily_amounts) / len(daily_amounts)
            cv = (variance ** 0.5) / mean if mean > 0 else 0  # coefficient of variation
            consistency_bonus = max(0, 10 - int(cv * 10))
            score = min(100, score + consistency_bonus)

        # Days on track
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

    # === 1. Burndown ===
    print("\n[1] Budget Burndown Chart")
    print("=" * 60)
    bd = bm.get_burndown(trip_id)
    trip = bd["trip"]
    print(f"  Trip: {trip['name']}")
    print(f"  Budget: NT${trip['budget']:,} / {trip['total_days']} days")
    print(f"  Members: {bd['num_members']} (budget is per person)")
    print(f"  Planned daily: NT${bd['daily_planned']:,}/person")
    print(f"")
    print(f"  {'Day':>4} {'Date':>12} {'Spent':>10} {'Cumulative':>12} {'Planned':>10} {'Actual':>10} {'Status'}")
    print(f"  {'-'*72}")
    for b in bd["burndown"]:
        status = "OK" if b["on_track"] else "OVER"
        print(f"  {b['day']:>4} {b['date']:>12} NT${b['daily_spent']:>7,} NT${b['cumulative_spent']:>9,} "
              f"NT${b['planned_remaining']:>7,} NT${b['actual_remaining']:>7,}  {status}")

    # === 2. Prediction ===
    print(f"\n\n[2] Spending Prediction")
    print("=" * 60)

    # Predict at Day 3 (mid-trip)
    pred = bm.predict_remaining(trip_id, current_day=3)
    print(f"  Predicting at Day {pred['current_day']} (3 days in, {pred['days_remaining']} remaining)")
    print(f"  Spent so far: NT${pred['actual_spent']:,}")
    print(f"  Daily rate: NT${pred['daily_rate']:,}/day")
    print(f"  Predicted total: NT${pred['predicted_total']:,}")
    print(f"  Budget: NT${pred['budget']:,}")
    diff = pred['predicted_vs_budget']
    if pred['will_exceed']:
        print(f"  Forecast: OVER budget by NT${diff:,}")
    else:
        print(f"  Forecast: Under budget by NT${abs(diff):,}")

    # Predict at end of trip
    pred_end = bm.predict_remaining(trip_id, current_day=5)
    print(f"\n  End of trip prediction:")
    print(f"  Final total: NT${pred_end['predicted_total']:,}")
    print(f"  Budget: NT${pred_end['budget']:,}")

    # === 3. Daily Limit ===
    print(f"\n\n[3] Daily Spending Limit Suggestion")
    print("=" * 60)
    for day in range(1, 6):
        limit = bm.suggest_daily_limit(trip_id, current_day=day)
        if limit.get("status") == "trip_completed":
            remaining = limit["remaining"]
            print(f"  Day {day}: Trip complete! Remaining NT${remaining:,}")
        else:
            diff = limit["limit_vs_original"]
            arrow = "same" if diff == 0 else (f"+{diff:,}" if diff > 0 else f"{diff:,}")
            print(f"  After Day {day}: budget left NT${limit['remaining_budget']:,}, "
                  f"suggest NT${limit['suggested_daily_limit']:,}/day ({arrow} vs planned)")

    # === 4. Health Assessment ===
    print(f"\n\n[4] Budget Health Assessment")
    print("=" * 60)
    health = bm.assess_health(trip_id)
    bar_filled = "#" * (health["score"] // 5)
    bar_empty = "-" * (20 - health["score"] // 5)
    print(f"  Score: {health['score']}/100 [{bar_filled}{bar_empty}]")
    print(f"  Status: {health['status']}")
    print(f"  Budget: NT${health['budget']:,}")
    print(f"  Spent: NT${health['total_spent']:,} ({health['usage_ratio']}%)")
    print(f"  On track: {health['on_track_days']}/{health['total_days']} days ({health['on_track_pct']}%)")

    print("\nDone!")

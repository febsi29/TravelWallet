"""
analytics.py - data analysis module

Features:
- Personal vs national average comparison
- Category analysis (personal vs national)
- Daily spending trend
- Split behavior analysis
- Payment method analysis
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


class Analytics:

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

    def personal_vs_national(self, trip_id: int) -> dict:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT t.start_date, t.end_date, t.destination,
                       julianday(t.end_date) - julianday(t.start_date) + 1 AS days
                FROM trips t WHERE t.trip_id = ?
            """, (trip_id,))
            trip = cursor.fetchone()
            if not trip:
                raise ValueError(f"Trip ID={trip_id} not found")

            start_date, end_date, destination, trip_days = trip

            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(amount_twd), 0)
                FROM transactions WHERE trip_id = ?
            """, (trip_id,))
            txn_count, total_twd = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,))
            num_members = cursor.fetchone()[0]

            per_person_total = round(total_twd / num_members) if num_members > 0 else total_twd
            per_person_daily = round(per_person_total / trip_days) if trip_days > 0 else 0

            trip_year = int(start_date[:4])
            cursor.execute("""
                SELECT avg_spending_twd, avg_stay_nights
                FROM gov_outbound_stats
                WHERE year = ? AND avg_spending_twd IS NOT NULL
            """, (trip_year,))
            gov = cursor.fetchone()

            if not gov:
                cursor.execute("""
                    SELECT avg_spending_twd, avg_stay_nights, year
                    FROM gov_outbound_stats
                    WHERE avg_spending_twd IS NOT NULL
                    ORDER BY year DESC LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    gov = (row[0], row[1])
                    trip_year = row[2]

        national_total = gov[0] if gov else 0
        national_nights = gov[1] if gov else 1
        national_daily = round(national_total / national_nights) if national_nights > 0 else 0

        diff_total = per_person_total - national_total
        diff_pct = round((per_person_total / national_total - 1) * 100, 1) if national_total > 0 else 0
        diff_daily = per_person_daily - national_daily

        if diff_pct < -30:
            verdict = "super saving - far below national average"
        elif diff_pct < -10:
            verdict = "below national average"
        elif diff_pct < 10:
            verdict = "close to national average"
        elif diff_pct < 30:
            verdict = "above national average"
        else:
            verdict = "luxury trip - far above national average"

        return {
            "trip": {
                "destination": destination, "days": int(trip_days),
                "members": num_members, "txn_count": txn_count,
                "start_date": start_date, "end_date": end_date,
            },
            "personal": {
                "total_twd": total_twd,
                "per_person_total": per_person_total,
                "per_person_daily": per_person_daily,
            },
            "national": {
                "year": trip_year, "avg_total": national_total,
                "avg_nights": national_nights, "avg_daily": national_daily,
            },
            "comparison": {
                "diff_total": diff_total, "diff_pct": diff_pct,
                "diff_daily": diff_daily, "verdict": verdict,
            },
        }

    def category_analysis(self, trip_id: int) -> list:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT category, COUNT(*), SUM(amount), SUM(amount_twd)
                FROM transactions WHERE trip_id = ?
                GROUP BY category ORDER BY SUM(amount_twd) DESC
            """, (trip_id,))
            rows = cursor.fetchall()
            cursor.execute("SELECT SUM(amount_twd) FROM transactions WHERE trip_id = ?", (trip_id,))
            grand_total = cursor.fetchone()[0] or 1

        return [
            {"category": r[0], "count": r[1], "total_original": r[2],
             "total_twd": r[3], "percentage": round(r[3] / grand_total * 100, 1)}
            for r in rows
        ]

    def category_vs_national(self, trip_id: int) -> list:
        national_ratios = {
            "": 28.0, "": 25.0, "": 18.0,
            "": 18.0, "": 6.0, "": 5.0,
        }
        personal = self.category_analysis(trip_id)
        personal_dict = {c["category"]: c["percentage"] for c in personal}
        comparison = []
        for cat, national_pct in national_ratios.items():
            personal_pct = personal_dict.get(cat, 0)
            diff = round(personal_pct - national_pct, 1)
            if diff > 5:
                status = "above"
            elif diff < -5:
                status = "below"
            else:
                status = "close"
            comparison.append({
                "category": cat, "personal_pct": personal_pct,
                "national_pct": national_pct, "diff": diff, "status": status,
            })
        return comparison

    def daily_spending(self, trip_id: int) -> list:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT DATE(txn_datetime) AS day, COUNT(*), SUM(amount_twd)
                FROM transactions WHERE trip_id = ?
                GROUP BY DATE(txn_datetime) ORDER BY day
            """, (trip_id,))
            rows = cursor.fetchall()

        cumulative = 0
        result = []
        for i, r in enumerate(rows, 1):
            cumulative += r[2]
            result.append({
                "day": i, "date": r[0], "txn_count": r[1],
                "daily_twd": r[2], "cumulative_twd": cumulative,
            })
        return result

    def split_behavior(self, trip_id: int) -> dict:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT u.display_name, COUNT(*), SUM(t.amount_twd)
                FROM transactions t JOIN users u ON t.paid_by = u.user_id
                WHERE t.trip_id = ?
                GROUP BY t.paid_by ORDER BY SUM(t.amount_twd) DESC
            """, (trip_id,))
            payer_ranking = [{"name": r[0], "times": r[1], "total_twd": r[2]} for r in cursor.fetchall()]

            cursor.execute("""
                SELECT u.display_name, SUM(sd.share_twd)
                FROM split_details sd
                JOIN users u ON sd.user_id = u.user_id
                JOIN transactions t ON sd.txn_id = t.txn_id
                WHERE t.trip_id = ?
                GROUP BY sd.user_id ORDER BY SUM(sd.share_twd) DESC
            """, (trip_id,))
            share_ranking = [{"name": r[0], "total_twd": r[1]} for r in cursor.fetchall()]

            cursor.execute("""
                SELECT u.display_name, t.category, SUM(sd.share_twd)
                FROM split_details sd
                JOIN users u ON sd.user_id = u.user_id
                JOIN transactions t ON sd.txn_id = t.txn_id
                WHERE t.trip_id = ?
                GROUP BY sd.user_id, t.category
                ORDER BY u.display_name, SUM(sd.share_twd) DESC
            """, (trip_id,))
            per_person_category: dict = {}
            for r in cursor.fetchall():
                name, cat, total = r
                if name not in per_person_category:
                    per_person_category[name] = {}
                per_person_category[name][cat] = total

        return {
            "payer_ranking": payer_ranking,
            "share_ranking": share_ranking,
            "per_person_category": per_person_category,
        }

    def payment_analysis(self, trip_id: int) -> list:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT payment_method, COUNT(*), SUM(amount_twd)
                FROM transactions WHERE trip_id = ?
                GROUP BY payment_method ORDER BY SUM(amount_twd) DESC
            """, (trip_id,))
            rows = cursor.fetchall()
            cursor.execute("SELECT SUM(amount_twd) FROM transactions WHERE trip_id = ?", (trip_id,))
            grand_total = cursor.fetchone()[0] or 1

        labels = {"cash": "", "credit_card": "", "mobile_pay": ""}
        return [
            {"method": labels.get(r[0], r[0]), "count": r[1],
             "total_twd": r[2], "percentage": round(r[2] / grand_total * 100, 1)}
            for r in rows
        ]

    def full_report(self, trip_id: int) -> dict:
        return {
            "personal_vs_national": self.personal_vs_national(trip_id),
            "category_analysis": self.category_analysis(trip_id),
            "category_vs_national": self.category_vs_national(trip_id),
            "daily_spending": self.daily_spending(trip_id),
            "split_behavior": self.split_behavior(trip_id),
            "payment_analysis": self.payment_analysis(trip_id),
        }


if __name__ == "__main__":
    print("TravelWallet - Analytics Test")
    print("=" * 55)

    ana = Analytics()
    trip_id = 1

    print("\n[1] Personal vs National Average")
    print("=" * 55)
    pvn = ana.personal_vs_national(trip_id)
    t = pvn["trip"]
    p = pvn["personal"]
    n = pvn["national"]
    c = pvn["comparison"]

    print(f"  Trip: {t['destination']} {t['days']} days, {t['members']} people")
    print(f"  Period: {t['start_date']} ~ {t['end_date']}")
    print(f"  {'':15s} {'Your Trip':>12s} {'National':>12s} {'Diff':>10s}")
    print(f"  {'-'*50}")
    print(f"  {'Per Person':15s} NT${p['per_person_total']:>8,} NT${n['avg_total']:>8,.0f} {c['diff_total']:>+8,.0f}")
    print(f"  {'Daily':15s} NT${p['per_person_daily']:>8,} NT${n['avg_daily']:>8,} {c['diff_daily']:>+8,}")
    print(f"  {'Days':15s} {t['days']:>10} {n['avg_nights']:>12.1f}")
    print(f"  Diff: {c['diff_pct']:+.1f}%  Verdict: {c['verdict']}")

    print("\nDone!")

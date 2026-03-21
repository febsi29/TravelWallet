"""
planner.py - 


-  + 
-  /  / 
- /////
- 


  from src.planner import TripPlanner
  planner = TripPlanner(db_path)
  plan = planner.suggest_budget("", 5, num_travelers=4)
"""

import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


# 
# > 1.0 < 1.0 
DESTINATION_FACTORS = {
    "":     {"factor": 1.15, "currency": "JPY", "avg_days": 5},
    "":     {"factor": 0.95, "currency": "KRW", "avg_days": 5},
    "":     {"factor": 0.70, "currency": "THB", "avg_days": 6},
    "":     {"factor": 0.55, "currency": "VND", "avg_days": 5},
    "":   {"factor": 1.10, "currency": "SGD", "avg_days": 4},
    "": {"factor": 0.65, "currency": "MYR", "avg_days": 5},
    "":     {"factor": 1.05, "currency": "HKD", "avg_days": 4},
    "":     {"factor": 1.50, "currency": "USD", "avg_days": 8},
    "":     {"factor": 1.60, "currency": "EUR", "avg_days": 10},
    "":     {"factor": 1.70, "currency": "GBP", "avg_days": 8},
    "":     {"factor": 1.40, "currency": "AUD", "avg_days": 8},
    "":     {"factor": 0.80, "currency": "CNY", "avg_days": 5},
}

# 
CATEGORY_RATIOS = {
    "": 0.28,
    "": 0.25,
    "": 0.18,
    "": 0.18,
    "": 0.06,
    "": 0.05,
}

# 
BUDGET_TIERS = {
    "budget":   {"label": "", "multiplier": 0.7, "description": "/"},
    "standard": {"label": "", "multiplier": 1.0, "description": ""},
    "premium":  {"label": "", "multiplier": 1.5, "description": ""},
}


class TripPlanner:
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

    def suggest_budget(self, destination: str, days: int, num_travelers: int = 1) -> dict:
        """
        

        
            destination:  ""
            days: 
            num_travelers: 

        
            dict: 
        """
        if not destination or not isinstance(destination, str):
            raise ValueError(f"destination : {destination!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days : {days!r}")
        if not isinstance(num_travelers, int) or num_travelers <= 0:
            raise ValueError(f"num_travelers : {num_travelers!r}")

        avg_daily = self._get_avg_daily_spending()

        dest_info = DESTINATION_FACTORS.get(destination)
        if dest_info:
            factor = dest_info["factor"]
            currency_code = dest_info["currency"]
        else:
            factor = 1.0
            currency_code = "USD"

        adjusted_daily = avg_daily * factor

        tiers = {}
        for tier_key, tier_info in BUDGET_TIERS.items():
            total_per_person = round(adjusted_daily * tier_info["multiplier"] * days)
            total_group = total_per_person * num_travelers

            breakdown = {cat: round(total_per_person * ratio) for cat, ratio in CATEGORY_RATIOS.items()}

            tiers[tier_key] = {
                "label": tier_info["label"],
                "description": tier_info["description"],
                "daily_per_person": round(adjusted_daily * tier_info["multiplier"]),
                "total_per_person": total_per_person,
                "total_group": total_group,
                "breakdown": breakdown,
            }

        local_amounts = self._convert_to_local(tiers, currency_code)

        return {
            "destination": destination,
            "days": days,
            "num_travelers": num_travelers,
            "currency_code": currency_code,
            "avg_daily_base": avg_daily,
            "destination_factor": factor,
            "tiers": tiers,
            "local_amounts": local_amounts,
            "category_ratios": CATEGORY_RATIOS,
            "data_source": " - ",
        }

    def _get_avg_daily_spending(self) -> int:
        """
        TWD

         / 
        """
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT avg_spending_twd, avg_stay_nights
                FROM gov_outbound_stats
                WHERE avg_spending_twd IS NOT NULL
                ORDER BY year DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

        if row and row[0] and row[1]:
            return round(row[0] / row[1])
        return 7714  # 2023 60,481 / 7.84 ≈ 7,714

    def _convert_to_local(self, tiers: dict, currency_code: str) -> dict | None:
        """"""
        try:
            from src.currency import CurrencyManager
            cm = CurrencyManager(self.db_path)
            rate = cm.get_rate(currency_code)

            return {
                tier_key: {
                    "daily_per_person": round(tier_info["daily_per_person"] * rate),
                    "total_per_person": round(tier_info["total_per_person"] * rate),
                    "total_group": round(tier_info["total_group"] * rate),
                }
                for tier_key, tier_info in tiers.items()
            }
        except Exception as e:
            print(f": {e}")
            return None

    # ============================================================
    #  
    # ============================================================

    def save_plan(self, user_id: int, plan: dict, user_budget: float = None) -> int:
        """
        

        
            user_id:  ID
            plan: suggest_budget() 
            user_budget: 
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id : {user_id!r}")

        with self._db() as (conn, cursor):
            standard = plan["tiers"]["standard"]
            cursor.execute("""
                INSERT INTO trip_plans
                (user_id, destination, currency_code, planned_days, num_travelers,
                 suggested_budget, user_budget, budget_breakdown, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                plan["destination"],
                plan["currency_code"],
                plan["days"],
                plan["num_travelers"],
                standard["total_group"],
                user_budget,
                json.dumps(standard["breakdown"], ensure_ascii=False),
                plan["data_source"],
            ))
            return cursor.lastrowid

    # ============================================================
    #  
    # ============================================================

    def list_destinations(self) -> dict:
        """"""
        return DESTINATION_FACTORS.copy()

    def compare_destinations(self, days: int = 5, num_travelers: int = 1) -> list:
        """
        

        
            list[dict]: 
        """
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days : {days!r}")

        results = []
        for dest in DESTINATION_FACTORS:
            plan = self.suggest_budget(dest, days, num_travelers)
            std = plan["tiers"]["standard"]
            results.append({
                "destination": dest,
                "currency": plan["currency_code"],
                "daily_per_person": std["daily_per_person"],
                "total_per_person": std["total_per_person"],
                "total_group": std["total_group"],
                "factor": plan["destination_factor"],
            })

        results.sort(key=lambda x: x["total_per_person"])
        return results


if __name__ == "__main__":
    print("TravelWallet - ")
    print("=" * 55)

    planner = TripPlanner()

    plan = planner.suggest_budget("", 5, num_travelers=4)
    print(f": {plan['data_source']}")
    print(f": NT${plan['avg_daily_base']:,}/")
    print(f": x{plan['destination_factor']}")

    for tier_key, tier in plan["tiers"].items():
        print(f"\n{tier['label']}")
        print(f"  : NT${tier['total_per_person']:,}")
        print(f"  4: NT${tier['total_group']:,}")

    print("\n5//")
    comparisons = planner.compare_destinations(days=5, num_travelers=1)
    for i, c in enumerate(comparisons, 1):
        print(f"  {i:2d}. {c['destination']:6s} NT${c['total_per_person']:>7,}")

    print("\nDone!")

"""
fx_strategy.py - 


- 7  / 30 
- 
-  /  / 
- 


  from src.fx_strategy import FxStrategy
  fx = FxStrategy(db_path)
  advice = fx.advise(currency="JPY", amount_twd=50000)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

#  30 
GOOD_RATE_THRESHOLD = 0.02   # 2% 
BAD_RATE_THRESHOLD  = 0.02   # 2% 


class FxStrategy:
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

    def get_history(self, currency: str, days: int = 30) -> list:
        """
         1 TWD 

        
            currency:  "JPY"
            days: 

        
            list[dict]: [{"date": str, "rate": float}, ...]
        """
        if not currency or not isinstance(currency, str):
            raise ValueError(f"currency : {currency!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days : {days!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT recorded_date, rate
                FROM exchange_rates
                WHERE target_currency = ?
                ORDER BY recorded_date DESC
                LIMIT ?
            """, (currency.upper(), days))
            rows = cursor.fetchall()

        return [{"date": r[0], "rate": r[1]} for r in reversed(rows)]

    def moving_average(self, history: list, window: int) -> list:
        """
        

        
            history: get_history() 
            window:  7  30

        
            list[dict]:  window-1  None
        """
        if window <= 0:
            raise ValueError(f"window : {window!r}")

        result = []
        for i, entry in enumerate(history):
            if i < window - 1:
                result.append({"date": entry["date"], "ma": None})
            else:
                window_rates = [history[j]["rate"] for j in range(i - window + 1, i + 1)]
                result.append({"date": entry["date"], "ma": round(sum(window_rates) / window, 6)})
        return result

    def find_extremes(self, history: list) -> dict:
        """
        

        1 TWD  =  = 
        """
        if not history:
            return {}

        rates = [h["rate"] for h in history]
        max_rate = max(rates)
        min_rate = min(rates)
        max_entry = next(h for h in history if h["rate"] == max_rate)
        min_entry = next(h for h in history if h["rate"] == min_rate)

        return {
            "best": {"date": max_entry["date"], "rate": max_rate},   # 
            "worst": {"date": min_entry["date"], "rate": min_rate},  # 
        }

    # ============================================================
    #  
    # ============================================================

    def advise(self, currency: str, amount_twd: float, days: int = 30) -> dict:
        """
        

        
            currency:  "JPY"
            amount_twd: 
            days: 

        
            dict: 
        """
        if not currency or not isinstance(currency, str):
            raise ValueError(f"currency : {currency!r}")
        if amount_twd <= 0:
            raise ValueError(f"amount_twd  0: {amount_twd!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days : {days!r}")

        currency = currency.upper()
        history = self.get_history(currency, days)

        if not history:
            return {
                "currency": currency,
                "recommendation": "no_data",
                "message": f" {currency} ",
                "current_rate": None,
                "history": [],
            }

        current_rate = history[-1]["rate"]
        avg_rate = sum(h["rate"] for h in history) / len(history)

        # 
        ma7  = self.moving_average(history, min(7, len(history)))
        ma30 = self.moving_average(history, min(30, len(history)))

        extremes = self.find_extremes(history)

        # 
        diff_from_avg = (current_rate - avg_rate) / avg_rate if avg_rate > 0 else 0

        if diff_from_avg >= GOOD_RATE_THRESHOLD:
            recommendation = "buy_now"
            message = (
                f" {current_rate:.4f}  {days}  {avg_rate:.4f} "
                f" {diff_from_avg*100:.1f}%"
            )
        elif diff_from_avg <= -BAD_RATE_THRESHOLD:
            recommendation = "wait"
            message = (
                f" {current_rate:.4f}  {days}  {avg_rate:.4f} "
                f" {abs(diff_from_avg)*100:.1f}%"
            )
        else:
            recommendation = "neutral"
            message = (
                f" {current_rate:.4f}  {days}  {avg_rate:.4f}"
                f""
            )

        # 
        worst_rate = extremes.get("worst", {}).get("rate", current_rate)
        best_rate  = extremes.get("best",  {}).get("rate", current_rate)

        foreign_now   = round(amount_twd * current_rate, 2)
        foreign_best  = round(amount_twd * best_rate,    2)
        foreign_worst = round(amount_twd * worst_rate,   2)

        vs_worst_saving = round(foreign_now - foreign_worst, 2)
        vs_best_missing = round(foreign_best - foreign_now,  2)

        return {
            "currency": currency,
            "recommendation": recommendation,
            "message": message,
            "current_rate": current_rate,
            "avg_rate": round(avg_rate, 6),
            "diff_from_avg_pct": round(diff_from_avg * 100, 2),
            "extremes": extremes,
            "amount_twd": amount_twd,
            "foreign_at_current": foreign_now,
            "foreign_at_best":    foreign_best,
            "foreign_at_worst":   foreign_worst,
            "vs_worst_saving":    vs_worst_saving,   # 
            "vs_best_missing":    vs_best_missing,   # 
            "ma7":  ma7,
            "ma30": ma30,
            "history": history,
        }

    def batch_advise(self, currencies: list, amount_twd: float, days: int = 30) -> list:
        """
        

        
            currencies: 
            amount_twd: 
            days: 

        
            list[dict]: 
        """
        if not currencies:
            raise ValueError("currencies ")

        priority_order = {"buy_now": 0, "neutral": 1, "wait": 2, "no_data": 3}
        results = [self.advise(c, amount_twd, days) for c in currencies]
        results.sort(key=lambda x: priority_order.get(x["recommendation"], 99))
        return results


if __name__ == "__main__":
    print("TravelWallet - ")
    print("=" * 55)

    from src.currency import CurrencyManager, FALLBACK_RATES

    # 
    cm = CurrencyManager()
    cm.save_all_rates(FALLBACK_RATES, "2026-03-01")
    cm.save_all_rates(
        {k: round(v * 1.02, 6) for k, v in FALLBACK_RATES.items()},
        "2026-03-05"
    )
    cm.save_all_rates(FALLBACK_RATES, "2026-03-08")

    fx = FxStrategy()

    print("\n (JPY)  NT$50,000:")
    advice = fx.advise("JPY", 50000, days=30)
    print(f"  : {advice['recommendation'].upper()}")
    print(f"  : {advice['message']}")
    if advice["current_rate"]:
        print(f"  : {advice['foreign_at_current']:,.0f} JPY")
        print(f"  : {advice['foreign_at_best']:,.0f} JPY")
        if advice["extremes"]:
            print(f"  : {advice['extremes']['best']['date']}")

    print("\nDone!")

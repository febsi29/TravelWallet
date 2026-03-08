"""
fx_strategy.py - 換匯策略建議模組

功能：
- 歷史匯率移動平均線（7 日 / 30 日）
- 高低點判斷（相對於近期均值）
- 換匯時機建議（現在換 / 等待 / 已過最佳時機）
- 換匯節省金額試算

使用方式：
  from src.fx_strategy import FxStrategy
  fx = FxStrategy(db_path)
  advice = fx.advise(currency="JPY", amount_twd=50000)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# 建議門檻：若當前匯率比 30 日均值便宜超過此比例，視為「好時機」
GOOD_RATE_THRESHOLD = 0.02   # 2% 優於均值
BAD_RATE_THRESHOLD  = 0.02   # 2% 劣於均值


class FxStrategy:
    """換匯策略建議模組"""

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
    #  歷史匯率分析
    # ============================================================

    def get_history(self, currency: str, days: int = 30) -> list:
        """
        取得某幣別的歷史匯率（以 1 TWD 可換多少外幣表示）

        參數：
            currency: 幣別代碼，例如 "JPY"
            days: 查詢天數

        回傳：
            list[dict]: [{"date": str, "rate": float}, ...]
        """
        if not currency or not isinstance(currency, str):
            raise ValueError(f"currency 必須為非空字串，收到: {currency!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days 必須為正整數，收到: {days!r}")

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
        計算移動平均線

        參數：
            history: get_history() 回傳的資料
            window: 窗口天數（例如 7 或 30）

        回傳：
            list[dict]: 每個日期對應的移動平均值（前 window-1 天為 None）
        """
        if window <= 0:
            raise ValueError(f"window 必須為正整數，收到: {window!r}")

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
        找出歷史區間的最高點（最貴）與最低點（最便宜）

        匯率含義：1 TWD 可換愈多外幣 = 台幣愈強 = 換匯愈划算
        """
        if not history:
            return {}

        rates = [h["rate"] for h in history]
        max_rate = max(rates)
        min_rate = min(rates)
        max_entry = next(h for h in history if h["rate"] == max_rate)
        min_entry = next(h for h in history if h["rate"] == min_rate)

        return {
            "best": {"date": max_entry["date"], "rate": max_rate},   # 台幣最強，最划算
            "worst": {"date": min_entry["date"], "rate": min_rate},  # 台幣最弱，最不划算
        }

    # ============================================================
    #  換匯時機建議
    # ============================================================

    def advise(self, currency: str, amount_twd: float, days: int = 30) -> dict:
        """
        換匯時機綜合建議

        參數：
            currency: 目標幣別，例如 "JPY"
            amount_twd: 準備換的台幣金額
            days: 參考歷史天數

        回傳：
            dict: 包含建議、節省試算、移動平均等資訊
        """
        if not currency or not isinstance(currency, str):
            raise ValueError(f"currency 必須為非空字串，收到: {currency!r}")
        if amount_twd <= 0:
            raise ValueError(f"amount_twd 必須大於 0，收到: {amount_twd!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days 必須為正整數，收到: {days!r}")

        currency = currency.upper()
        history = self.get_history(currency, days)

        if not history:
            return {
                "currency": currency,
                "recommendation": "no_data",
                "message": f"資料庫中沒有 {currency} 的歷史匯率，請先更新匯率資料",
                "current_rate": None,
                "history": [],
            }

        current_rate = history[-1]["rate"]
        avg_rate = sum(h["rate"] for h in history) / len(history)

        # 移動平均
        ma7  = self.moving_average(history, min(7, len(history)))
        ma30 = self.moving_average(history, min(30, len(history)))

        extremes = self.find_extremes(history)

        # 判斷建議
        diff_from_avg = (current_rate - avg_rate) / avg_rate if avg_rate > 0 else 0

        if diff_from_avg >= GOOD_RATE_THRESHOLD:
            recommendation = "buy_now"
            message = (
                f"目前匯率 {current_rate:.4f} 比近 {days} 日均值 {avg_rate:.4f} "
                f"好 {diff_from_avg*100:.1f}%，建議現在換匯"
            )
        elif diff_from_avg <= -BAD_RATE_THRESHOLD:
            recommendation = "wait"
            message = (
                f"目前匯率 {current_rate:.4f} 比近 {days} 日均值 {avg_rate:.4f} "
                f"差 {abs(diff_from_avg)*100:.1f}%，建議等待更好時機"
            )
        else:
            recommendation = "neutral"
            message = (
                f"目前匯率 {current_rate:.4f} 接近近 {days} 日均值 {avg_rate:.4f}，"
                f"時機普通，可依需求決定"
            )

        # 節省試算（與最差時機比較）
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
            "vs_worst_saving":    vs_worst_saving,   # 與最差時機比，現在多換多少
            "vs_best_missing":    vs_best_missing,   # 與最好時機比，還差多少
            "ma7":  ma7,
            "ma30": ma30,
            "history": history,
        }

    def batch_advise(self, currencies: list, amount_twd: float, days: int = 30) -> list:
        """
        批次查詢多個幣別的換匯建議

        參數：
            currencies: 幣別代碼列表
            amount_twd: 準備換的台幣金額
            days: 參考歷史天數

        回傳：
            list[dict]: 各幣別建議（按建議優先度排序）
        """
        if not currencies:
            raise ValueError("currencies 不可為空")

        priority_order = {"buy_now": 0, "neutral": 1, "wait": 2, "no_data": 3}
        results = [self.advise(c, amount_twd, days) for c in currencies]
        results.sort(key=lambda x: priority_order.get(x["recommendation"], 99))
        return results


if __name__ == "__main__":
    print("TravelWallet - 換匯策略建議測試")
    print("=" * 55)

    from src.currency import CurrencyManager, FALLBACK_RATES

    # 先儲存備用匯率以供測試
    cm = CurrencyManager()
    cm.save_all_rates(FALLBACK_RATES, "2026-03-01")
    cm.save_all_rates(
        {k: round(v * 1.02, 6) for k, v in FALLBACK_RATES.items()},
        "2026-03-05"
    )
    cm.save_all_rates(FALLBACK_RATES, "2026-03-08")

    fx = FxStrategy()

    print("\n日圓 (JPY) 換匯建議（換 NT$50,000）:")
    advice = fx.advise("JPY", 50000, days=30)
    print(f"  建議: {advice['recommendation'].upper()}")
    print(f"  說明: {advice['message']}")
    if advice["current_rate"]:
        print(f"  目前可換: {advice['foreign_at_current']:,.0f} JPY")
        print(f"  最好時機可換: {advice['foreign_at_best']:,.0f} JPY")
        if advice["extremes"]:
            print(f"  最好換匯日: {advice['extremes']['best']['date']}")

    print("\nDone!")

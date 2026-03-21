"""
planner.py - 旅遊前預算規劃模組

功能：
- 根據目的地 + 天數，建議合理預算範圍
- 三檔預算（節省 / 標準 / 豪華）
- 類別分配建議（住宿/餐飲/交通/購物/娛樂/其他）
- 結合政府統計資料與即時匯率

使用方式：
  from src.planner import TripPlanner
  planner = TripPlanner(db_path)
  plan = planner.suggest_budget("日本", 5, num_travelers=4)
"""

import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


# 各目的地的每日消費係數（相對於全國平均）
# > 1.0 表示比平均貴，< 1.0 表示比平均便宜
DESTINATION_FACTORS = {
    "日本":     {"factor": 1.15, "currency": "JPY", "avg_days": 5},
    "韓國":     {"factor": 0.95, "currency": "KRW", "avg_days": 5},
    "泰國":     {"factor": 0.70, "currency": "THB", "avg_days": 6},
    "越南":     {"factor": 0.55, "currency": "VND", "avg_days": 5},
    "新加坡":   {"factor": 1.10, "currency": "SGD", "avg_days": 4},
    "馬來西亞": {"factor": 0.65, "currency": "MYR", "avg_days": 5},
    "香港":     {"factor": 1.05, "currency": "HKD", "avg_days": 4},
    "美國":     {"factor": 1.50, "currency": "USD", "avg_days": 8},
    "歐洲":     {"factor": 1.60, "currency": "EUR", "avg_days": 10},
    "英國":     {"factor": 1.70, "currency": "GBP", "avg_days": 8},
    "澳洲":     {"factor": 1.40, "currency": "AUD", "avg_days": 8},
    "中國":     {"factor": 0.80, "currency": "CNY", "avg_days": 5},
}

# 消費類別分配比例（根據觀光署調查資料）
CATEGORY_RATIOS = {
    "住宿": 0.28,
    "餐飲": 0.25,
    "交通": 0.18,
    "購物": 0.18,
    "娛樂": 0.06,
    "其他": 0.05,
}

# 三檔預算的乘數
BUDGET_TIERS = {
    "budget":   {"label": "節省版", "multiplier": 0.7, "description": "住青旅/平價旅館、吃當地小吃、搭大眾運輸"},
    "standard": {"label": "標準版", "multiplier": 1.0, "description": "住商務旅館、餐廳與小吃各半、偶爾計程車"},
    "premium":  {"label": "豪華版", "multiplier": 1.5, "description": "住星級飯店、高檔餐廳、包車或新幹線"},
}


class TripPlanner:
    """旅遊前預算規劃"""

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
    #  核心功能：預算建議
    # ============================================================

    def suggest_budget(self, destination: str, days: int, num_travelers: int = 1) -> dict:
        """
        根據目的地和天數建議預算

        參數：
            destination: 目的地名稱（例如 "日本"）
            days: 旅行天數
            num_travelers: 旅行人數

        回傳：
            dict: 包含三檔預算、類別分配、參考資訊
        """
        if not destination or not isinstance(destination, str):
            raise ValueError(f"destination 必須為非空字串，收到: {destination!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days 必須為正整數，收到: {days!r}")
        if not isinstance(num_travelers, int) or num_travelers <= 0:
            raise ValueError(f"num_travelers 必須為正整數，收到: {num_travelers!r}")

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
            "data_source": "交通部觀光署 - 歷年國人出國旅遊重要指標統計表",
        }

    def _get_avg_daily_spending(self) -> int:
        """
        從資料庫取得最新的全國平均每日消費（TWD）

        計算方式：每人每次平均消費 / 平均停留夜數
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
        return 7714  # 備用值（2023 年資料：60,481 / 7.84 ≈ 7,714）

    def _convert_to_local(self, tiers: dict, currency_code: str) -> dict | None:
        """嘗試將預算換算成當地幣別"""
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
            print(f"無法換算當地幣別: {e}")
            return None

    # ============================================================
    #  儲存規劃
    # ============================================================

    def save_plan(self, user_id: int, plan: dict, user_budget: float = None) -> int:
        """
        將規劃結果儲存到資料庫

        參數：
            user_id: 使用者 ID
            plan: suggest_budget() 的回傳結果
            user_budget: 使用者自訂預算（可選）
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

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
    #  查詢功能
    # ============================================================

    def list_destinations(self) -> dict:
        """列出所有支援的目的地"""
        return DESTINATION_FACTORS.copy()

    def compare_destinations(self, days: int = 5, num_travelers: int = 1) -> list:
        """
        比較所有目的地的預算

        回傳：
            list[dict]: 按標準版預算排序的目的地列表
        """
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days 必須為正整數，收到: {days!r}")

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
    print("TravelWallet - 旅遊前預算規劃測試")
    print("=" * 55)

    planner = TripPlanner()

    plan = planner.suggest_budget("日本", 5, num_travelers=4)
    print(f"資料來源: {plan['data_source']}")
    print(f"全國平均每日消費: NT${plan['avg_daily_base']:,}/人")
    print(f"日本消費係數: x{plan['destination_factor']}")

    for tier_key, tier in plan["tiers"].items():
        print(f"\n{tier['label']}")
        print(f"  每人總計: NT${tier['total_per_person']:,}")
        print(f"  4人總計: NT${tier['total_group']:,}")

    print("\n目的地預算比較（5天/每人/標準版）")
    comparisons = planner.compare_destinations(days=5, num_travelers=1)
    for i, c in enumerate(comparisons, 1):
        print(f"  {i:2d}. {c['destination']:6s} NT${c['total_per_person']:>7,}")

    print("\nDone!")

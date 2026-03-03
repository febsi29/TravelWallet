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
    "budget":   {"label": "🟢 節省版", "multiplier": 0.7, "description": "住青旅/平價旅館、吃當地小吃、搭大眾運輸"},
    "standard": {"label": "🟡 標準版", "multiplier": 1.0, "description": "住商務旅館、餐廳與小吃各半、偶爾計程車"},
    "premium":  {"label": "🔴 豪華版", "multiplier": 1.5, "description": "住星級飯店、高檔餐廳、包車或新幹線"},
}


class TripPlanner:
    """旅遊前預算規劃"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ============================================================
    #  核心功能：預算建議
    # ============================================================

    def suggest_budget(self, destination, days, num_travelers=1):
        """
        根據目的地和天數建議預算

        參數：
            destination: 目的地名稱（例如 "日本"）
            days: 旅行天數
            num_travelers: 旅行人數

        回傳：
            dict: 包含三檔預算、類別分配、參考資訊
        """
        # 1. 取得全國平均每日消費
        avg_daily = self._get_avg_daily_spending()

        # 2. 根據目的地調整
        dest_info = DESTINATION_FACTORS.get(destination)
        if dest_info:
            factor = dest_info["factor"]
            currency_code = dest_info["currency"]
        else:
            factor = 1.0
            currency_code = "USD"

        adjusted_daily = avg_daily * factor

        # 3. 計算三檔預算
        tiers = {}
        for tier_key, tier_info in BUDGET_TIERS.items():
            total_per_person = round(adjusted_daily * tier_info["multiplier"] * days)
            total_group = total_per_person * num_travelers

            # 類別分配
            breakdown = {}
            for cat, ratio in CATEGORY_RATIOS.items():
                breakdown[cat] = round(total_per_person * ratio)

            tiers[tier_key] = {
                "label": tier_info["label"],
                "description": tier_info["description"],
                "daily_per_person": round(adjusted_daily * tier_info["multiplier"]),
                "total_per_person": total_per_person,
                "total_group": total_group,
                "breakdown": breakdown,
            }

        # 4. 嘗試換算當地幣別
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

    def _get_avg_daily_spending(self):
        """
        從資料庫取得最新的全國平均每日消費（TWD）

        計算方式：每人每次平均消費 / 平均停留夜數
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 取最新一年有完整資料的紀錄
        cursor.execute("""
            SELECT avg_spending_twd, avg_stay_nights
            FROM gov_outbound_stats
            WHERE avg_spending_twd IS NOT NULL
            ORDER BY year DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        if row and row[0] and row[1]:
            avg_daily = row[0] / row[1]
            return round(avg_daily)
        else:
            # 備用值（根據 2023 年資料：60,481 / 7.84 ≈ 7,714）
            return 7714

    def _convert_to_local(self, tiers, currency_code):
        """嘗試將預算換算成當地幣別"""
        try:
            from src.currency import CurrencyManager
            cm = CurrencyManager(self.db_path)
            rate = cm.get_rate(currency_code)

            local = {}
            for tier_key, tier_info in tiers.items():
                local[tier_key] = {
                    "daily_per_person": round(tier_info["daily_per_person"] * rate),
                    "total_per_person": round(tier_info["total_per_person"] * rate),
                    "total_group": round(tier_info["total_group"] * rate),
                }
            return local

        except Exception as e:
            print(f"⚠️ 無法換算當地幣別: {e}")
            return None

    # ============================================================
    #  儲存規劃
    # ============================================================

    def save_plan(self, user_id, plan, user_budget=None):
        """
        將規劃結果儲存到資料庫

        參數：
            user_id: 使用者 ID
            plan: suggest_budget() 的回傳結果
            user_budget: 使用者自訂預算（可選）
        """
        conn = self._connect()
        cursor = conn.cursor()

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

        plan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return plan_id

    # ============================================================
    #  查詢功能
    # ============================================================

    def list_destinations(self):
        """列出所有支援的目的地"""
        return DESTINATION_FACTORS.copy()

    def compare_destinations(self, days=5, num_travelers=1):
        """
        比較所有目的地的預算

        回傳：
            list[dict]: 按標準版預算排序的目的地列表
        """
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


# ============================================================
#  測試 / Demo
# ============================================================

if __name__ == "__main__":
    print("🧳 TravelWallet - 旅遊前預算規劃測試")
    print("=" * 55)

    planner = TripPlanner()

    # --- 情境：4 個人去日本 5 天 ---
    print("\n✈️  情境：4 個好朋友去日本東京 5 天")
    print("=" * 55)

    plan = planner.suggest_budget("日本", 5, num_travelers=4)

    print(f"\n📊 資料來源: {plan['data_source']}")
    print(f"📌 全國平均每日消費: NT${plan['avg_daily_base']:,}/人")
    print(f"📌 日本消費係數: x{plan['destination_factor']} (比平均高 {(plan['destination_factor']-1)*100:.0f}%)")

    for tier_key, tier in plan["tiers"].items():
        print(f"\n{tier['label']}")
        print(f"  說明: {tier['description']}")
        print(f"  每人每日: NT${tier['daily_per_person']:,}")
        print(f"  每人總計: NT${tier['total_per_person']:,}")
        print(f"  4人總計: NT${tier['total_group']:,}")

        if plan["local_amounts"] and tier_key in plan["local_amounts"]:
            local = plan["local_amounts"][tier_key]
            symbol = "¥"
            print(f"  (約 {symbol}{local['total_per_person']:,} {plan['currency_code']}/人)")

        print(f"  類別分配:")
        for cat, amount in tier["breakdown"].items():
            pct = CATEGORY_RATIOS[cat] * 100
            print(f"    {cat}: NT${amount:,} ({pct:.0f}%)")

    # --- 目的地比較 ---
    print(f"\n\n🌏 目的地預算比較（5天/每人/標準版）")
    print("=" * 55)
    comparisons = planner.compare_destinations(days=5, num_travelers=1)
    for i, c in enumerate(comparisons, 1):
        bar = "█" * int(c["total_per_person"] / 2000)
        print(f"  {i:2d}. {c['destination']:6s} NT${c['total_per_person']:>7,}  {bar}")

    print("\n🎉 預算規劃測試完成！")

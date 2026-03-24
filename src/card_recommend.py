"""
card_recommend.py - 信用卡推薦模組

功能：
- 依旅行消費模式推薦最佳回饋信用卡
- 計算各卡片在特定消費下的實際回饋金額
- 多卡比較（考量海外手續費 vs 回饋率）
- 內建台灣常見旅遊信用卡資料

使用方式：
  from src.card_recommend import CardRecommendService, seed_cards
  seed_cards(db_path)
  svc = CardRecommendService(db_path)
  results = svc.recommend_by_trip(trip_id=1)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

VALID_CATEGORIES = ("餐飲", "交通", "住宿", "購物", "娛樂", "其他", "all", "海外")


class CardRecommendService:
    """信用卡推薦服務"""

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
    #  卡片查詢
    # ============================================================

    def get_all_cards(self) -> list:
        """
        取得所有啟用中的信用卡及其回饋規則

        回傳：
            list[dict]: 卡片列表（含 rewards 子列表）
        """
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT card_id, card_name, issuer, card_type, annual_fee, overseas_fee_pct
                FROM credit_cards WHERE is_active = 1
                ORDER BY card_name
            """)
            cards = cursor.fetchall()

        result = []
        for card in cards:
            card_dict = {
                "card_id": card[0],
                "card_name": card[1],
                "issuer": card[2],
                "card_type": card[3],
                "annual_fee": card[4],
                "overseas_fee_pct": card[5],
                "rewards": self._get_rewards(card[0]),
            }
            result.append(card_dict)

        return result

    def get_card_detail(self, card_id: int) -> dict:
        """
        取得單張信用卡的詳細資料

        參數：
            card_id: 信用卡 ID

        回傳：
            dict: 卡片完整資料（含回饋規則）
        """
        if not isinstance(card_id, int) or card_id <= 0:
            raise ValueError(f"card_id 必須為正整數，收到: {card_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT card_id, card_name, issuer, card_type, annual_fee, overseas_fee_pct
                FROM credit_cards WHERE card_id = ?
            """, (card_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"找不到 card_id={card_id}")

        return {
            "card_id": row[0],
            "card_name": row[1],
            "issuer": row[2],
            "card_type": row[3],
            "annual_fee": row[4],
            "overseas_fee_pct": row[5],
            "rewards": self._get_rewards(row[0]),
        }

    def _get_rewards(self, card_id: int) -> list:
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT reward_id, category, region, reward_type, reward_rate,
                       reward_cap, min_spend
                FROM card_rewards WHERE card_id = ?
                ORDER BY reward_rate DESC
            """, (card_id,))
            rows = cursor.fetchall()

        keys = ["reward_id", "category", "region", "reward_type",
                "reward_rate", "reward_cap", "min_spend"]
        return [dict(zip(keys, r)) for r in rows]

    # ============================================================
    #  回饋計算
    # ============================================================

    def calculate_reward(
        self,
        card_id: int,
        amount: float,
        category: str,
        region: str = "all",
    ) -> dict:
        """
        計算單筆消費在指定卡片的回饋金額

        優先順序：精確類別+地區 > 精確類別+all > all+any

        參數：
            card_id: 信用卡 ID
            amount: 消費金額（TWD）
            category: 消費類別
            region: 消費地區（"all" 或目的地名稱）

        回傳：
            dict: {reward_amount, reward_rate, reward_type, fee_amount, net_benefit}
        """
        if not isinstance(card_id, int) or card_id <= 0:
            raise ValueError(f"card_id 必須為正整數，收到: {card_id!r}")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError(f"amount 必須大於 0，收到: {amount!r}")
        if not category or not isinstance(category, str):
            raise ValueError(f"category 必須為非空字串，收到: {category!r}")

        rewards = self._get_rewards(card_id)

        best_rule = None
        best_priority = -1

        for rule in rewards:
            cat_match = (rule["category"] == category or rule["category"] == "all" or rule["category"] == "海外")
            if not cat_match:
                continue

            # 地區匹配優先級
            if rule["region"] == region and rule["category"] == category:
                priority = 3
            elif rule["region"] == "all" and rule["category"] == category:
                priority = 2
            elif rule["category"] == "all" or rule["category"] == "海外":
                priority = 1
            else:
                priority = 0

            if priority > best_priority:
                best_priority = priority
                best_rule = rule

        if not best_rule or amount < (best_rule.get("min_spend") or 0):
            reward_amount = 0.0
            reward_rate = 0.0
            reward_type = "none"
        else:
            reward_amount = round(amount * best_rule["reward_rate"] / 100, 2)
            if best_rule.get("reward_cap"):
                reward_amount = min(reward_amount, best_rule["reward_cap"])
            reward_rate = best_rule["reward_rate"]
            reward_type = best_rule["reward_type"]

        # 取得海外手續費
        with self._db() as (conn, cursor):
            cursor.execute(
                "SELECT overseas_fee_pct FROM credit_cards WHERE card_id = ?",
                (card_id,)
            )
            row = cursor.fetchone()
        overseas_fee_pct = row[0] if row else 1.5

        # 若為台幣消費（region=all + 無指定地區），不計手續費
        fee_amount = round(amount * overseas_fee_pct / 100, 2) if region != "all" else 0.0
        net_benefit = round(reward_amount - fee_amount, 2)

        return {
            "reward_amount": reward_amount,
            "reward_rate": reward_rate,
            "reward_type": reward_type,
            "fee_amount": fee_amount,
            "net_benefit": net_benefit,
        }

    # ============================================================
    #  依旅行推薦
    # ============================================================

    def recommend_by_trip(self, trip_id: int) -> list:
        """
        依旅行消費模式推薦最佳信用卡

        參數：
            trip_id: 旅行 ID

        回傳：
            list[dict]: 依淨回饋排名的信用卡列表
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        # 取得旅行目的地和交易
        with self._db() as (conn, cursor):
            cursor.execute("SELECT destination FROM trips WHERE trip_id = ?", (trip_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"找不到 trip_id={trip_id}")
            destination = row[0]

            cursor.execute("""
                SELECT category, SUM(amount_twd) FROM transactions
                WHERE trip_id = ?
                GROUP BY category
            """, (trip_id,))
            category_spending = cursor.fetchall()

        if not category_spending:
            return []

        cards = self.get_all_cards()
        results = []

        for card in cards:
            total_reward = 0.0
            total_fee = 0.0
            top_category = None
            top_category_reward = 0.0

            for cat, amount_twd in category_spending:
                calc = self.calculate_reward(card["card_id"], float(amount_twd), cat, destination)
                total_reward += calc["reward_amount"]
                total_fee += calc["fee_amount"]
                if calc["reward_amount"] > top_category_reward:
                    top_category_reward = calc["reward_amount"]
                    top_category = cat

            net_benefit = round(total_reward - total_fee, 2)
            results.append({
                "card_id": card["card_id"],
                "card_name": card["card_name"],
                "issuer": card["issuer"],
                "total_reward": round(total_reward, 2),
                "total_fee": round(total_fee, 2),
                "net_benefit": net_benefit,
                "top_category": top_category,
            })

        results.sort(key=lambda x: x["net_benefit"], reverse=True)
        return results

    # ============================================================
    #  依類別推薦
    # ============================================================

    def recommend_by_category(
        self, category: str, amount: float, region: str = "all"
    ) -> list:
        """
        依單一消費類別推薦最佳信用卡

        參數：
            category: 消費類別
            amount: 消費金額（TWD）
            region: 消費地區

        回傳：
            list[dict]: 依淨回饋排名的信用卡列表
        """
        if not category or not isinstance(category, str):
            raise ValueError(f"category 必須為非空字串，收到: {category!r}")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError(f"amount 必須大於 0，收到: {amount!r}")

        cards = self.get_all_cards()
        results = []

        for card in cards:
            calc = self.calculate_reward(card["card_id"], float(amount), category, region)
            results.append({
                "card_id": card["card_id"],
                "card_name": card["card_name"],
                "issuer": card["issuer"],
                **calc,
            })

        results.sort(key=lambda x: x["net_benefit"], reverse=True)
        return results

    # ============================================================
    #  卡片比較
    # ============================================================

    def compare_cards(self, card_ids: list, trip_id: int) -> dict:
        """
        比較多張信用卡在同一旅行下的回饋差異

        參數：
            card_ids: 要比較的信用卡 ID 列表
            trip_id: 旅行 ID

        回傳：
            dict: {"cards": [per-card results], "best_card_id", "max_net_benefit"}
        """
        if not card_ids:
            raise ValueError("card_ids 不可為空")
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        all_results = self.recommend_by_trip(trip_id)
        card_map = {r["card_id"]: r for r in all_results}

        cards = [card_map[cid] for cid in card_ids if cid in card_map]
        if not cards:
            return {"cards": [], "best_card_id": None, "max_net_benefit": 0.0}

        best = max(cards, key=lambda x: x["net_benefit"])
        return {
            "cards": cards,
            "best_card_id": best["card_id"],
            "max_net_benefit": best["net_benefit"],
        }


# ============================================================
#  種子資料：台灣常見旅遊信用卡
# ============================================================

def seed_cards(db_path: str = None) -> None:
    """
    寫入台灣常見旅遊信用卡示範資料

    參數：
        db_path: 資料庫路徑（None 則使用預設路徑）
    """
    db = db_path or DB_PATH

    cards = [
        # (card_name, issuer, card_type, annual_fee, overseas_fee_pct)
        ("玉山 Pi 錢包卡", "玉山銀行", "visa", 0, 1.5),
        ("中信 CUBE 卡", "中國信託", "visa", 0, 1.5),
        ("台新 @GoGo 卡", "台新銀行", "visa", 0, 1.5),
        ("國泰 KOKO 卡", "國泰世華", "mastercard", 0, 1.5),
        ("富邦 J 卡", "台北富邦", "jcb", 0, 0.0),
        ("聯邦 賴點卡", "聯邦銀行", "visa", 0, 1.5),
    ]

    rewards_data = {
        "玉山 Pi 錢包卡": [
            ("海外", "all", "cashback", 2.8, None, 0),
        ],
        "中信 CUBE 卡": [
            ("餐飲", "all", "cashback", 5.0, 500, 0),
            ("海外", "all", "cashback", 2.5, None, 0),
        ],
        "台新 @GoGo 卡": [
            ("海外", "all", "cashback", 3.0, None, 0),
        ],
        "國泰 KOKO 卡": [
            ("海外", "all", "cashback", 3.3, None, 0),
            ("購物", "all", "cashback", 3.3, None, 0),
        ],
        "富邦 J 卡": [
            ("all", "日本", "cashback", 5.0, 1000, 0),
            ("海外", "all", "cashback", 2.0, None, 0),
        ],
        "聯邦 賴點卡": [
            ("購物", "all", "cashback", 5.0, 300, 0),
            ("all", "all", "cashback", 1.0, None, 0),
        ],
    }

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    for card_name, issuer, card_type, annual_fee, overseas_fee_pct in cards:
        # 先查詢是否已存在，避免重複
        cursor.execute("SELECT card_id FROM credit_cards WHERE card_name = ?", (card_name,))
        existing = cursor.fetchone()

        if existing:
            # 卡片已存在，跳過（冪等）
            continue

        cursor.execute("""
            INSERT INTO credit_cards
            (card_name, issuer, card_type, annual_fee, overseas_fee_pct, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (card_name, issuer, card_type, annual_fee, overseas_fee_pct))
        card_id = cursor.lastrowid

        for category, region, reward_type, reward_rate, reward_cap, min_spend in rewards_data.get(card_name, []):
            cursor.execute("""
                INSERT INTO card_rewards
                (card_id, category, region, reward_type, reward_rate, reward_cap, min_spend)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (card_id, category, region, reward_type, reward_rate, reward_cap, min_spend))

    conn.commit()
    conn.close()
    print(f"信用卡種子資料已寫入：{len(cards)} 張卡片")

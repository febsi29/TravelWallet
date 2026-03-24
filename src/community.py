"""
community.py - 社群排行榜模組

功能：
- 匿名化分享旅行消費資料至社群資料庫
- 依目的地統計平均消費
- 最節省 / 最豪華旅遊排行榜
- 類似旅行比較（查詢同目的地、相近天數的平均消費）
- 我的旅行排名百分位

使用方式：
  from src.community import CommunityService
  svc = CommunityService(db_path)
  svc.share_trip_data(user_id=1, trip_id=1)
  leaderboard = svc.get_leaderboard(metric="frugal")
"""

import sqlite3
import os
import json
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

VALID_METRICS = ("frugal", "spender")


class CommunityService:
    """社群排行榜服務"""

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
    #  分享旅行資料
    # ============================================================

    def share_trip_data(self, user_id: int, trip_id: int) -> dict:
        """
        將旅行消費資料匿名化後分享至社群資料庫

        參數：
            user_id: 使用者 ID
            trip_id: 旅行 ID

        回傳：
            dict: 已分享的統計資料
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        with self._db() as (conn, cursor):
            # 取得旅行基本資訊
            cursor.execute("""
                SELECT destination, start_date, end_date,
                       CAST(julianday(end_date) - julianday(start_date) + 1 AS INTEGER)
                FROM trips WHERE trip_id = ?
            """, (trip_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"找不到 trip_id={trip_id}")
            destination, start_date, end_date, trip_days = row

            # 旅行成員數
            cursor.execute(
                "SELECT COUNT(*) FROM trip_members WHERE trip_id = ?",
                (trip_id,)
            )
            num_travelers = cursor.fetchone()[0] or 1

            # 總消費（台幣）
            cursor.execute(
                "SELECT COALESCE(SUM(amount_twd), 0) FROM transactions WHERE trip_id = ?",
                (trip_id,)
            )
            total_spent_twd = cursor.fetchone()[0]

            # 每人每日消費
            per_person_daily = (
                total_spent_twd / num_travelers / trip_days
                if trip_days > 0 and num_travelers > 0
                else 0.0
            )

            # 消費類別分佈
            cursor.execute("""
                SELECT category, SUM(amount_twd)
                FROM transactions WHERE trip_id = ?
                GROUP BY category
            """, (trip_id,))
            cat_rows = cursor.fetchall()
            total = sum(r[1] for r in cat_rows) or 1
            category_breakdown = {r[0]: round(r[1] / total, 4) for r in cat_rows}

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT OR REPLACE INTO community_stats
                (destination, trip_days, num_travelers, total_spent_twd,
                 per_person_daily, category_breakdown, user_id, trip_id, is_anonymous)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                destination, int(trip_days), num_travelers,
                float(total_spent_twd), round(float(per_person_daily), 2),
                json.dumps(category_breakdown, ensure_ascii=False),
                user_id, trip_id,
            ))

        return {
            "destination": destination,
            "trip_days": int(trip_days),
            "num_travelers": num_travelers,
            "total_spent_twd": float(total_spent_twd),
            "per_person_daily": round(float(per_person_daily), 2),
            "category_breakdown": category_breakdown,
        }

    # ============================================================
    #  目的地統計
    # ============================================================

    def get_destination_stats(self, destination: str) -> dict:
        """
        取得某目的地的社群消費統計

        參數：
            destination: 目的地名稱

        回傳：
            dict: {destination, count, avg_daily, min_daily, max_daily, avg_days}
        """
        if not destination or not isinstance(destination, str):
            raise ValueError(f"destination 必須為非空字串，收到: {destination!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT COUNT(*), AVG(per_person_daily), MIN(per_person_daily),
                       MAX(per_person_daily), AVG(trip_days)
                FROM community_stats
                WHERE destination = ?
            """, (destination,))
            row = cursor.fetchone()

        count = row[0] or 0
        if count == 0:
            return {
                "destination": destination,
                "count": 0,
                "avg_daily": 0.0,
                "min_daily": 0.0,
                "max_daily": 0.0,
                "avg_days": 0.0,
            }

        return {
            "destination": destination,
            "count": count,
            "avg_daily": round(row[1] or 0, 2),
            "min_daily": round(row[2] or 0, 2),
            "max_daily": round(row[3] or 0, 2),
            "avg_days": round(row[4] or 0, 1),
        }

    # ============================================================
    #  排行榜
    # ============================================================

    def get_leaderboard(self, metric: str = "frugal", limit: int = 10) -> list:
        """
        取得旅行消費排行榜

        參數：
            metric: "frugal"（最節省）或 "spender"（最豪華）
            limit: 最多回傳筆數

        回傳：
            list[dict]: 排行榜列表
        """
        if metric not in VALID_METRICS:
            raise ValueError(f"metric 必須為 'frugal' 或 'spender'，收到: {metric!r}")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit 必須為正整數，收到: {limit!r}")

        order = "ASC" if metric == "frugal" else "DESC"

        with self._db() as (conn, cursor):
            cursor.execute(f"""
                SELECT stat_id, destination, trip_days, num_travelers,
                       per_person_daily, shared_at
                FROM community_stats
                ORDER BY per_person_daily {order}
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

        result = []
        for rank, row in enumerate(rows, 1):
            result.append({
                "rank": rank,
                "stat_id": row[0],
                "destination": row[1],
                "trip_days": row[2],
                "num_travelers": row[3],
                "per_person_daily": round(row[4], 2),
                "shared_at": row[5],
            })

        return result

    # ============================================================
    #  目的地比較
    # ============================================================

    def get_destination_comparison(self, destinations: list) -> list:
        """
        比較多個目的地的消費統計

        參數：
            destinations: 目的地名稱列表

        回傳：
            list[dict]: 各目的地統計列表
        """
        if not destinations or not isinstance(destinations, list):
            raise ValueError("destinations 必須為非空列表")

        return [self.get_destination_stats(d) for d in destinations]

    # ============================================================
    #  類似旅行查詢
    # ============================================================

    def get_similar_trips(
        self, destination: str, days: int, num_travelers: int
    ) -> dict:
        """
        查詢類似旅行（同目的地、相近天數）的平均消費

        參數：
            destination: 目的地名稱
            days: 旅行天數
            num_travelers: 旅行人數

        回傳：
            dict: {destination, similar_count, avg_daily}
        """
        if not destination or not isinstance(destination, str):
            raise ValueError(f"destination 必須為非空字串，收到: {destination!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days 必須為正整數，收到: {days!r}")
        if not isinstance(num_travelers, int) or num_travelers <= 0:
            raise ValueError(f"num_travelers 必須為正整數，收到: {num_travelers!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT COUNT(*), AVG(per_person_daily)
                FROM community_stats
                WHERE destination = ?
                  AND trip_days BETWEEN ? AND ?
            """, (destination, max(1, days - 1), days + 1))
            row = cursor.fetchone()

        count = row[0] or 0
        avg_daily = round(row[1] or 0, 2)

        return {
            "destination": destination,
            "similar_count": count,
            "avg_daily": avg_daily,
        }

    # ============================================================
    #  我的排名
    # ============================================================

    def get_my_ranking(self, user_id: int, trip_id: int) -> dict:
        """
        查詢我的旅行在同目的地中的排名

        參數：
            user_id: 使用者 ID
            trip_id: 旅行 ID

        回傳：
            dict: {rank, total, percentile, per_person_daily}
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT destination, per_person_daily
                FROM community_stats
                WHERE user_id = ? AND trip_id = ?
            """, (user_id, trip_id))
            row = cursor.fetchone()

        if not row:
            return {"rank": None, "total": 0, "percentile": None, "per_person_daily": None}

        destination, per_person_daily = row

        with self._db() as (conn, cursor):
            cursor.execute(
                "SELECT COUNT(*) FROM community_stats WHERE destination = ?",
                (destination,)
            )
            total = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(*) FROM community_stats
                WHERE destination = ? AND per_person_daily < ?
            """, (destination, per_person_daily))
            cheaper_count = cursor.fetchone()[0] or 0

        rank = total - cheaper_count
        percentile = round(cheaper_count / total * 100, 1) if total > 0 else 0.0

        return {
            "rank": rank,
            "total": total,
            "percentile": percentile,
            "per_person_daily": round(per_person_daily, 2),
            "destination": destination,
        }

"""
prediction.py - 支出預測與智慧提醒模組

功能：
- 以指數平滑法預測每日消費趨勢
- 線性迴歸推算超支日期
- 自動產生智慧提醒（超支警告、異常消費、匯率波動）
- 提醒紀錄管理

使用方式：
  from src.prediction import SpendingPredictor
  predictor = SpendingPredictor(db_path)
  result = predictor.predict_budget_exceed_day(trip_id=1)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# 指數平滑係數
EXP_SMOOTHING_ALPHA = 0.3
# 超支警告倍數門檻（今日 > 1.5x 日均 → 發出警告）
OVERSPEND_THRESHOLD = 1.5


class SpendingPredictor:
    """支出預測與智慧提醒引擎"""

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
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT trip_id, trip_name, destination, currency_code,
                       start_date, end_date, total_budget,
                       CAST(julianday(end_date) - julianday(start_date) + 1 AS INTEGER) AS total_days
                FROM trips WHERE trip_id = ?
            """, (trip_id,))
            row = cursor.fetchone()
        if not row:
            raise ValueError(f"找不到 trip_id={trip_id}")
        keys = ["trip_id", "trip_name", "destination", "currency_code",
                "start_date", "end_date", "budget", "total_days"]
        return dict(zip(keys, row))

    # ============================================================
    #  預算超支預測
    # ============================================================

    def predict_budget_exceed_day(self, trip_id: int) -> dict:
        """
        預測旅行是否會超支，以及預計超支日

        使用 BudgetManager 的線性迴歸結果（y = a + b*x）：
        超支日 = (budget - a) / b

        參數：
            trip_id: 旅行 ID

        回傳：
            dict: {will_exceed, exceed_day, days_until_exceed, predicted_total, budget, current_day}
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        try:
            from src.budget import BudgetManager
            bm = BudgetManager(self.db_path)
            prediction = bm.predict_remaining(trip_id)
            trip = self._get_trip_info(trip_id)
        except Exception as e:
            return {"error": str(e), "will_exceed": False}

        if "error" in prediction:
            return {"will_exceed": False, "message": prediction["error"]}

        will_exceed = prediction.get("will_exceed", False)
        predicted_total = prediction.get("predicted_total", 0)
        budget = prediction.get("budget", 0)
        current_day = prediction.get("current_day", 1)
        total_days = trip["total_days"]

        exceed_day = None
        days_until_exceed = None

        if will_exceed and prediction.get("daily_rate", 0) > 0:
            # 估算超支日（簡化為線性推算）
            actual_spent = prediction.get("actual_spent", 0)
            daily_rate = prediction.get("daily_rate", 0)
            if daily_rate > 0:
                days_to_exceed = (budget - actual_spent) / daily_rate
                exceed_day = min(int(current_day + days_to_exceed) + 1, total_days + 1)
                days_until_exceed = max(0, exceed_day - current_day)

        return {
            "will_exceed": will_exceed,
            "exceed_day": exceed_day,
            "days_until_exceed": days_until_exceed,
            "predicted_total": predicted_total,
            "budget": budget,
            "current_day": current_day,
            "total_days": total_days,
        }

    # ============================================================
    #  每日消費趨勢預測（指數平滑）
    # ============================================================

    def predict_daily_spending(self, trip_id: int) -> dict:
        """
        使用指數平滑法預測每日消費趨勢

        純 Python 實作，無需外部套件：
        smoothed[0] = data[0]
        smoothed[i] = alpha * data[i] + (1-alpha) * smoothed[i-1]

        參數：
            trip_id: 旅行 ID

        回傳：
            dict: {historical, predicted_next, trend}
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT DATE(txn_datetime) AS day, SUM(amount_twd) AS daily_total
                FROM transactions
                WHERE trip_id = ?
                GROUP BY DATE(txn_datetime)
                ORDER BY day
            """, (trip_id,))
            rows = cursor.fetchall()

        if not rows:
            return {
                "historical": [],
                "predicted_next": 0.0,
                "trend": "stable",
                "message": "尚無交易資料",
            }

        dates = [r[0] for r in rows]
        amounts = [r[1] for r in rows]

        # 指數平滑
        alpha = EXP_SMOOTHING_ALPHA
        smoothed = [amounts[0]]
        for i in range(1, len(amounts)):
            s = alpha * amounts[i] + (1 - alpha) * smoothed[i - 1]
            smoothed.append(round(s, 2))

        historical = [
            {"date": d, "actual": a, "smoothed": s}
            for d, a, s in zip(dates, amounts, smoothed)
        ]

        predicted_next = round(smoothed[-1], 2)

        # 趨勢判斷：比較最後三天平均 vs 最初三天平均
        n = len(amounts)
        if n >= 6:
            early_avg = sum(amounts[:3]) / 3
            late_avg = sum(amounts[-3:]) / 3
            ratio = late_avg / early_avg if early_avg > 0 else 1.0
            if ratio > 1.15:
                trend = "up"
            elif ratio < 0.85:
                trend = "down"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "historical": historical,
            "predicted_next": predicted_next,
            "trend": trend,
        }

    # ============================================================
    #  超支警告
    # ============================================================

    def check_overspend(
        self, trip_id: int, user_id: int, threshold: float = OVERSPEND_THRESHOLD
    ) -> list:
        """
        檢查今日消費是否超過日均的 threshold 倍

        參數：
            trip_id: 旅行 ID
            user_id: 使用者 ID
            threshold: 觸發警告的倍數門檻（預設 1.5 倍）

        回傳：
            list[dict]: 觸發的警告列表
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        alerts = []

        with self._db() as (conn, cursor):
            # 今日消費
            cursor.execute("""
                SELECT COALESCE(SUM(amount_twd), 0)
                FROM transactions
                WHERE trip_id = ? AND DATE(txn_datetime) = DATE('now')
            """, (trip_id,))
            today_spent = cursor.fetchone()[0]

            # 旅行總消費與天數（計算日均）
            cursor.execute("""
                SELECT COALESCE(SUM(amount_twd), 0),
                       COUNT(DISTINCT DATE(txn_datetime))
                FROM transactions WHERE trip_id = ?
            """, (trip_id,))
            total_spent, days_elapsed = cursor.fetchone()

        if days_elapsed > 0 and today_spent > 0:
            daily_avg = total_spent / days_elapsed
            if daily_avg > 0 and today_spent > threshold * daily_avg:
                alerts.append({
                    "alert_type": "daily_overspend",
                    "severity": "warning",
                    "title": "今日消費超標",
                    "message": (
                        f"今日消費 NT${today_spent:,.0f} 超過日均消費 "
                        f"NT${daily_avg:,.0f} 的 {threshold:.0%}"
                    ),
                })

        return alerts

    # ============================================================
    #  綜合提醒產生
    # ============================================================

    def generate_all_alerts(self, trip_id: int, user_id: int) -> list:
        """
        執行全部檢查並產生智慧提醒，寫入 spending_alerts 表

        參數：
            trip_id: 旅行 ID
            user_id: 使用者 ID

        回傳：
            list[dict]: 所有產生的提醒
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        generated = []

        # 1. 預算超支預測
        exceed = self.predict_budget_exceed_day(trip_id)
        if exceed.get("will_exceed"):
            days = exceed.get("days_until_exceed")
            msg = (
                f"依目前消費速率，預計在第 {exceed.get('exceed_day')} 天超出預算，"
                f"剩餘 {days} 天需特別注意支出"
            ) if days is not None else "預計將超出旅行預算"
            generated.append({
                "trip_id": trip_id,
                "user_id": user_id,
                "alert_type": "prediction",
                "severity": "warning" if days and days > 1 else "critical",
                "title": "預算超支預警",
                "message": msg,
            })

        # 2. 今日超支檢查
        overspend_alerts = self.check_overspend(trip_id, user_id)
        generated.extend([{**a, "trip_id": trip_id, "user_id": user_id} for a in overspend_alerts])

        # 3. 匯率波動檢查
        try:
            trip = self._get_trip_info(trip_id)
            currency = trip.get("currency_code", "JPY")
            if currency != "TWD":
                from src.fx_strategy import FxStrategy
                fx = FxStrategy(self.db_path)
                advice = fx.advise(currency, 10000)
                if advice.get("recommendation") == "wait":
                    generated.append({
                        "trip_id": trip_id,
                        "user_id": user_id,
                        "alert_type": "rate_spike",
                        "severity": "info",
                        "title": "匯率偏低提醒",
                        "message": advice.get("message", "目前匯率偏低，建議等待更佳換匯時機"),
                    })
        except Exception:
            pass

        # 寫入資料庫
        with self._db() as (conn, cursor):
            for alert in generated:
                cursor.execute("""
                    INSERT INTO spending_alerts
                    (trip_id, user_id, alert_type, severity, title, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    alert["trip_id"], alert["user_id"],
                    alert["alert_type"], alert["severity"],
                    alert["title"], alert["message"],
                ))
                alert["alert_id"] = cursor.lastrowid

        return generated

    # ============================================================
    #  查詢 / 標記已讀
    # ============================================================

    def get_alerts(self, trip_id: int, user_id: int, unread_only: bool = False) -> list:
        """
        查詢智慧提醒列表

        參數：
            trip_id: 旅行 ID
            user_id: 使用者 ID
            unread_only: 是否只回傳未讀提醒

        回傳：
            list[dict]: 提醒列表
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        query = """
            SELECT alert_id, trip_id, user_id, alert_type, severity,
                   title, message, is_read, created_at
            FROM spending_alerts
            WHERE trip_id = ? AND user_id = ?
        """
        params = [trip_id, user_id]

        if unread_only:
            query += " AND is_read = 0"

        query += " ORDER BY created_at DESC"

        with self._db() as (conn, cursor):
            cursor.execute(query, params)
            rows = cursor.fetchall()

        keys = ["alert_id", "trip_id", "user_id", "alert_type", "severity",
                "title", "message", "is_read", "created_at"]
        return [dict(zip(keys, r)) for r in rows]

    def mark_read(self, alert_id: int) -> None:
        """
        標記提醒為已讀

        參數：
            alert_id: 提醒 ID
        """
        if not isinstance(alert_id, int) or alert_id <= 0:
            raise ValueError(f"alert_id 必須為正整數，收到: {alert_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute(
                "UPDATE spending_alerts SET is_read = 1 WHERE alert_id = ?",
                (alert_id,)
            )

"""
rate_alert.py - 匯率到價提醒模組

功能：
- 建立匯率到價提醒（高於/低於目標匯率觸發）
- 比對當前匯率，自動標記已觸發的提醒
- 查詢提醒列表與歷史紀錄

使用方式：
  from src.rate_alert import RateAlertService
  svc = RateAlertService(db_path)
  svc.create_alert(user_id=1, target_currency="JPY", target_rate=4.8, direction="above")
  triggered = svc.check_alerts(user_id=1)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

VALID_DIRECTIONS = ("above", "below")


class RateAlertService:
    """匯率到價提醒服務"""

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
    #  建立提醒
    # ============================================================

    def create_alert(
        self,
        user_id: int,
        target_currency: str,
        target_rate: float,
        direction: str = "above",
        note: str = None,
    ) -> dict:
        """
        建立匯率到價提醒

        參數：
            user_id: 使用者 ID
            target_currency: 目標幣別（例如 "JPY"）
            target_rate: 目標匯率（1 TWD 可換多少外幣）
            direction: 觸發方向，"above" = 高於目標時觸發，"below" = 低於目標時觸發
            note: 備註說明

        回傳：
            dict: 新建立的提醒資料
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency 必須為非空字串，收到: {target_currency!r}")
        if not isinstance(target_rate, (int, float)) or target_rate <= 0:
            raise ValueError(f"target_rate 必須大於 0，收到: {target_rate!r}")
        if direction not in VALID_DIRECTIONS:
            raise ValueError(f"direction 必須為 'above' 或 'below'，收到: {direction!r}")

        target_currency = target_currency.upper()

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT INTO rate_alerts
                (user_id, base_currency, target_currency, target_rate, direction, note)
                VALUES (?, 'TWD', ?, ?, ?, ?)
            """, (user_id, target_currency, float(target_rate), direction, note))
            alert_id = cursor.lastrowid

        return self._get_alert_by_id(alert_id)

    def _get_alert_by_id(self, alert_id: int) -> dict:
        """取得單筆提醒資料"""
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT alert_id, user_id, base_currency, target_currency,
                       target_rate, direction, current_rate, is_triggered,
                       triggered_at, is_active, note, created_at
                FROM rate_alerts WHERE alert_id = ?
            """, (alert_id,))
            row = cursor.fetchone()

        if not row:
            return {}
        return self._row_to_dict(row)

    def _row_to_dict(self, row: tuple) -> dict:
        keys = [
            "alert_id", "user_id", "base_currency", "target_currency",
            "target_rate", "direction", "current_rate", "is_triggered",
            "triggered_at", "is_active", "note", "created_at",
        ]
        return dict(zip(keys, row))

    # ============================================================
    #  查詢提醒
    # ============================================================

    def get_alerts(self, user_id: int, active_only: bool = True) -> list:
        """
        取得使用者的提醒列表

        參數：
            user_id: 使用者 ID
            active_only: 是否只回傳啟用中的提醒

        回傳：
            list[dict]: 提醒列表，依建立時間倒序排列
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        query = """
            SELECT alert_id, user_id, base_currency, target_currency,
                   target_rate, direction, current_rate, is_triggered,
                   triggered_at, is_active, note, created_at
            FROM rate_alerts
            WHERE user_id = ?
        """
        params = [user_id]

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY created_at DESC"

        with self._db() as (conn, cursor):
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_dict(r) for r in rows]

    def get_triggered_alerts(self, user_id: int) -> list:
        """
        取得使用者已觸發的提醒

        參數：
            user_id: 使用者 ID

        回傳：
            list[dict]: 已觸發的提醒，依觸發時間倒序排列
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT alert_id, user_id, base_currency, target_currency,
                       target_rate, direction, current_rate, is_triggered,
                       triggered_at, is_active, note, created_at
                FROM rate_alerts
                WHERE user_id = ? AND is_triggered = 1
                ORDER BY triggered_at DESC
            """, (user_id,))
            rows = cursor.fetchall()

        return [self._row_to_dict(r) for r in rows]

    # ============================================================
    #  檢查觸發
    # ============================================================

    def check_alerts(self, user_id: int) -> list:
        """
        比對當前匯率，觸發符合條件的提醒

        參數：
            user_id: 使用者 ID

        回傳：
            list[dict]: 本次新觸發的提醒列表
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        active_alerts = self.get_alerts(user_id, active_only=True)
        untriggered = [a for a in active_alerts if not a["is_triggered"]]

        if not untriggered:
            return []

        # 取得各幣別目前匯率
        try:
            from src.currency import CurrencyManager
            cm = CurrencyManager(self.db_path)
        except ImportError:
            return []

        triggered = []
        for alert in untriggered:
            currency = alert["target_currency"]
            try:
                current_rate = cm.get_rate(currency)
            except Exception:
                continue

            condition_met = False
            if alert["direction"] == "above" and current_rate >= alert["target_rate"]:
                condition_met = True
            elif alert["direction"] == "below" and current_rate <= alert["target_rate"]:
                condition_met = True

            if condition_met:
                with self._db() as (conn, cursor):
                    cursor.execute("""
                        UPDATE rate_alerts
                        SET is_triggered = 1,
                            triggered_at = datetime('now'),
                            current_rate = ?
                        WHERE alert_id = ?
                    """, (current_rate, alert["alert_id"]))
                alert["is_triggered"] = 1
                alert["current_rate"] = current_rate
                triggered.append(alert)

        return triggered

    # ============================================================
    #  停用提醒
    # ============================================================

    def deactivate_alert(self, alert_id: int) -> None:
        """
        停用指定的提醒

        參數：
            alert_id: 提醒 ID
        """
        if not isinstance(alert_id, int) or alert_id <= 0:
            raise ValueError(f"alert_id 必須為正整數，收到: {alert_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute(
                "UPDATE rate_alerts SET is_active = 0 WHERE alert_id = ?",
                (alert_id,)
            )

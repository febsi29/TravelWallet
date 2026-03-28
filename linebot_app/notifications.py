# -*- coding: utf-8 -*-
"""
推播通知服務。

提供 NotificationService 類別，用於在旅行成員新增交易時，
透過 LINE push_message 主動推播分帳通知給同行成員（排除付款人）。
"""

import sqlite3
import logging
from typing import Any

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from config.settings import DB_PATH, LINE_CHANNEL_ACCESS_TOKEN

logger = logging.getLogger(__name__)


class NotificationService:
    """
    LINE 推播通知服務。

    使用 singleton 模式管理 MessagingApi 實例，
    以避免每次推播都重新建立 HTTP 連線。
    """

    def __init__(self) -> None:
        configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        self._api_client = ApiClient(configuration)
        self._messaging_api = MessagingApi(self._api_client)

    def notify_new_transaction(
        self,
        trip_id: int,
        txn_data: dict[str, Any],
        payer_line_id: str,
    ) -> None:
        """
        當旅行中新增一筆交易時，推播通知給所有成員（排除付款人）。

        Args:
            trip_id:        旅行 ID
            txn_data:       交易資料字典，需包含 category、amount_twd、paid_by（user_id）
            payer_line_id:  付款人的 LINE user_id（用於排除推播對象）
        """
        try:
            trip_name, payer_name, category, amount_twd, member_line_ids, share_per_person = (
                self._fetch_notification_data(trip_id, txn_data, payer_line_id)
            )
        except sqlite3.Error as exc:
            logger.error("查詢推播所需資料時發生資料庫錯誤 (trip_id=%d): %s", trip_id, exc)
            return
        except KeyError as exc:
            logger.error("txn_data 缺少必要欄位: %s", exc)
            return

        if not member_line_ids:
            logger.debug("旅行 %d 沒有其他成員需要通知", trip_id)
            return

        message_text = (
            f"{payer_name} 在「{trip_name}」新增了一筆 {category} NT${amount_twd:,.0f}，"
            f"你的分攤金額為 NT${share_per_person:,.0f}"
        )

        for line_id in member_line_ids:
            self._push_text(line_id, message_text)

    def _fetch_notification_data(
        self,
        trip_id: int,
        txn_data: dict[str, Any],
        payer_line_id: str,
    ) -> tuple[str, str, str, float, list[str], float]:
        """
        從資料庫查詢推播所需的旅行名稱、付款人姓名、成員清單與分攤金額。

        回傳：(trip_name, payer_name, category, amount_twd, member_line_ids, share_per_person)
        """
        paid_by: int = int(txn_data["paid_by"])
        amount_twd: float = float(txn_data["amount_twd"])
        category: str = str(txn_data.get("category", "其他"))

        with sqlite3.connect(DB_PATH) as conn:
            # 取得旅行名稱
            cursor = conn.execute(
                "SELECT trip_name FROM trips WHERE trip_id = ?",
                (trip_id,),
            )
            trip_row = cursor.fetchone()
            trip_name: str = trip_row[0] if trip_row else f"旅行 #{trip_id}"

            # 取得付款人顯示名稱
            cursor = conn.execute(
                "SELECT display_name FROM users WHERE user_id = ?",
                (paid_by,),
            )
            payer_row = cursor.fetchone()
            payer_name: str = payer_row[0] if payer_row else "某人"

            # 查詢 line_user_id 欄位是否存在
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            if "line_user_id" not in columns:
                logger.warning("users 資料表尚無 line_user_id 欄位，無法推播")
                return trip_name, payer_name, category, amount_twd, [], 0.0

            # 取得所有旅行成員的 line_user_id（排除付款人）
            cursor = conn.execute(
                """
                SELECT DISTINCT u.line_user_id
                FROM trip_members tm
                JOIN users u ON tm.user_id = u.user_id
                WHERE tm.trip_id = ?
                  AND u.line_user_id IS NOT NULL
                  AND u.line_user_id != ''
                  AND u.line_user_id != ?
                UNION
                SELECT u.line_user_id
                FROM trips t
                JOIN users u ON t.user_id = u.user_id
                WHERE t.trip_id = ?
                  AND u.line_user_id IS NOT NULL
                  AND u.line_user_id != ''
                  AND u.line_user_id != ?
                """,
                (trip_id, payer_line_id, trip_id, payer_line_id),
            )
            member_line_ids: list[str] = [row[0] for row in cursor.fetchall()]

        # 計算每人分攤金額（簡單均分）
        total_members = len(member_line_ids) + 1  # 加上付款人本身
        share_per_person: float = amount_twd / total_members if total_members > 0 else 0.0

        return trip_name, payer_name, category, amount_twd, member_line_ids, share_per_person

    def _push_text(self, line_user_id: str, text: str) -> None:
        """
        向單一使用者推播文字訊息。
        失敗時記錄錯誤日誌，不 raise 例外。
        """
        try:
            self._messaging_api.push_message(
                PushMessageRequest(
                    to=line_user_id,
                    messages=[TextMessage(text=text)],
                )
            )
            logger.debug("推播成功 (to=%s)", line_user_id)
        except Exception as exc:
            logger.error("推播失敗 (to=%s): %s", line_user_id, exc)

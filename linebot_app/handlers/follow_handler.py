# -*- coding: utf-8 -*-
"""
加好友事件處理器。

當使用者首次加入或封鎖後重新加入時，觸發此處理器：
1. 取得 LINE 使用者 Profile
2. 將 line_user_id 寫入 users 資料表（若欄位不存在則先執行 ALTER TABLE）
3. 回覆歡迎 Flex Message，包含開啟 TravelWallet 的 LIFF 按鈕
"""

import sqlite3
import logging
from typing import Optional

from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    FlexMessage,
    FlexContainer,
)
from linebot.v3.webhooks import FollowEvent

from config.settings import DB_PATH, LIFF_ID

logger = logging.getLogger(__name__)

# LIFF URL 格式
_LIFF_URL_TEMPLATE = "https://liff.line.me/{liff_id}"


def _ensure_line_user_id_column(conn: sqlite3.Connection) -> None:
    """
    檢查 users 資料表是否有 line_user_id 欄位。
    若不存在，執行 ALTER TABLE 新增之。
    """
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if "line_user_id" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN line_user_id TEXT")
        logger.info("已在 users 資料表新增 line_user_id 欄位")


def _upsert_line_user(
    conn: sqlite3.Connection,
    line_user_id: str,
    display_name: str,
) -> None:
    """
    依 line_user_id 寫入或更新使用者資料。

    若 users 資料表中已有對應的 line_user_id，不做任何變更；
    若沒有，則以 display_name 新增一筆記錄，username 以 line_user_id 代替以確保唯一性。
    """
    # 先嘗試找到已存在的使用者
    cursor = conn.execute(
        "SELECT user_id FROM users WHERE line_user_id = ?",
        (line_user_id,),
    )
    existing = cursor.fetchone()
    if existing is not None:
        logger.debug("使用者 %s 已存在於資料庫，跳過新增", line_user_id)
        return

    # 新增使用者（username 使用 line_user_id 確保唯一）
    conn.execute(
        """
        INSERT INTO users (username, display_name, line_user_id)
        VALUES (?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET line_user_id = excluded.line_user_id
        """,
        (line_user_id, display_name, line_user_id),
    )
    logger.info("已新增 LINE 使用者: %s (%s)", display_name, line_user_id)


def _build_welcome_flex(display_name: str, liff_url: str) -> FlexMessage:
    """
    組裝歡迎用的 Flex Message。

    包含歡迎文字與「開啟 TravelWallet」按鈕。
    """
    container_json = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "歡迎加入 TravelWallet",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#1DB954",
                },
                {
                    "type": "text",
                    "text": f"哈囉，{display_name}！",
                    "size": "md",
                    "color": "#333333",
                    "margin": "sm",
                },
                {
                    "type": "text",
                    "text": "TravelWallet 幫你輕鬆管理旅遊帳單、即時分帳、掌握匯率動態。",
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                    "margin": "sm",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1DB954",
                    "action": {
                        "type": "uri",
                        "label": "開啟 TravelWallet",
                        "uri": liff_url,
                    },
                }
            ],
        },
    }
    return FlexMessage(
        alt_text="歡迎加入 TravelWallet",
        contents=FlexContainer.from_dict(container_json),
    )


def _get_profile_display_name(
    messaging_api: MessagingApi,
    line_user_id: str,
) -> str:
    """
    透過 LINE API 取得使用者顯示名稱。
    若取得失敗，回傳 line_user_id 作為備用名稱。
    """
    try:
        profile = messaging_api.get_profile(line_user_id)
        return profile.display_name
    except Exception as exc:
        logger.warning("無法取得使用者 Profile (%s): %s", line_user_id, exc)
        return line_user_id


def handle_follow(event: FollowEvent, messaging_api: MessagingApi) -> None:
    """
    處理 FollowEvent（加好友事件）的主要入口函式。

    步驟：
    1. 取得使用者 Profile
    2. 寫入資料庫
    3. 回覆歡迎 Flex Message
    """
    line_user_id: str = event.source.user_id
    if not line_user_id:
        logger.warning("FollowEvent 缺少 user_id，略過")
        return

    display_name = _get_profile_display_name(messaging_api, line_user_id)
    liff_url = _LIFF_URL_TEMPLATE.format(liff_id=LIFF_ID) if LIFF_ID else "#"

    # 寫入資料庫
    try:
        with sqlite3.connect(DB_PATH) as conn:
            _ensure_line_user_id_column(conn)
            _upsert_line_user(conn, line_user_id, display_name)
    except sqlite3.Error as exc:
        logger.error("資料庫操作失敗 (user=%s): %s", line_user_id, exc)
        # 資料庫失敗不應阻擋歡迎訊息發送，繼續執行

    # 回覆歡迎訊息
    flex_message = _build_welcome_flex(display_name, liff_url)
    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[flex_message],
            )
        )
    except Exception as exc:
        logger.error("回覆歡迎訊息失敗 (user=%s): %s", line_user_id, exc)

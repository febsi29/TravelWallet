# -*- coding: utf-8 -*-
"""
Postback 事件處理器。

處理來自 Rich Menu 或 Flex Message 按鈕的 PostbackEvent，
依據 action 參數分派至對應邏輯。

支援的 action：
- view_trips  — 列出使用者旅行
- split       — 顯示分帳狀態
- exchange    — 顯示常見匯率
- open_app    — 回覆 LIFF URL
"""

import sqlite3
import logging

from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import PostbackEvent

from config.settings import DB_PATH, LIFF_ID
from linebot_app.handlers.message_handler import (
    _lookup_user_id_by_line_id,
    _cmd_list_trips,
    _cmd_split,
    FALLBACK_RATES,
)

logger = logging.getLogger(__name__)

_LIFF_URL_TEMPLATE = "https://liff.line.me/{liff_id}"

# 顯示於 exchange action 的常見貨幣清單
_COMMON_CURRENCIES = ["JPY", "USD", "EUR", "KRW", "THB", "SGD", "HKD", "AUD"]


def _build_exchange_summary() -> str:
    """
    組裝常見貨幣匯率摘要字串。
    只顯示 _COMMON_CURRENCIES 中的貨幣。
    """
    lines = ["常見貨幣參考匯率（對 TWD，靜態備用）：\n"]
    for code in _COMMON_CURRENCIES:
        rate = FALLBACK_RATES.get(code)
        if rate is not None:
            lines.append(f"1 {code} = NT$ {rate:,.4f}")
    lines.append("\n注意：實際匯率請以銀行公告為準。")
    return "\n".join(lines)


def _parse_action(data: str) -> tuple[str, dict[str, str]]:
    """
    解析 postback data 字串。

    格式：action=view_trips&key=value...
    回傳 (action, params_dict)。
    """
    params: dict[str, str] = {}
    action = ""
    for part in data.split("&"):
        if "=" in part:
            key, _, value = part.partition("=")
            params[key.strip()] = value.strip()
    action = params.pop("action", "")
    return action, params


def handle_postback(event: PostbackEvent, messaging_api: MessagingApi) -> None:
    """
    處理 PostbackEvent 的主要入口函式。

    1. 解析 postback data 取得 action
    2. 依 action 分派邏輯
    3. 回覆 TextMessage
    """
    line_user_id: str = event.source.user_id
    if not line_user_id:
        logger.warning("PostbackEvent 缺少 user_id，略過")
        return

    postback_data: str = event.postback.data or ""
    action, _params = _parse_action(postback_data)

    # 取得資料庫中的 user_id，找不到則自動建立，再 fallback 到 1
    user_id: int | None = None
    if action in ("view_trips", "split", "add_txn"):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                user_id = _lookup_user_id_by_line_id(conn, line_user_id)
        except sqlite3.Error as exc:
            logger.error("查詢使用者 ID 失敗 (line_user_id=%s): %s", line_user_id, exc)

        if user_id is None:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.execute("PRAGMA table_info(users)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if "line_user_id" not in columns:
                        conn.execute("ALTER TABLE users ADD COLUMN line_user_id TEXT")
                    conn.execute(
                        """INSERT INTO users (username, display_name, line_user_id)
                           VALUES (?, ?, ?)
                           ON CONFLICT(username) DO UPDATE SET line_user_id = excluded.line_user_id""",
                        (line_user_id, line_user_id, line_user_id),
                    )
                    row = conn.execute(
                        "SELECT user_id FROM users WHERE line_user_id = ?", (line_user_id,)
                    ).fetchone()
                    user_id = int(row[0]) if row else None
            except sqlite3.Error as exc:
                logger.error("自動建立使用者失敗 (line_user_id=%s): %s", line_user_id, exc)

        if user_id is None:
            user_id = 1  # fallback 示範資料

    reply_text: str

    if action == "view_trips":
        try:
            with sqlite3.connect(DB_PATH) as conn:
                reply_text = _cmd_list_trips(conn, user_id)
        except sqlite3.Error as exc:
            logger.error("查詢旅行失敗 (user_id=%d): %s", user_id, exc)
            reply_text = "查詢旅行時發生錯誤，請稍後再試。"

    elif action == "add_txn":
        liff_url = _LIFF_URL_TEMPLATE.format(liff_id=LIFF_ID) if LIFF_ID else f"https://travelwallet-web.onrender.com"
        reply_text = f"請開啟 TravelWallet 新增交易：\n{liff_url}"

    elif action == "split":
        try:
            with sqlite3.connect(DB_PATH) as conn:
                reply_text = _cmd_split(conn, user_id)
        except sqlite3.Error as exc:
            logger.error("查詢分帳失敗 (user_id=%d): %s", user_id, exc)
            reply_text = "查詢分帳時發生錯誤，請稍後再試。"

    elif action == "exchange":
        reply_text = _build_exchange_summary()

    elif action == "open_app":
        liff_url = _LIFF_URL_TEMPLATE.format(liff_id=LIFF_ID) if LIFF_ID else "#"
        reply_text = f"點選以下連結開啟 TravelWallet：\n{liff_url}"

    else:
        logger.warning("收到未知 postback action: %s (data=%s)", action, postback_data)
        reply_text = f"未知的操作：{action}"

    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )
    except Exception as exc:
        logger.error("回覆 Postback 訊息失敗 (line_user_id=%s): %s", line_user_id, exc)

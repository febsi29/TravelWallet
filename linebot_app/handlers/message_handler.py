# -*- coding: utf-8 -*-
"""
文字訊息事件處理器。

支援以下指令：
- 查旅行 / 我的旅行  — 列出使用者的旅行清單
- 分帳              — 顯示最近一趟旅行的分帳狀態
- 匯率 XXX          — 回傳指定貨幣對 TWD 的匯率（使用備用靜態匯率表）
- 餘額              — 顯示錢包各幣別餘額
- 其他              — 回覆使用說明
"""

import sqlite3
import logging
from typing import Optional

from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent

from config.settings import DB_PATH

logger = logging.getLogger(__name__)

# 備用靜態匯率表（1 TWD 可換多少外幣的倒數，即 1 外幣 = ? TWD）
FALLBACK_RATES: dict[str, float] = {
    "JPY": 0.22,
    "USD": 32.5,
    "EUR": 35.2,
    "KRW": 0.024,
    "THB": 0.91,
    "GBP": 41.0,
    "HKD": 4.16,
    "SGD": 24.1,
    "AUD": 21.0,
    "CNY": 4.48,
    "MYR": 7.1,
    "VND": 0.0013,
}

# 使用說明文字
_HELP_TEXT = (
    "TravelWallet 指令說明：\n"
    "- 查旅行 / 我的旅行：列出你的旅行\n"
    "- 分帳：顯示最近旅行的分帳狀態\n"
    "- 匯率 JPY（或其他貨幣代碼）：查詢匯率\n"
    "- 餘額：顯示錢包餘額\n"
    "\n"
    "支援的貨幣：" + "、".join(sorted(FALLBACK_RATES.keys()))
)


def _lookup_user_id_by_line_id(
    conn: sqlite3.Connection, line_user_id: str
) -> Optional[int]:
    """依 line_user_id 查詢 users 資料表，回傳 user_id；找不到則回傳 None。"""
    # 先確認 line_user_id 欄位存在
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if "line_user_id" not in columns:
        return None

    cursor = conn.execute(
        "SELECT user_id FROM users WHERE line_user_id = ?",
        (line_user_id,),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else None


def _cmd_list_trips(conn: sqlite3.Connection, user_id: int) -> str:
    """
    查詢使用者所有旅行（包含以 trip_members 加入的旅行）。
    回傳格式化字串。
    """
    cursor = conn.execute(
        """
        SELECT DISTINCT t.trip_name, t.destination, t.start_date, t.end_date, t.status
        FROM trips t
        LEFT JOIN trip_members tm ON t.trip_id = tm.trip_id
        WHERE t.user_id = ? OR tm.user_id = ?
        ORDER BY t.start_date DESC
        LIMIT 10
        """,
        (user_id, user_id),
    )
    rows = cursor.fetchall()
    if not rows:
        return "目前沒有任何旅行記錄。\n可以在 TravelWallet 中建立你的第一趟旅行！"

    lines = ["你的旅行清單：\n"]
    for i, (name, dest, start, end, status) in enumerate(rows, 1):
        status_label = {"planning": "規劃中", "ongoing": "進行中", "completed": "已結束"}.get(
            status, status
        )
        lines.append(f"{i}. {name}（{dest}）")
        lines.append(f"   {start} ~ {end}｜{status_label}")
    return "\n".join(lines)


def _cmd_split(conn: sqlite3.Connection, user_id: int) -> str:
    """
    查詢使用者最近一趟旅行的分帳狀態。
    """
    # 取得最近一趟旅行
    cursor = conn.execute(
        """
        SELECT t.trip_id, t.trip_name, t.currency_code
        FROM trips t
        LEFT JOIN trip_members tm ON t.trip_id = tm.trip_id
        WHERE t.user_id = ? OR tm.user_id = ?
        ORDER BY t.start_date DESC
        LIMIT 1
        """,
        (user_id, user_id),
    )
    trip_row = cursor.fetchone()
    if not trip_row:
        return "找不到旅行記錄，請先建立旅行。"

    trip_id, trip_name, currency = trip_row

    # 查詢該旅行的分帳摘要
    cursor = conn.execute(
        """
        SELECT u.display_name, SUM(sd.share_twd) AS total_share,
               SUM(CASE WHEN sd.is_settled = 1 THEN sd.share_twd ELSE 0 END) AS settled
        FROM split_details sd
        JOIN transactions tx ON sd.txn_id = tx.txn_id
        JOIN users u ON sd.user_id = u.user_id
        WHERE tx.trip_id = ?
        GROUP BY sd.user_id
        """,
        (trip_id,),
    )
    splits = cursor.fetchall()
    if not splits:
        return f"旅行「{trip_name}」尚無分帳記錄。"

    lines = [f"旅行「{trip_name}」分帳狀態：\n"]
    for name, total, settled in splits:
        owed = total - settled
        lines.append(f"- {name}：應付 NT${total:,.0f}，已結清 NT${settled:,.0f}，未結清 NT${owed:,.0f}")
    return "\n".join(lines)


def _cmd_exchange(currency_code: str) -> str:
    """
    從 FALLBACK_RATES 查詢匯率並回傳結果字串。
    """
    code = currency_code.upper().strip()
    rate = FALLBACK_RATES.get(code)
    if rate is None:
        supported = "、".join(sorted(FALLBACK_RATES.keys()))
        return f"不支援貨幣代碼 {code}。\n目前支援：{supported}"
    return f"參考匯率（靜態備用）\n1 {code} = NT$ {rate:,.4f}\n\n注意：實際匯率請以銀行公告為準。"


def _cmd_balance(conn: sqlite3.Connection, user_id: int) -> str:
    """
    查詢使用者的錢包餘額。
    """
    cursor = conn.execute(
        """
        SELECT currency_code, balance, locked_balance
        FROM wallets
        WHERE user_id = ?
        ORDER BY currency_code
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        return "目前沒有任何錢包餘額記錄。"

    lines = ["你的錢包餘額：\n"]
    for currency, balance, locked in rows:
        lines.append(f"- {currency}：{balance:,.2f}（鎖定中：{locked:,.2f}）")
    return "\n".join(lines)


def _dispatch_command(text: str, user_id: int) -> str:
    """
    根據指令文字分派至對應的處理邏輯，回傳回覆字串。
    """
    stripped = text.strip()

    # 查旅行 / 我的旅行
    if stripped in ("查旅行", "我的旅行"):
        with sqlite3.connect(DB_PATH) as conn:
            return _cmd_list_trips(conn, user_id)

    # 分帳
    if stripped == "分帳":
        with sqlite3.connect(DB_PATH) as conn:
            return _cmd_split(conn, user_id)

    # 匯率 XXX
    if stripped.startswith("匯率"):
        parts = stripped.split()
        if len(parts) >= 2:
            return _cmd_exchange(parts[1])
        return "請輸入貨幣代碼，例如：匯率 JPY"

    # 餘額
    if stripped == "餘額":
        with sqlite3.connect(DB_PATH) as conn:
            return _cmd_balance(conn, user_id)

    # 其他
    return _HELP_TEXT


def handle_text_message(event: MessageEvent, messaging_api: MessagingApi) -> None:
    """
    處理 TextMessageEvent 的主要入口函式。

    1. 取得 LINE user_id 並查對應的 user_id
    2. 分派指令
    3. 回覆 TextMessage
    """
    line_user_id: str = event.source.user_id
    if not line_user_id:
        logger.warning("TextMessageEvent 缺少 user_id，略過")
        return

    text: str = event.message.text or ""

    # 查詢資料庫中的 user_id
    try:
        with sqlite3.connect(DB_PATH) as conn:
            user_id = _lookup_user_id_by_line_id(conn, line_user_id)
    except sqlite3.Error as exc:
        logger.error("查詢使用者 ID 失敗 (line_user_id=%s): %s", line_user_id, exc)
        user_id = None

    if user_id is None:
        reply_text = "請先加我為好友重新綁定，或確認已完成帳號連結。"
    else:
        try:
            reply_text = _dispatch_command(text, user_id)
        except sqlite3.Error as exc:
            logger.error("指令執行時資料庫錯誤 (user_id=%d): %s", user_id, exc)
            reply_text = "查詢資料時發生錯誤，請稍後再試。"
        except Exception as exc:
            logger.exception("指令執行時發生未預期錯誤 (user_id=%d): %s", user_id, exc)
            reply_text = "系統發生錯誤，請稍後再試。"

    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )
    except Exception as exc:
        logger.error("回覆訊息失敗 (line_user_id=%s): %s", line_user_id, exc)

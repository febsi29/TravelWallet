# -*- coding: utf-8 -*-
"""
LINE Bot Webhook 入口點。

負責接收 LINE 平台的 HTTP 回呼請求，驗證簽名後將事件分派至各處理器。
"""

import logging
import threading
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from linebot.v3.webhook import WebhookParser
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    PostbackEvent,
)

from config.settings import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN
from linebot_app.handlers.follow_handler import handle_follow
from linebot_app.handlers.message_handler import handle_text_message
from linebot_app.handlers.postback_handler import handle_postback

logger = logging.getLogger(__name__)

app = FastAPI(title="TravelWallet LINE Bot")


@app.on_event("startup")
async def _seed_on_startup() -> None:
    """在背景執行 seed_data，不阻擋 port 綁定。"""
    def _run() -> None:
        try:
            from database import seed_data  # noqa: F401 — 執行即觸發 seed
            logger.info("seed_data 執行完成")
        except Exception as exc:
            logger.warning("seed_data 執行失敗（非致命）: %s", exc)

    threading.Thread(target=_run, daemon=True).start()


# 初始化 LINE SDK 元件
_configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
_parser = WebhookParser(LINE_CHANNEL_SECRET)


def _get_messaging_api() -> MessagingApi:
    """建立 MessagingApi 實例（每次請求建立新實例以避免連線複用問題）。"""
    return MessagingApi(ApiClient(_configuration))


@app.get("/health")
async def health_check() -> JSONResponse:
    """健康檢查端點，供 load balancer 或監控服務呼叫。"""
    return JSONResponse(content={"status": "ok"})


@app.post("/callback")
async def callback(request: Request) -> JSONResponse:
    """
    LINE Webhook 主入口。

    驗證 X-Line-Signature 後，逐一分派事件給對應的處理器。
    若簽名驗證失敗，回傳 HTTP 400。
    """
    signature: str = request.headers.get("X-Line-Signature", "")
    body_bytes: bytes = await request.body()
    body_text: str = body_bytes.decode("utf-8")

    try:
        events = _parser.parse(body_text, signature)
    except InvalidSignatureError:
        logger.warning("LINE 簽名驗證失敗")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as exc:
        logger.exception("解析 LINE 事件時發生未預期錯誤: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")

    messaging_api = _get_messaging_api()

    for event in events:
        try:
            if isinstance(event, FollowEvent):
                handle_follow(event, messaging_api)
            elif isinstance(event, MessageEvent) and isinstance(
                event.message, TextMessageContent
            ):
                handle_text_message(event, messaging_api)
            elif isinstance(event, PostbackEvent):
                handle_postback(event, messaging_api)
            else:
                logger.debug("忽略未支援的事件類型: %s", type(event).__name__)
        except Exception as exc:
            logger.exception("處理事件時發生錯誤 (類型=%s): %s", type(event).__name__, exc)
            # 單一事件失敗不影響後續事件處理

    return JSONResponse(content={"status": "ok"})

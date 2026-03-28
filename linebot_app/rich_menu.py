# -*- coding: utf-8 -*-
"""
LINE Rich Menu 建立腳本。
此腳本執行一次即可完成 Rich Menu 的建立與設定。
執行方式：python -m linebot_app.rich_menu
"""

import json
import sys

import requests

from config import settings

# LINE Messaging API 端點
LINE_API_BASE = "https://api.line.me/v2/bot"


def _build_headers() -> dict[str, str]:
    """建立含授權資訊的 HTTP 標頭。"""
    token = settings.LINE_CHANNEL_ACCESS_TOKEN
    if not token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN 未設定，請檢查環境變數。")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _build_rich_menu_body() -> dict:
    """回傳 Rich Menu 定義結構（不含圖片，使用 LINE 預設文字樣式）。"""
    return {
        "size": {"width": 2500, "height": 843},
        "selected": True,
        "name": "TravelWallet選單",
        "chatBarText": "開啟選單",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 500, "height": 843},
                "action": {
                    "type": "postback",
                    "data": "action=view_trips",
                    "displayText": "查旅行",
                },
            },
            {
                "bounds": {"x": 500, "y": 0, "width": 500, "height": 843},
                "action": {
                    "type": "postback",
                    "data": "action=add_txn",
                    "displayText": "新增交易",
                },
            },
            {
                "bounds": {"x": 1000, "y": 0, "width": 500, "height": 843},
                "action": {
                    "type": "postback",
                    "data": "action=split",
                    "displayText": "分帳",
                },
            },
            {
                "bounds": {"x": 1500, "y": 0, "width": 500, "height": 843},
                "action": {
                    "type": "postback",
                    "data": "action=exchange",
                    "displayText": "匯率",
                },
            },
            {
                "bounds": {"x": 2000, "y": 0, "width": 500, "height": 843},
                "action": {
                    "type": "postback",
                    "data": "action=open_app",
                    "displayText": "開啟App",
                },
            },
        ],
    }


def create_rich_menu(headers: dict[str, str]) -> str:
    """向 LINE API 建立 Rich Menu，回傳 richMenuId。"""
    body = _build_rich_menu_body()
    url = f"{LINE_API_BASE}/richmenu"
    response = requests.post(url, headers=headers, json=body, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"建立 Rich Menu 失敗：{response.status_code} {response.text}"
        )

    rich_menu_id: str = response.json()["richMenuId"]
    print(f"Rich Menu 建立成功，ID：{rich_menu_id}")
    return rich_menu_id


def set_default_rich_menu(rich_menu_id: str, headers: dict[str, str]) -> None:
    """將指定的 Rich Menu 設為預設選單。"""
    # 設定預設時不需要 Content-Type，只需授權標頭
    auth_headers = {"Authorization": headers["Authorization"]}
    url = f"{LINE_API_BASE}/user/all/richmenu/{rich_menu_id}"
    response = requests.post(url, headers=auth_headers, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"設定預設 Rich Menu 失敗：{response.status_code} {response.text}"
        )

    print(f"已將 Rich Menu（{rich_menu_id}）設為預設選單。")


def main() -> None:
    """主流程：建立 Rich Menu 並設為預設。"""
    try:
        headers = _build_headers()
        rich_menu_id = create_rich_menu(headers)
        set_default_rich_menu(rich_menu_id, headers)
        print("Rich Menu 設定完成。")
    except ValueError as exc:
        print(f"設定錯誤：{exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"API 錯誤：{exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"網路錯誤：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

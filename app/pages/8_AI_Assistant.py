"""
TravelWallet AI Agent - Smart Travel Assistant
Gemini API as primary, rule-based engine as fallback
"""
import streamlit as st
import sqlite3
import os
import sys
import json
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

from src.split import SplitEngine
from src.currency import CurrencyManager, COMMON_CURRENCIES, FALLBACK_RATES
from src.planner import TripPlanner, DESTINATION_FACTORS
from src.analytics import Analytics
from src.anomaly import AnomalyDetector
from src.budget import BudgetManager

# ============================================================
#  Service Instances
# ============================================================

engine = SplitEngine(DB_PATH)
cm = CurrencyManager(DB_PATH)
planner = TripPlanner(DB_PATH)
ana = Analytics(DB_PATH)
detector = AnomalyDetector(DB_PATH)
bm = BudgetManager(DB_PATH)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
)

# ============================================================
#  預設旅遊規劃 Prompt
# ============================================================

DEFAULT_TRAVEL_PROMPT = """你是一個專業旅遊規劃助理，請為使用者規劃一趟「東京自由行」行程，符合便宜、好玩、好拍照、不累、避免踩雷等需求，並提供清楚、可執行的詳細建議。
請根據使用者需求，設計完整且實用的旅遊計畫，包括每日行程安排、交通建議、預算控制技巧、美食推薦與拍照亮點，確保行程順暢、不折返、不過度拉車、不安排評價過低或觀光陷阱行程。
在提出最終行程前，請先進行規劃邏輯思考，確保：
- 行程動線合理（同區域安排在同一天）
- 每日步行與交通時間不過長
- 熱門景點避開尖峰或給替代建議
- 平衡景點、美食、拍照、休息時間
- 提供價格親民或高CP值選項

# Steps
1. 旅遊基本設定推估（若使用者未提供）
- 預設旅遊天數（3–5天合理安排）
- 住宿區域假設（如上野/淺草/新宿其中一區）
- 出發季節採一般旅遊旺季標準規劃
- 預設適合第一次東京自由行旅客
2. 行程規劃邏輯（需先內部推理後再輸出結果）
- 區域分配（例如：淺草上野一天、澀谷原宿一天、新宿一天等）
- 避免跨區來回
- 每日最多 3–4 個主要景點
- 安排至少 1 個拍照亮點
- 安排 1–2 間高評價平價美食
- 預留休息或彈性時間
3. 預算控制建議
- 免費景點或低門票景點優先
- 平價餐廳（人均合理日幣價格範圍）
- 交通票券建議（是否需要地鐵券）
4. 防踩雷設計
- 避開評價明顯兩極或過度觀光化餐廳
- 提醒避開尖峰時段
- 如為爆紅名店，給平替選項
5. 最後輸出完整每日行程安排與總結建議

# Output Format
請使用以下結構輸出（以Markdown呈現）：
1. 行程總覽（簡述本次旅行風格與特色，約150字內）
2. 每日詳細行程（依 Day 1 / Day 2 / Day 3… 分段）
- 上午：
- 午餐建議：
- 下午：
- 晚餐建議：
- 拍照亮點：
- 小省錢技巧：
3. 交通與票券建議
4. 預算概抓（以日幣估算區間）
5. 防踩雷提醒
6. 加分可替代選項（如下雨備案或體力不足時方案）

篇幅建議：1000–1800字
語氣：親切、實用、像旅遊部落客但不浮誇
內容需具體（提供真實地區與類型建議，但避免虛構商家）"""

# ============================================================
#  Rule-Based Engine (Fallback)
# ============================================================

def rule_based_response(user_input: str) -> str | None:
    """Keyword-based intent detection and response"""
    text = user_input.lower()

    # --- Currency / Exchange Rate ---
    currency_keywords = ["匯率", "換算", "日圓", "美金", "韓元", "泰銖", "歐元", "英鎊", "換錢", "exchange", "rate"]
    if any(k in text for k in currency_keywords):
        found_code = None
        name_map = {
            "日圓": "JPY", "日幣": "JPY", "美金": "USD", "美元": "USD",
            "韓元": "KRW", "韓幣": "KRW", "泰銖": "THB", "歐元": "EUR",
            "英鎊": "GBP", "澳幣": "AUD", "港幣": "HKD", "人民幣": "CNY",
            "新加坡": "SGD", "馬來": "MYR", "越南": "VND",
        }
        for name, code in name_map.items():
            if name in text:
                found_code = code
                break

        if found_code:
            try:
                rate = cm.get_rate(found_code)
                info = cm.get_currency_info(found_code)
                twd_per = round(1 / rate, 2) if rate > 0 else 0

                amounts = re.findall(r'[\d,]+', text.replace(",", ""))
                if amounts:
                    amt = float(amounts[0])
                    converted = cm.quick_convert(amt, found_code, "TWD")
                    return (
                        f"**{info['name']}（{found_code}）匯率**\n\n"
                        f"- 1 TWD = {rate:.4f} {found_code}\n"
                        f"- 1 {found_code} = NT${twd_per}\n\n"
                        f"{info['symbol']}{amt:,.0f} = **NT${converted:,.0f}**"
                    )

                return (
                    f"**{info['name']}（{found_code}）匯率**\n\n"
                    f"- 1 TWD = {rate:.4f} {found_code}\n"
                    f"- 1 {found_code} = NT${twd_per}\n\n"
                    f"需要換算金額的話，直接告訴我數字就好！"
                )
            except Exception:
                return "抱歉，目前無法取得匯率資訊，請稍後再試。"
        else:
            lines = ["**目前主要貨幣匯率**\n"]
            for code in ["JPY", "USD", "KRW", "THB", "EUR"]:
                try:
                    rate = cm.get_rate(code)
                    info = cm.get_currency_info(code)
                    twd_per = round(1 / rate, 2) if rate > 0 else 0
                    lines.append(f"- {info['name']}: 1 {code} = NT${twd_per}")
                except Exception:
                    pass
            return "\n".join(lines)

    # --- Budget Planning ---
    plan_keywords = ["預算", "規劃", "plan", "budget", "花多少", "要帶多少", "行程", "幾天", "幾人"]
    days_match = re.search(r'(\d+)\s*[天日]', text)
    people_match = re.search(r'(\d+)\s*[人個位]', text)
    has_numbers = bool(days_match or people_match)

    # 偵測訊息中是否含有支援的目的地
    matched_dest = None
    for d in DESTINATION_FACTORS.keys():
        if d in text:
            matched_dest = d
            break

    # 若無目的地但有天數/人數，沿用上一次目的地（對話追蹤）
    if not matched_dest and has_numbers:
        matched_dest = st.session_state.get("last_dest")

    if any(k in text for k in plan_keywords) or matched_dest:
        dest = matched_dest

        days = int(days_match.group(1)) if days_match else 5
        people = int(people_match.group(1)) if people_match else 1

        if dest:
            # 儲存目的地供後續對話使用
            st.session_state.last_dest = dest
            plan = planner.suggest_budget(dest, days, people)
            std = plan["tiers"]["standard"]
            bud = plan["tiers"]["budget"]
            pre = plan["tiers"]["premium"]
            return (
                f"**{dest} {days}天 {people}人 預算建議**\n\n"
                f"| 方案 | 每人每日 | 每人總計 |\n"
                f"|------|---------|--------|\n"
                f"| 省錢 | NT${bud['daily_per_person']:,} | NT${bud['total_per_person']:,} |\n"
                f"| 標準 | NT${std['daily_per_person']:,} | NT${std['total_per_person']:,} |\n"
                f"| 豪華 | NT${pre['daily_per_person']:,} | NT${pre['total_per_person']:,} |\n\n"
                f"輸入天數和人數可以調整計算！"
            )
        else:
            dests = "、".join(list(DESTINATION_FACTORS.keys()))
            return f"我支援以下旅遊地點：{dests}\n\n請告訴我目的地、天數和人數，我幫你規劃！"

    # --- Split Bill ---
    split_keywords = ["分帳", "結算", "誰欠", "欠款", "split", "owe", "settle", "帳"]
    if any(k in text for k in split_keywords):
        try:
            balances = engine.get_net_balances(1)
            transfers = engine.settle_trip(1)

            lines = ["**分帳結算**\n"]
            lines.append("**個人餘額**")
            for uid, info in balances.items():
                b = info["balance"]
                label = "（應收）" if b > 0 else "（應付）"
                lines.append(f"- {info['name']}: ¥{b:,.0f} {label}")

            lines.append(f"\n**需要 {len(transfers)} 筆轉帳完成結算**")
            for t in transfers:
                lines.append(f"- {t['from_name']} 付給 {t['to_name']}: ¥{t['amount']:,.0f} (NT${t['amount_twd']:,})")

            return "\n".join(lines)
        except Exception:
            return "抱歉，無法取得分帳資訊，請稍後再試。"

    # --- Analytics ---
    analytics_keywords = ["分析", "消費", "統計", "花費", "支出", "報告", "比較", "趨勢"]
    if any(k in text for k in analytics_keywords):
        try:
            pvn = ana.personal_vs_national(1)
            p = pvn["personal"]
            n = pvn["national"]
            c = pvn["comparison"]

            cats = ana.category_analysis(1)
            cat_lines = "\n".join([
                f"- {cat['category']}: NT${cat['total_twd']:,.0f} ({cat['percentage']}%)"
                for cat in cats[:5]
            ])

            return (
                f"**消費分析報告**\n\n"
                f"**個人 vs 全國平均**\n"
                f"- 本次每人消費：NT${p['per_person_total']:,}\n"
                f"- 全國平均（{n['year']}）：NT${n['avg_total']:,.0f}\n"
                f"- 差距：{c['diff_pct']:+.1f}%\n"
                f"- {c['verdict']}\n\n"
                f"**消費類別前五名**\n{cat_lines}"
            )
        except Exception:
            return "抱歉，無法取得分析資料，請稍後再試。"

    # --- Anomaly ---
    anomaly_keywords = ["異常", "可疑", "詐騙", "anomaly", "fraud", "警告"]
    if any(k in text for k in anomaly_keywords):
        try:
            summary = detector.get_anomaly_summary(1)
            if summary["anomaly_count"] > 0:
                lines = [f"**偵測到 {summary['anomaly_count']} 筆異常消費**\n"]
                for a in summary["anomalies"]:
                    lines.append(f"- NT${a['amount_twd']:,.0f} | {a['category']} | {a['description']}")
                return "\n".join(lines)
            else:
                return "目前沒有異常消費，所有交易均在正常範圍內！"
        except Exception:
            return "抱歉，無法執行異常偵測，請稍後再試。"

    # --- Budget Status ---
    budget_keywords = ["預算", "健康", "狀態", "剩餘", "burn"]
    budget_scope = ["狀況", "如何", "多少", "查"]
    if any(k in text for k in budget_keywords) and any(k in text for k in budget_scope):
        try:
            health = bm.assess_health(1)
            return (
                f"**預算健康狀況**\n\n"
                f"- 健康分數：{health['score']}/100\n"
                f"- 狀態：{health['status']}\n"
                f"- 已用：NT${health['total_spent']:,}（{health['usage_ratio']}%）\n"
                f"- 預算：NT${health['budget']:,.0f}"
            )
        except Exception:
            return "抱歉，無法取得預算資訊，請稍後再試。"

    # --- Default ---
    return None


# ============================================================
#  Gemini API Call
# ============================================================

def get_context_data() -> str:
    """Gather current data context for Gemini"""
    context_parts = []

    try:
        balances = engine.get_net_balances(1)
        bal_text = ", ".join([f"{info['name']}: ¥{info['balance']:,.0f}" for uid, info in balances.items()])
        context_parts.append(f"Split balances: {bal_text}")
    except Exception:
        pass

    try:
        summary = engine.get_trip_summary(1)
        context_parts.append(
            f"Trip: Tokyo 5 days 4 people, total ¥{summary['total_amount']:,.0f} ({summary['txn_count']} transactions)"
        )
    except Exception:
        pass

    try:
        health = bm.assess_health(1)
        context_parts.append(
            f"Budget: NT${health['budget']:,.0f}, spent NT${health['total_spent']:,} ({health['usage_ratio']}%), score {health['score']}/100"
        )
    except Exception:
        pass

    try:
        for code in ["JPY", "USD", "KRW"]:
            rate = cm.get_rate(code)
            twd_per = round(1 / rate, 2) if rate > 0 else 0
            context_parts.append(f"Exchange: 1 {code} = NT${twd_per}")
    except Exception:
        pass

    return "\n".join(context_parts)


def call_gemini(user_input: str, chat_history: list, custom_prompt: str = "") -> str | None:
    """Call Gemini API with context"""
    if not GEMINI_API_KEY:
        return None

    try:
        import requests
    except ImportError:
        return None

    context = get_context_data()

    travel_section = f"\n\n---\n{custom_prompt}" if custom_prompt.strip() else ""

    system_prompt = f"""You are TravelWallet AI Assistant, a smart travel finance helper for Taiwanese travelers.
You help with: trip budget planning, currency exchange, expense tracking, split bills, anomaly detection.

Current data context:
{context}

Supported destinations for budget planning: {', '.join(DESTINATION_FACTORS.keys())}
Supported currencies: {', '.join(COMMON_CURRENCIES.keys())}

Rules:
- Reply in Traditional Chinese (繁體中文)
- Be helpful and use data from context when relevant
- When asked about budget planning, provide 3 tiers (budget/standard/premium)
- For currency questions, provide the rate and conversion
- For split bill questions, explain who owes whom
{travel_section}
"""

    contents = []
    for msg in chat_history[-6:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    contents.append({"role": "user", "parts": [{"text": user_input}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 3000,
        },
    }

    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=15)
        data = response.json()

        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return None
    except Exception:
        return None


# ============================================================
#  Streamlit Chat UI
# ============================================================

st.title("TravelWallet AI 旅遊助手")
st.caption("詢問旅遊預算、匯率換算、分帳結算、消費分析等問題！")

# 側邊欄：自訂 Prompt 編輯器
with st.sidebar:
    st.markdown("### 自訂旅遊 Prompt")
    with st.expander("編輯 AI 行為指令", expanded=False):
        if "custom_travel_prompt" not in st.session_state:
            st.session_state.custom_travel_prompt = DEFAULT_TRAVEL_PROMPT
        edited = st.text_area(
            "Prompt 內容",
            value=st.session_state.custom_travel_prompt,
            height=300,
            label_visibility="collapsed",
        )
        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button("儲存", use_container_width=True):
                st.session_state.custom_travel_prompt = edited
                st.success("已儲存")
        with col_reset:
            if st.button("還原預設", use_container_width=True):
                st.session_state.custom_travel_prompt = DEFAULT_TRAVEL_PROMPT
                st.rerun()

col1, col2 = st.columns([3, 1])
with col2:
    mode = st.radio(
        "Engine",
        ["AI (Gemini)", "規則引擎"],
        horizontal=True,
        label_visibility="collapsed",
    )

st.markdown("---")
qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
with qcol1:
    if st.button("匯率查詢", use_container_width=True):
        st.session_state.quick_msg = "目前主要貨幣匯率"
with qcol2:
    if st.button("行程規劃", use_container_width=True):
        st.session_state.quick_msg = st.session_state.get("custom_travel_prompt", DEFAULT_TRAVEL_PROMPT)
with qcol3:
    if st.button("分帳結算", use_container_width=True):
        st.session_state.quick_msg = "查看分帳狀況"
with qcol4:
    if st.button("消費分析", use_container_width=True):
        st.session_state.quick_msg = "分析消費紀錄"
with qcol5:
    if st.button("異常偵測", use_container_width=True):
        st.session_state.quick_msg = "檢查異常消費"

st.markdown("---")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "歡迎使用 TravelWallet AI 旅遊助手！\n\n"
                "我可以幫你：\n"
                "- 查詢匯率與換算\n"
                "- 規劃旅遊預算\n"
                "- 計算分帳與結算\n"
                "- 分析消費數據\n"
                "- 偵測異常消費\n\n"
                "請輸入問題，或點擊上方快速按鈕！"
            ),
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


def get_response(prompt: str) -> tuple[str, str]:
    """Return (response_text, source_label)"""
    response = rule_based_response(prompt)
    if response:
        return response, "規則引擎"

    custom_prompt = st.session_state.get("custom_travel_prompt", DEFAULT_TRAVEL_PROMPT)
    response = call_gemini(prompt, st.session_state.messages, custom_prompt)
    if response:
        return response, "Gemini"

    return "抱歉，目前無法處理此問題，請嘗試其他問題。", "備用回覆"


# Handle quick action
if "quick_msg" in st.session_state:
    prompt = st.session_state.pop("quick_msg")
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            response, source = get_response(prompt)
            st.markdown(response)
            st.caption(f"Powered by {source}")

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# Chat input
if prompt := st.chat_input("請輸入問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            if "規則" in mode:
                response = rule_based_response(prompt)
                source = "規則引擎"
                if not response:
                    response = "抱歉，找不到對應的回答，請嘗試其他問題。"
            else:
                response, source = get_response(prompt)

            st.markdown(response)
            st.caption(f"Powered by {source}")

    st.session_state.messages.append({"role": "assistant", "content": response})

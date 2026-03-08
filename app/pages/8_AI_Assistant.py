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

st.set_page_config(page_title="AI Assistant", page_icon=None, layout="wide")

# --- Init modules ---
engine = SplitEngine(DB_PATH)
cm = CurrencyManager(DB_PATH)
planner = TripPlanner(DB_PATH)
ana = Analytics(DB_PATH)
detector = AnomalyDetector(DB_PATH)
bm = BudgetManager(DB_PATH)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# ============================================================
#  Rule-Based Engine (Fallback)
# ============================================================

def rule_based_response(user_input):
    """Keyword-based intent detection and response"""
    text = user_input.lower()
    
    # --- Currency / Exchange Rate ---
    currency_keywords = ["匯率", "換算", "日圓", "美金", "韓元", "泰銖", "歐元", "英鎊", "換錢", "exchange", "rate"]
    if any(k in text for k in currency_keywords):
        # Try to find currency code
        found_code = None
        name_map = {"日圓": "JPY", "日幣": "JPY", "美金": "USD", "美元": "USD",
                     "韓元": "KRW", "韓幣": "KRW", "泰銖": "THB", "歐元": "EUR",
                     "英鎊": "GBP", "澳幣": "AUD", "港幣": "HKD", "人民幣": "CNY",
                     "新加坡": "SGD", "馬來": "MYR", "越南": "VND"}
        for name, code in name_map.items():
            if name in text:
                found_code = code
                break
        
        if found_code:
            try:
                rate = cm.get_rate(found_code)
                info = cm.get_currency_info(found_code)
                twd_per = round(1 / rate, 2) if rate > 0 else 0
                
                # Check if there's an amount to convert
                amounts = re.findall(r'[\d,]+', text.replace(",", ""))
                if amounts:
                    amt = float(amounts[0])
                    converted = cm.quick_convert(amt, found_code, "TWD")
                    return (f"**{info['name']}({found_code})匯率**\n\n"
                            f"- 1 TWD = {rate:.4f} {found_code}\n"
                            f"- 1 {found_code} = NT${twd_per}\n\n"
                            f"{info['symbol']}{amt:,.0f} = **NT${converted:,.0f}**")

                return (f"**{info['name']}({found_code})匯率**\n\n"
                        f"- 1 TWD = {rate:.4f} {found_code}\n"
                        f"- 1 {found_code} = NT${twd_per}\n\n"
                        f"需要換算金額的話，直接告訴我數字就好！")
            except:
                return "抱歉，目前無法取得匯率資訊。"
        else:
            # Show all rates
            lines = ["**目前匯率一覽**\n"]
            for code in ["JPY", "USD", "KRW", "THB", "EUR"]:
                try:
                    rate = cm.get_rate(code)
                    info = cm.get_currency_info(code)
                    twd_per = round(1 / rate, 2) if rate > 0 else 0
                    lines.append(f"- {info['name']}: 1 {code} = NT${twd_per}")
                except:
                    pass
            return "\n".join(lines)
    
    # --- Budget Planning ---
    plan_keywords = ["預算", "規劃", "plan", "budget", "花多少", "要帶多少"]
    dest_keywords = {k: k for k in DESTINATION_FACTORS.keys()}
    if any(k in text for k in plan_keywords):
        dest = None
        for d in DESTINATION_FACTORS.keys():
            if d in text:
                dest = d
                break
        
        days_match = re.search(r'(\d+)\s*[天日]', text)
        days = int(days_match.group(1)) if days_match else 5
        
        people_match = re.search(r'(\d+)\s*[人個位]', text)
        people = int(people_match.group(1)) if people_match else 1
        
        if dest:
            plan = planner.suggest_budget(dest, days, people)
            std = plan["tiers"]["standard"]
            bud = plan["tiers"]["budget"]
            pre = plan["tiers"]["premium"]
            return (f"**{dest} {days}天 {people}人 預算建議**\n\n"
                    f"| 方案 | 每人每日 | 每人總計 |\n"
                    f"|------|---------|--------|\n"
                    f"| 節省版 | NT${bud['daily_per_person']:,} | NT${bud['total_per_person']:,} |\n"
                    f"| 標準版 | NT${std['daily_per_person']:,} | NT${std['total_per_person']:,} |\n"
                    f"| 豪華版 | NT${pre['daily_per_person']:,} | NT${pre['total_per_person']:,} |\n\n"
                    f"資料來源：交通部觀光署統計")
        else:
            dests = "、".join(list(DESTINATION_FACTORS.keys()))
            return f"請告訴我你想去哪裡？目前支援：{dests}\n\n例如：「去日本5天4個人預算多少？」"
    
    # --- Split Bill ---
    split_keywords = ["分帳", "誰欠", "結算", "代墊", "split", "owe", "settle", "付了多少"]
    if any(k in text for k in split_keywords):
        try:
            balances = engine.get_net_balances(1)
            transfers = engine.settle_trip(1)
            
            lines = ["**分帳狀態（東京自由行）**\n"]
            lines.append("**淨餘額：**")
            for uid, info in balances.items():
                b = info["balance"]
                label = "被欠" if b > 0 else "欠人"
                lines.append(f"- {info['name']}: ¥{b:,.0f} ({label})")

            lines.append(f"\n**最佳結算方案（{len(transfers)}筆轉帳）：**")
            for t in transfers:
                lines.append(f"- {t['from_name']} -> {t['to_name']}: ¥{t['amount']:,.0f} (NT${t['amount_twd']:,})")
            
            return "\n".join(lines)
        except:
            return "目前沒有分帳資料，請先建立旅行和交易紀錄。"
    
    # --- Analytics ---
    analytics_keywords = ["分析", "統計", "花最多", "消費", "比較", "全國", "平均", "類別"]
    if any(k in text for k in analytics_keywords):
        try:
            pvn = ana.personal_vs_national(1)
            p = pvn["personal"]
            n = pvn["national"]
            c = pvn["comparison"]
            
            cats = ana.category_analysis(1)
            cat_lines = "\n".join([f"- {cat['category']}: NT${cat['total_twd']:,.0f} ({cat['percentage']}%)" for cat in cats[:5]])
            
            return (f"**消費分析（東京自由行）**\n\n"
                    f"**個人 vs 全國平均：**\n"
                    f"- 你的每人花費：NT${p['per_person_total']:,}\n"
                    f"- 全國平均({n['year']}年)：NT${n['avg_total']:,.0f}\n"
                    f"- 差異：{c['diff_pct']:+.1f}%\n"
                    f"- 評語：{c['verdict']}\n\n"
                    f"**消費類別：**\n{cat_lines}")
        except:
            return "目前沒有足夠的分析資料。"
    
    # --- Anomaly ---
    anomaly_keywords = ["異常", "可疑", "詐騙", "anomaly", "fraud", "奇怪"]
    if any(k in text for k in anomaly_keywords):
        try:
            summary = detector.get_anomaly_summary(1)
            if summary["anomaly_count"] > 0:
                lines = [f"**偵測到 {summary['anomaly_count']} 筆異常消費！**\n"]
                for a in summary["anomalies"]:
                    lines.append(f"- NT${a['amount_twd']:,.0f} | {a['category']} | {a['description']}")
                return "\n".join(lines)
            else:
                return "目前沒有偵測到異常消費，所有交易都在合理範圍內。"
        except:
            return "請先執行異常偵測功能。"
    
    # --- Budget Status ---
    budget_keywords = ["預算", "還能花", "剩多少", "超支", "burn"]
    if any(k in text for k in budget_keywords) and any(k in text for k in ["剩", "還", "超", "狀態"]):
        try:
            health = bm.assess_health(1)
            return (f"**預算健康狀態**\n\n"
                    f"- 評分：{health['score']}/100\n"
                    f"- 狀態：{health['status']}\n"
                    f"- 已花費：NT${health['total_spent']:,} ({health['usage_ratio']}%)\n"
                    f"- 預算：NT${health['budget']:,.0f}")
        except:
            return "目前沒有預算資料。"
    
    # --- Default ---
    return None


# ============================================================
#  Gemini API Call
# ============================================================

def get_context_data():
    """Gather current data context for Gemini"""
    context_parts = []
    
    try:
        balances = engine.get_net_balances(1)
        bal_text = ", ".join([f"{info['name']}: ¥{info['balance']:,.0f}" for uid, info in balances.items()])
        context_parts.append(f"Split balances: {bal_text}")
    except:
        pass
    
    try:
        summary = engine.get_trip_summary(1)
        context_parts.append(f"Trip: Tokyo 5 days 4 people, total ¥{summary['total_amount']:,.0f} ({summary['txn_count']} transactions)")
    except:
        pass
    
    try:
        health = bm.assess_health(1)
        context_parts.append(f"Budget: NT${health['budget']:,.0f}, spent NT${health['total_spent']:,} ({health['usage_ratio']}%), score {health['score']}/100")
    except:
        pass
    
    try:
        for code in ["JPY", "USD", "KRW"]:
            rate = cm.get_rate(code)
            twd_per = round(1 / rate, 2) if rate > 0 else 0
            context_parts.append(f"Exchange: 1 {code} = NT${twd_per}")
    except:
        pass
    
    return "\n".join(context_parts)


def call_gemini(user_input, chat_history):
    """Call Gemini API with context"""
    try:
        import requests
    except ImportError:
        return None
    
    context = get_context_data()
    
    system_prompt = f"""You are TravelWallet AI Assistant, a smart travel finance helper for Taiwanese travelers.
You help with: trip budget planning, currency exchange, expense tracking, split bills, anomaly detection.

Current data context:
{context}

Supported destinations for budget planning: {', '.join(DESTINATION_FACTORS.keys())}
Supported currencies: {', '.join(COMMON_CURRENCIES.keys())}

Rules:
- Reply in Traditional Chinese (繁體中文)
- Be concise and helpful
- Use numbers and data from the context when relevant
- When asked about budget planning, provide 3 tiers (budget/standard/premium)
- For currency questions, provide the rate and conversion
- For split bill questions, explain who owes whom
- Do not use emoji in responses
"""
    
    # Build message history
    contents = []
    for msg in chat_history[-6:]:  # last 6 messages for context
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    contents.append({"role": "user", "parts": [{"text": user_input}]})
    
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
        }
    }
    
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=15)
        data = response.json()
        
        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return None
    except Exception as e:
        return None


# ============================================================
#  Streamlit Chat UI
# ============================================================

st.title("TravelWallet AI Assistant")
st.caption("Ask me anything about travel budgets, exchange rates, split bills, and spending analysis!")

# Mode indicator
col1, col2 = st.columns([3, 1])
with col2:
    mode = st.radio("Engine", ["AI (Gemini)", "Rule-based"], horizontal=True, label_visibility="collapsed")

# Quick action buttons
st.markdown("---")
qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
with qcol1:
    if st.button("查匯率", use_container_width=True):
        st.session_state.quick_msg = "現在日圓匯率多少？"
with qcol2:
    if st.button("預算規劃", use_container_width=True):
        st.session_state.quick_msg = "去日本5天4個人預算多少？"
with qcol3:
    if st.button("分帳狀態", use_container_width=True):
        st.session_state.quick_msg = "現在誰欠誰多少？"
with qcol4:
    if st.button("消費分析", use_container_width=True):
        st.session_state.quick_msg = "幫我分析這趟旅行的消費"
with qcol5:
    if st.button("異常偵測", use_container_width=True):
        st.session_state.quick_msg = "有沒有異常消費？"

st.markdown("---")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "嗨！我是 TravelWallet 智慧助手\n\n我可以幫你：\n- 查詢匯率和換算\n- 規劃旅遊預算\n- 查看分帳狀態和結算方案\n- 分析消費模式\n- 偵測異常消費\n\n直接問我，或點上面的快速按鈕！"}
    ]

# Display chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle quick action
if "quick_msg" in st.session_state:
    prompt = st.session_state.quick_msg
    del st.session_state.quick_msg
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get response
    with st.chat_message("assistant"):
        with st.spinner("thinking..."):
            # Try rule-based first for quick actions
            response = rule_based_response(prompt)
            if response:
                source = "Rule Engine"
            else:
                response = call_gemini(prompt, st.session_state.messages)
                source = "Gemini"

            if not response:
                response = "抱歉，我目前無法回答這個問題。請試試其他問法！"
                source = "Fallback"
            
            st.markdown(response)
            st.caption(f"Powered by {source}")
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# Chat input
if prompt := st.chat_input("問我任何旅遊理財問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("thinking..."):
            if "Rule" in mode:
                response = rule_based_response(prompt)
                source = "Rule Engine"
                if not response:
                    response = "我不太理解你的問題。試試問我：匯率、預算規劃、分帳、消費分析、異常偵測相關的問題！"
            else:
                # Try rule-based first for structured data
                response = rule_based_response(prompt)
                if response:
                    source = "Rule Engine"
                else:
                    response = call_gemini(prompt, st.session_state.messages)
                    source = "Gemini"

                if not response:
                    # Fallback to rule-based
                    response = rule_based_response(prompt)
                    source = "Fallback"

                if not response:
                    response = "抱歉，我目前無法回答這個問題。試試問我匯率、預算規劃、分帳、消費分析相關的問題！"
                    source = "Fallback"
            
            st.markdown(response)
            st.caption(f"Powered by {source}")
    
    st.session_state.messages.append({"role": "assistant", "content": response})

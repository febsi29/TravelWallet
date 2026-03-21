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

st.set_page_config(page_title="AI Assistant", page_icon="", layout="wide")

# --- Init modules ---
engine = SplitEngine(DB_PATH)
cm = CurrencyManager(DB_PATH)
planner = TripPlanner(DB_PATH)
ana = Analytics(DB_PATH)
detector = AnomalyDetector(DB_PATH)
bm = BudgetManager(DB_PATH)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDLwxs8kOD7ZL94nWNfr_baYmI-2WTVgzM")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# ============================================================
#  Rule-Based Engine (Fallback)
# ============================================================

def rule_based_response(user_input):
    """Keyword-based intent detection and response"""
    text = user_input.lower()
    
    # --- Currency / Exchange Rate ---
    currency_keywords = ["", "", "", "", "", "", "", "", "", "exchange", "rate"]
    if any(k in text for k in currency_keywords):
        # Try to find currency code
        found_code = None
        name_map = {"": "JPY", "": "JPY", "": "USD", "": "USD",
                     "": "KRW", "": "KRW", "": "THB", "": "EUR",
                     "": "GBP", "": "AUD", "": "HKD", "": "CNY",
                     "": "SGD", "": "MYR", "": "VND"}
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
                    return (f" **{info['name']}({found_code})**\n\n"
                            f"- 1 TWD = {rate:.4f} {found_code}\n"
                            f"- 1 {found_code} = NT${twd_per}\n\n"
                            f" {info['symbol']}{amt:,.0f} = **NT${converted:,.0f}**")
                
                return (f" **{info['name']}({found_code})**\n\n"
                        f"- 1 TWD = {rate:.4f} {found_code}\n"
                        f"- 1 {found_code} = NT${twd_per}\n\n"
                        f"")
            except:
                return ""
        else:
            # Show all rates
            lines = [" ****\n"]
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
    plan_keywords = ["", "", "plan", "budget", "", ""]
    dest_keywords = {k: k for k in DESTINATION_FACTORS.keys()}
    if any(k in text for k in plan_keywords):
        dest = None
        for d in DESTINATION_FACTORS.keys():
            if d in text:
                dest = d
                break
        
        days_match = re.search(r'(\d+)\s*[]', text)
        days = int(days_match.group(1)) if days_match else 5
        
        people_match = re.search(r'(\d+)\s*[]', text)
        people = int(people_match.group(1)) if people_match else 1
        
        if dest:
            plan = planner.suggest_budget(dest, days, people)
            std = plan["tiers"]["standard"]
            bud = plan["tiers"]["budget"]
            pre = plan["tiers"]["premium"]
            return (f" **{dest} {days} {people} **\n\n"
                    f"|  |  |  |\n"
                    f"|------|---------|--------|\n"
                    f"| 🟢  | NT${bud['daily_per_person']:,} | NT${bud['total_per_person']:,} |\n"
                    f"| 🟡  | NT${std['daily_per_person']:,} | NT${std['total_per_person']:,} |\n"
                    f"|   | NT${pre['daily_per_person']:,} | NT${pre['total_per_person']:,} |\n\n"
                    f" ")
        else:
            dests = "".join(list(DESTINATION_FACTORS.keys()))
            return f" {dests}\n\n54"
    
    # --- Split Bill ---
    split_keywords = ["", "", "", "", "split", "owe", "settle", ""]
    if any(k in text for k in split_keywords):
        try:
            balances = engine.get_net_balances(1)
            transfers = engine.settle_trip(1)
            
            lines = [" ****\n"]
            lines.append("****")
            for uid, info in balances.items():
                b = info["balance"]
                emoji = "" if b > 0 else ""
                label = "" if b > 0 else ""
                lines.append(f"- {info['name']}: ¥{b:,.0f} {emoji} {label}")
            
            lines.append(f"\n**{len(transfers)}**")
            for t in transfers:
                lines.append(f"-  {t['from_name']} → {t['to_name']}: ¥{t['amount']:,.0f} (NT${t['amount_twd']:,})")
            
            return "\n".join(lines)
        except:
            return ""
    
    # --- Analytics ---
    analytics_keywords = ["", "", "", "", "", "", "", ""]
    if any(k in text for k in analytics_keywords):
        try:
            pvn = ana.personal_vs_national(1)
            p = pvn["personal"]
            n = pvn["national"]
            c = pvn["comparison"]
            
            cats = ana.category_analysis(1)
            cat_lines = "\n".join([f"- {cat['category']}: NT${cat['total_twd']:,.0f} ({cat['percentage']}%)" for cat in cats[:5]])
            
            return (f" ****\n\n"
                    f"** vs **\n"
                    f"- NT${p['per_person_total']:,}\n"
                    f"- ({n['year']})NT${n['avg_total']:,.0f}\n"
                    f"- {c['diff_pct']:+.1f}%\n"
                    f"- {c['verdict']}\n\n"
                    f"****\n{cat_lines}")
        except:
            return ""
    
    # --- Anomaly ---
    anomaly_keywords = ["", "", "", "anomaly", "fraud", ""]
    if any(k in text for k in anomaly_keywords):
        try:
            summary = detector.get_anomaly_summary(1)
            if summary["anomaly_count"] > 0:
                lines = [f" ** {summary['anomaly_count']} **\n"]
                for a in summary["anomalies"]:
                    lines.append(f"- NT${a['amount_twd']:,.0f} | {a['category']} | {a['description']}")
                return "\n".join(lines)
            else:
                return " "
        except:
            return ""
    
    # --- Budget Status ---
    budget_keywords = ["", "", "", "", "burn"]
    if any(k in text for k in budget_keywords) and any(k in text for k in ["", "", "", ""]):
        try:
            health = bm.assess_health(1)
            return (f" ****\n\n"
                    f"- {health['score']}/100\n"
                    f"- {health['status']}\n"
                    f"- NT${health['total_spent']:,} ({health['usage_ratio']}%)\n"
                    f"- NT${health['budget']:,.0f}")
        except:
            return ""
    
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
- Reply in Traditional Chinese ()
- Be concise and helpful
- Use numbers and data from the context when relevant
- When asked about budget planning, provide 3 tiers (budget/standard/premium)
- For currency questions, provide the rate and conversion
- For split bill questions, explain who owes whom
- Use emoji to make responses friendly
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

st.title(" TravelWallet AI Assistant")
st.caption("Ask me anything about travel budgets, exchange rates, split bills, and spending analysis!")

# Mode indicator
col1, col2 = st.columns([3, 1])
with col2:
    mode = st.radio("Engine", [" AI (Gemini)", " Rule-based"], horizontal=True, label_visibility="collapsed")

# Quick action buttons
st.markdown("---")
qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
with qcol1:
    if st.button(" ", use_container_width=True):
        st.session_state.quick_msg = ""
with qcol2:
    if st.button(" ", use_container_width=True):
        st.session_state.quick_msg = "54"
with qcol3:
    if st.button(" ", use_container_width=True):
        st.session_state.quick_msg = ""
with qcol4:
    if st.button(" ", use_container_width=True):
        st.session_state.quick_msg = ""
with qcol5:
    if st.button(" ", use_container_width=True):
        st.session_state.quick_msg = ""

st.markdown("---")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": " TravelWallet  \n\n\n-  \n-  \n-  \n-  \n-  \n\n"}
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
                source = " Rule Engine"
            else:
                response = call_gemini(prompt, st.session_state.messages)
                source = " Gemini"
            
            if not response:
                response = ""
                source = " Fallback"
            
            st.markdown(response)
            st.caption(f"Powered by {source}")
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# Chat input
if prompt := st.chat_input("..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("thinking..."):
            if "Rule" in mode:
                response = rule_based_response(prompt)
                source = " Rule Engine"
                if not response:
                    response = ""
            else:
                # Try rule-based first for structured data
                response = rule_based_response(prompt)
                if response:
                    source = " Rule Engine"
                else:
                    response = call_gemini(prompt, st.session_state.messages)
                    source = " Gemini"
                
                if not response:
                    # Fallback to rule-based
                    response = rule_based_response(prompt)
                    source = " Fallback"
                
                if not response:
                    response = ""
                    source = ""
            
            st.markdown(response)
            st.caption(f"Powered by {source}")
    
    st.session_state.messages.append({"role": "assistant", "content": response})

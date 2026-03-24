"""
16_AIAgent.py - Anthropic Claude AI Agent 整合頁面

功能分頁：
  財務顧問 | 異常說明 | 信用卡推薦 | 預算規劃
"""
import streamlit as st
import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.ai_agent import AIAgentService, MODEL_HAIKU, MODEL_SONNET
from src.planner import DESTINATION_FACTORS

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# ============================================================
#  初始化
# ============================================================

@st.cache_resource
def get_agent():
    return AIAgentService(DB_PATH)


agent = get_agent()
user_id = st.session_state.get("user_id", 1)

# ── 頁面標題與 API 狀態列 ──────────────────────────────────
st.title("Claude AI Agent")

status_col, model_col = st.columns([3, 1])
with status_col:
    if agent.is_available:
        st.success("Claude API 已連線 — 完整 AI 功能已啟用")
    else:
        st.warning(
            "未設定 ANTHROPIC_API_KEY — 使用規則型降級模式。"
            "請在環境變數中設定金鑰以啟用完整功能。"
        )
with model_col:
    if agent.is_available:
        st.caption(
            f"一般：{MODEL_HAIKU.split('-')[1]}\n"
            f"複雜：{MODEL_SONNET.split('-')[1]}"
        )

st.markdown("---")

# ============================================================
#  四個功能分頁
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "智慧財務顧問",
    "異常交易說明",
    "信用卡推薦對話",
    "預算規劃 Agent",
])

# ────────────────────────────────────────────────────────────
#  Tab 1：智慧財務顧問
# ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("旅行財務顧問")
    st.caption("針對您的旅行消費提供個人化分析與建議")

    cfg_col, chat_col = st.columns([1, 2])

    with cfg_col:
        trip_id_adv = st.number_input("旅行 ID", min_value=1, step=1, value=1, key="adv_trip")

        if st.button("載入旅行資料", type="primary"):
            ctx = agent.advisor.build_context(int(trip_id_adv))
            st.session_state["advisor_context"] = ctx
            st.session_state["advisor_trip_id"] = int(trip_id_adv)
            st.session_state["advisor_history"] = []
            st.success("已載入")

        if "advisor_context" in st.session_state:
            with st.expander("旅行資料摘要", expanded=False):
                st.text(st.session_state["advisor_context"])

        st.markdown("**快速問題**")
        quick_qs = [
            "分析我的消費是否合理",
            "哪個類別超支最嚴重",
            "如何在剩餘天數節省開支",
            "與全國平均比較",
        ]
        for q in quick_qs:
            if st.button(q, use_container_width=True, key=f"adv_q_{q[:6]}"):
                st.session_state["advisor_quick"] = q

    with chat_col:
        history = st.session_state.get("advisor_history", [])
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # 快速問題觸發
        quick = st.session_state.pop("advisor_quick", None)
        prompt = st.chat_input("請問財務顧問...", key="advisor_input") or quick

        if prompt:
            if "advisor_trip_id" not in st.session_state:
                st.warning("請先點擊「載入旅行資料」")
            else:
                history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("分析中..."):
                        reply = agent.advisor.chat(
                            prompt,
                            st.session_state["advisor_trip_id"],
                            history[:-1],
                        )
                        st.markdown(reply)
                        src = "Claude Sonnet" if agent.is_available else "規則引擎"
                        st.caption(f"Powered by {src}")
                history.append({"role": "assistant", "content": reply})
                st.session_state["advisor_history"] = history

# ────────────────────────────────────────────────────────────
#  Tab 2：異常交易說明
# ────────────────────────────────────────────────────────────
with tab2:
    st.subheader("異常交易 AI 說明")
    st.caption("為偵測到的異常消費生成自然語言解釋")

    trip_id_anom = st.number_input("旅行 ID", min_value=1, step=1, value=1, key="anom_trip")

    if st.button("偵測並說明異常交易", type="primary"):
        with st.spinner("偵測異常中..."):
            try:
                from src.anomaly import AnomalyDetector
                detector = AnomalyDetector(DB_PATH)
                anomalies = detector.detect_all(int(trip_id_anom))
                flagged = [a for a in anomalies if a.get("is_anomaly")]

                if not flagged:
                    st.success("未偵測到異常交易，所有消費在正常範圍內")
                else:
                    st.warning(f"偵測到 {len(flagged)} 筆可能異常的交易")
                    with st.spinner(f"為 {min(len(flagged), 5)} 筆異常生成說明..."):
                        explained = agent.explainer.explain_batch(flagged, max_count=5)

                    for item in explained:
                        flags = item.get("flags", 0)
                        amount = item.get("amount_twd", 0)
                        cat = item.get("category", "--")
                        with st.expander(
                            f"NT${amount:,} | {cat} | {flags}/3 方法標記 | {item.get('txn_datetime', '')[:10]}"
                        ):
                            d_col, e_col = st.columns([1, 1])
                            with d_col:
                                st.markdown("**偵測細節**")
                                st.write(f"Z-Score：{item.get('zscore', 0):+.2f}")
                                st.write(f"IQR 異常：{'是' if item.get('is_anomaly_iqr') else '否'}")
                                st.write(f"Isolation Forest：{'是' if item.get('is_anomaly_if') else '否'}")
                                st.write(f"描述：{item.get('description', '--')}")
                            with e_col:
                                st.markdown("**AI 說明**")
                                st.info(item.get("explanation", "說明生成失敗"))

                    src = "Claude Haiku" if agent.is_available else "規則引擎"
                    st.caption(f"說明由 {src} 生成")
            except ValueError as e:
                st.error(str(e))

# ────────────────────────────────────────────────────────────
#  Tab 3：信用卡推薦對話
# ────────────────────────────────────────────────────────────
with tab3:
    st.subheader("信用卡推薦顧問")
    st.caption("透過對話了解您的消費習慣，推薦最適合的旅遊信用卡")

    reset_col, load_col = st.columns([1, 2])
    with reset_col:
        if st.button("重新開始對話", key="card_reset"):
            st.session_state["card_history"] = []
            st.rerun()
    with load_col:
        card_trip = st.number_input(
            "載入旅行消費輔助推薦（0=略過）",
            min_value=0, step=1, value=0, key="card_trip_id"
        )

    # 初始化對話
    if "card_history" not in st.session_state:
        st.session_state["card_history"] = [{
            "role": "assistant",
            "content": (
                "您好！我是信用卡推薦顧問。\n\n"
                "讓我透過幾個問題了解您的旅遊消費習慣，"
                "為您推薦最划算的信用卡。\n\n"
                "請問您最常前往哪些旅遊地區？（例如：日本、東南亞、歐美等）"
            ),
        }]

    for msg in st.session_state["card_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if card_prompt := st.chat_input("回答問題或詢問信用卡...", key="card_input"):
        st.session_state["card_history"].append({"role": "user", "content": card_prompt})
        with st.chat_message("user"):
            st.markdown(card_prompt)

        spending_profile = None
        if card_trip > 0:
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT category, SUM(amount_twd) FROM transactions "
                    "WHERE trip_id=? GROUP BY category", (int(card_trip),)
                )
                rows = cursor.fetchall()
                conn.close()
                if rows:
                    spending_profile = {r[0]: r[1] for r in rows}
            except Exception:
                pass

        with st.chat_message("assistant"):
            with st.spinner("思考推薦中..."):
                reply = agent.card_advisor.chat(
                    card_prompt,
                    st.session_state["card_history"][:-1],
                    spending_profile,
                )
                st.markdown(reply)
                src = "Claude Haiku" if agent.is_available else "規則引擎"
                st.caption(f"Powered by {src}")

        st.session_state["card_history"].append({"role": "assistant", "content": reply})

# ────────────────────────────────────────────────────────────
#  Tab 4：預算規劃 Agent
# ────────────────────────────────────────────────────────────
with tab4:
    st.subheader("AI 預算規劃")
    st.caption("輸入旅行資訊，獲取個人化預算建議")

    param_col, result_col = st.columns([1, 2])

    with param_col:
        st.markdown("**旅行設定**")
        destination = st.selectbox(
            "目的地", options=list(DESTINATION_FACTORS.keys()), index=0
        )
        days = st.slider("天數", min_value=1, max_value=30, value=5)
        num_travelers = st.slider("人數", min_value=1, max_value=10, value=2)
        travel_style = st.radio(
            "旅遊風格",
            options=["budget", "standard", "premium"],
            format_func=lambda x: {"budget": "省錢", "standard": "標準", "premium": "豪華"}[x],
            index=1,
            horizontal=True,
        )
        special_needs = st.text_input(
            "特殊需求（選填）",
            placeholder="例如：帶小孩、蜜月旅行",
        )

        if st.button("生成預算規劃", type="primary"):
            with st.spinner("規劃中..."):
                plan_result = agent.budget_planner.plan(
                    destination=destination,
                    days=days,
                    num_travelers=num_travelers,
                    travel_style=travel_style,
                    special_needs=special_needs,
                    user_id=user_id,
                )
                st.session_state["budget_plan"] = plan_result
                st.success("規劃完成")

    with result_col:
        if "budget_plan" in st.session_state:
            plan = st.session_state["budget_plan"]
            base = plan["base_plan"]
            tiers = base.get("tiers", {})

            # 三檔預算卡片
            b_col, s_col, p_col = st.columns(3)
            for col, (key, label) in zip(
                [b_col, s_col, p_col],
                [("budget", "省錢"), ("standard", "標準"), ("premium", "豪華")],
            ):
                t = tiers.get(key, {})
                with col:
                    st.metric(
                        label=label,
                        value=f"NT${t.get('total_per_person', 0):,}",
                        delta=f"每日 NT${t.get('daily_per_person', 0):,}",
                    )

            # 標準版類別分配
            std_breakdown = tiers.get("standard", {}).get("breakdown", {})
            if std_breakdown:
                st.markdown("**標準版類別分配（每人）**")
                bd_df = pd.DataFrame([
                    {"類別": k, "金額": f"NT${v:,}"}
                    for k, v in std_breakdown.items()
                ])
                st.dataframe(bd_df, use_container_width=True, hide_index=True)

            # AI 個人化分析
            if plan.get("ai_analysis"):
                st.markdown("---")
                st.markdown("**AI 個人化建議**")
                st.markdown(plan["ai_analysis"])
                st.caption(f"Powered by {plan['source']}")

    # 互動對話調整
    st.markdown("---")
    st.markdown("**對話調整預算**")

    if "budget_chat_history" not in st.session_state:
        st.session_state["budget_chat_history"] = []

    for msg in st.session_state["budget_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if budget_prompt := st.chat_input("詢問或調整預算...", key="budget_input"):
        st.session_state["budget_chat_history"].append(
            {"role": "user", "content": budget_prompt}
        )
        with st.chat_message("user"):
            st.markdown(budget_prompt)

        current_params = {
            "destination": destination,
            "days": days,
            "num_travelers": num_travelers,
            "travel_style": travel_style,
        }
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                reply, _ = agent.budget_planner.interactive_plan(
                    budget_prompt,
                    st.session_state["budget_chat_history"][:-1],
                    current_params,
                )
                st.markdown(reply)
                src = "Claude Haiku" if agent.is_available else "規則引擎"
                st.caption(f"Powered by {src}")

        st.session_state["budget_chat_history"].append(
            {"role": "assistant", "content": reply}
        )

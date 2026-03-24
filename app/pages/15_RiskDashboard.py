"""
15_RiskDashboard.py - 風險評估儀表板頁面
"""
import streamlit as st
import os, sys, pandas as pd
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.risk_dashboard import RiskDashboard

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("風險評估儀表板")
st.caption("綜合匯率、預算、異常交易、信用四維度評估旅行財務健康度")

user_id = st.session_state.get("user_id", 1)
rd = RiskDashboard(DB_PATH)

col_trip, col_btn = st.columns([2, 1])
with col_trip:
    trip_id = st.number_input("旅行 ID", min_value=1, step=1, value=1)
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    assess_btn = st.button("執行評估", type="primary", use_container_width=True)

if assess_btn:
    try:
        result = rd.assess_overall(user_id=user_id, trip_id=int(trip_id))
        st.session_state["risk_result"] = result
    except ValueError as e:
        st.error(str(e))

if "risk_result" in st.session_state:
    r = st.session_state["risk_result"]

    # 健康指數 + 整體風險
    health = r["health_index"]
    overall = r["overall_risk"]
    color_map = {"A": "#10B981", "B": "#3B82F6", "C": "#F59E0B", "D": "#F97316", "F": "#EF4444"}
    health_color = color_map.get(health, "#6B7280")

    st.markdown(
        f"<h2 style='text-align:center; color:{health_color}'>財務健康指數：{health}</h2>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("整體風險", f"{overall:.1f}")
    c2.metric("匯率風險", f"{r['fx']['risk_score']:.1f}", delta=r['fx'].get('level'))
    c3.metric("預算風險", f"{r['budget']['risk_score']:.1f}", delta=r['budget'].get('level'))
    c4.metric("異常風險", f"{r['anomaly']['risk_score']:.1f}")
    c5.metric("信用風險", f"{r['credit']['risk_score']:.1f}")

    # 雷達圖
    categories = ["匯率風險", "預算風險", "異常風險", "信用風險"]
    values = [
        r["fx"]["risk_score"],
        r["budget"]["risk_score"],
        r["anomaly"]["risk_score"],
        r["credit"]["risk_score"],
    ]
    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        line_color="#2563EB",
        fillcolor="rgba(37, 99, 235, 0.2)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="四維度風險雷達圖",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    # 各維度詳情
    st.subheader("各維度詳情")
    tabs = st.tabs(["匯率", "預算", "異常交易", "信用"])

    with tabs[0]:
        fx = r["fx"]
        st.metric("風險評分", f"{fx['risk_score']:.1f}/100")
        st.write(f"**風險等級：** {fx.get('level', '--')}")
        st.write(f"**說明：** {fx.get('message', '--')}")

    with tabs[1]:
        budget = r["budget"]
        st.metric("風險評分", f"{budget['risk_score']:.1f}/100")
        st.write(f"**說明：** {budget.get('message', '--')}")

    with tabs[2]:
        anomaly = r["anomaly"]
        st.metric("風險評分", f"{anomaly['risk_score']:.1f}/100")
        st.write(f"**異常交易率：** {anomaly.get('anomaly_rate', 0)*100:.1f}%")
        st.write(f"**說明：** {anomaly.get('message', '--')}")

    with tabs[3]:
        credit = r["credit"]
        st.metric("風險評分", f"{credit['risk_score']:.1f}/100")
        st.write(f"**信用評分：** {credit.get('credit_score', '--')}")
        st.write(f"**說明：** {credit.get('message', '--')}")

    # 改善建議
    st.subheader("改善建議")
    recs = r.get("recommendations", [])
    if recs:
        for rec in recs:
            st.info(rec)
    else:
        st.success("財務狀況良好，繼續保持！")

# 歷史評估紀錄
st.markdown("---")
st.subheader("歷史評估紀錄")
try:
    history = rd.get_risk_history(user_id=user_id, limit=10)
    if history:
        rows = []
        for h in history:
            rows.append({
                "評估時間": h.get("assessed_at", "")[:16],
                "旅行 ID": h["trip_id"],
                "健康指數": h["health_index"],
                "整體風險": f"{h['overall_risk']:.1f}",
                "匯率": f"{h['fx_risk']:.1f}",
                "預算": f"{h['budget_risk']:.1f}",
                "異常": f"{h['anomaly_risk']:.1f}",
                "信用": f"{h['credit_risk']:.1f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("尚無評估紀錄，請先執行評估")
except ValueError as e:
    st.error(str(e))

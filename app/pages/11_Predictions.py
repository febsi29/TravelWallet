"""
11_Predictions.py - 支出預測與智慧提醒頁面
"""
import streamlit as st
import os, sys, pandas as pd
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.prediction import SpendingPredictor

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("支出預測與智慧提醒")

user_id = st.session_state.get("user_id", 1)
trip_id = st.number_input("旅行 ID", min_value=1, step=1, value=1)

predictor = SpendingPredictor(DB_PATH)

col1, col2 = st.columns(2)

# 預算超支預測
with col1:
    st.subheader("預算超支預測")
    try:
        exceed = predictor.predict_budget_exceed_day(trip_id)
        if exceed.get("will_exceed"):
            st.error(f"預計第 {exceed['exceed_day']} 天超支")
            st.metric("剩餘天數", f"{exceed.get('days_remaining', '--')} 天")
            st.metric("每日燒錢率", f"NT${exceed.get('daily_burn_rate', 0):,.0f}")
        else:
            st.success("預算充足，無超支風險")
        if exceed.get("message"):
            st.caption(exceed["message"])
    except ValueError as e:
        st.warning(str(e))

# 每日消費預測
with col2:
    st.subheader("每日消費預測（指數平滑）")
    try:
        pred = predictor.predict_daily_spending(trip_id)
        st.metric("明日預測支出", f"NT${pred['predicted_tomorrow']:,.0f}")
        st.metric("7 日平均", f"NT${pred.get('avg_7d', 0):,.0f}")
        if pred.get("trend") == "up":
            st.warning("消費有上升趨勢")
        elif pred.get("trend") == "down":
            st.info("消費呈現下降趨勢")
        else:
            st.success("消費趨勢穩定")
    except ValueError as e:
        st.warning(str(e))

# 預測走勢圖
st.markdown("---")
st.subheader("消費走勢圖")
try:
    pred_detail = predictor.predict_daily_spending(trip_id)
    history = pred_detail.get("history", [])
    smoothed = pred_detail.get("smoothed", [])
    if history:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=history, name="實際支出", mode="lines+markers",
            line=dict(color="#3B82F6")
        ))
        if smoothed:
            fig.add_trace(go.Scatter(
                y=smoothed, name="預測（平滑）", mode="lines",
                line=dict(color="#F59E0B", dash="dash")
            ))
        fig.update_layout(
            title="每日消費走勢",
            xaxis_title="天數",
            yaxis_title="支出（TWD）",
            template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("資料不足，無法繪製圖表")
except ValueError:
    pass

# 智慧提醒
st.markdown("---")
st.subheader("智慧提醒")

col_gen, col_filter = st.columns([1, 1])
with col_gen:
    if st.button("重新產生提醒", type="primary"):
        try:
            alerts = predictor.generate_all_alerts(trip_id, user_id)
            st.success(f"已產生 {len(alerts)} 則提醒")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
with col_filter:
    show_unread = st.checkbox("只顯示未讀", value=False)

try:
    alerts = predictor.get_alerts(trip_id, user_id, unread_only=show_unread)
except ValueError as e:
    st.error(str(e))
    alerts = []

if alerts:
    for a in alerts:
        severity = a.get("severity", "info")
        icon_map = {"warning": st.warning, "error": st.error, "info": st.info}
        render_fn = icon_map.get(severity, st.info)
        msg = f"**{a['title']}** — {a['message']}"
        if not a.get("is_read"):
            msg += "  （未讀）"
        render_fn(msg)

        if not a.get("is_read"):
            if st.button(f"標為已讀 #{a['alert_id']}", key=f"read_{a['alert_id']}"):
                predictor.mark_read(a["alert_id"])
                st.rerun()
else:
    st.caption("目前沒有提醒")

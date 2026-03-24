"""
12_Community.py - 社群排行榜頁面
"""
import streamlit as st
import os, sys, pandas as pd
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.community import CommunityService

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("社群排行榜")
st.caption("分享旅行消費資料，與社群比較並找到最省錢的旅行方式")

user_id = st.session_state.get("user_id", 1)
svc = CommunityService(DB_PATH)

# 分享旅行資料
with st.expander("分享我的旅行資料", expanded=False):
    share_trip_id = st.number_input("旅行 ID", min_value=1, step=1, value=1, key="share_trip")
    if st.button("匿名分享", type="primary"):
        try:
            result = svc.share_trip_data(user_id=user_id, trip_id=share_trip_id)
            st.success(
                f"已分享！目的地：{result['destination']}，"
                f"每人每日：NT${result['per_person_daily']:,.0f}"
            )
        except ValueError as e:
            st.error(str(e))

st.markdown("---")

# 排行榜
tab1, tab2 = st.tabs(["省錢排行", "豪爽排行"])

with tab1:
    st.subheader("最省錢旅行者 Top 10")
    try:
        frugal = svc.get_leaderboard(metric="frugal", limit=10)
        if frugal:
            df = pd.DataFrame([{
                "排名": i + 1,
                "目的地": r["destination"],
                "天數": r["trip_days"],
                "人數": r["num_travelers"],
                "每人每日（TWD）": f"NT${r['per_person_daily']:,.0f}",
            } for i, r in enumerate(frugal)])
            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = px.bar(
                [{"目的地": r["destination"], "每人每日": r["per_person_daily"]} for r in frugal],
                x="目的地", y="每人每日",
                title="省錢榜 — 每人每日消費（TWD）",
                color="每人每日",
                color_continuous_scale="Blues",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("尚無資料，請先分享旅行資料")
    except ValueError as e:
        st.error(str(e))

with tab2:
    st.subheader("最豪爽旅行者 Top 10")
    try:
        spenders = svc.get_leaderboard(metric="spender", limit=10)
        if spenders:
            df = pd.DataFrame([{
                "排名": i + 1,
                "目的地": r["destination"],
                "天數": r["trip_days"],
                "人數": r["num_travelers"],
                "每人每日（TWD）": f"NT${r['per_person_daily']:,.0f}",
            } for i, r in enumerate(spenders)])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("尚無資料")
    except ValueError as e:
        st.error(str(e))

# 目的地統計
st.markdown("---")
st.subheader("目的地查詢")

dest_input = st.text_input("輸入目的地（如：日本、韓國）", value="日本")
if st.button("查詢") and dest_input:
    try:
        stats = svc.get_destination_stats(dest_input)
        col1, col2, col3 = st.columns(3)
        col1.metric("旅行筆數", stats["count"])
        col2.metric("平均每人每日", f"NT${stats['avg_daily']:,.0f}")
        col3.metric("最低每人每日", f"NT${stats.get('min_daily', 0):,.0f}")
    except ValueError as e:
        st.error(str(e))

# 我的排名
st.markdown("---")
st.subheader("我的排名")
rank_trip = st.number_input("旅行 ID", min_value=1, step=1, value=1, key="rank_trip")
if st.button("查詢排名"):
    try:
        rank = svc.get_my_ranking(user_id=user_id, trip_id=rank_trip)
        if rank["rank"] is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric("排名", f"#{rank['rank']}")
            col2.metric("前百分比", f"{rank['percentile']:.1f}%")
            col3.metric("每人每日", f"NT${rank['per_person_daily']:,.0f}")
        else:
            st.info("尚未分享此旅行資料，請先分享以獲得排名")
    except ValueError as e:
        st.error(str(e))

# 目的地比較
st.markdown("---")
st.subheader("目的地消費比較")
dest_list_input = st.text_input("輸入多個目的地（逗號分隔）", value="日本,韓國,泰國")
if st.button("比較目的地"):
    dests = [d.strip() for d in dest_list_input.split(",") if d.strip()]
    if dests:
        try:
            comparison = svc.get_destination_comparison(dests)
            df = pd.DataFrame([{
                "目的地": c["destination"],
                "旅行筆數": c["count"],
                "平均每人每日（TWD）": f"NT${c['avg_daily']:,.0f}",
            } for c in comparison])
            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = px.bar(
                [{"目的地": c["destination"], "平均每人每日": c["avg_daily"]} for c in comparison if c["avg_daily"] > 0],
                x="目的地", y="平均每人每日",
                title="各目的地平均每人每日消費比較",
                color_discrete_sequence=["#2563EB"],
            )
            st.plotly_chart(fig, use_container_width=True)
        except ValueError as e:
            st.error(str(e))

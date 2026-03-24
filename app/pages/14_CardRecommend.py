"""
14_CardRecommend.py - 信用卡推薦頁面
"""
import streamlit as st
import os, sys, pandas as pd
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.card_recommend import CardRecommendService, seed_cards

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("信用卡推薦")
st.caption("根據你的消費模式，推薦最高回饋的旅遊信用卡")

svc = CardRecommendService(DB_PATH)

# 確保種子資料存在
seed_cards(DB_PATH)

# 依旅行推薦
st.subheader("依旅行推薦最佳卡片")
trip_id = st.number_input("旅行 ID", min_value=1, step=1, value=1)

if st.button("分析並推薦", type="primary"):
    try:
        results = svc.recommend_by_trip(trip_id=int(trip_id))
        if results:
            st.session_state["trip_recommend"] = results
            st.success(f"找到 {len(results)} 張候選卡片")
        else:
            st.warning("此旅行尚無消費紀錄，無法推薦")
    except ValueError as e:
        st.error(str(e))

if "trip_recommend" in st.session_state:
    results = st.session_state["trip_recommend"]
    best = results[0]
    st.info(f"推薦首選：**{best['card_name']}**（{best['issuer']}）— 預估淨回饋 NT${best['net_benefit']:,.0f}")

    df = pd.DataFrame([{
        "卡片名稱": r["card_name"],
        "發卡行": r["issuer"],
        "預估回饋": f"NT${r['total_reward']:,.0f}",
        "海外手續費": f"NT${r['total_fee']:,.0f}",
        "淨回饋": f"NT${r['net_benefit']:,.0f}",
        "最佳類別": r.get("top_category") or "--",
    } for r in results])
    st.dataframe(df, use_container_width=True, hide_index=True)

    fig = px.bar(
        [{"卡片": r["card_name"], "淨回饋": r["net_benefit"]} for r in results],
        x="卡片", y="淨回饋",
        title="各卡片預估淨回饋比較（TWD）",
        color="淨回饋",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 依類別推薦
st.subheader("依消費類別推薦")
col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox("消費類別", ["餐飲", "住宿", "交通", "購物", "娛樂", "其他"])
with col2:
    amount = st.number_input("消費金額（TWD）", min_value=1, value=5000, step=500)
with col3:
    region = st.text_input("消費地區（空白=台灣境內）", value="日本")

if st.button("查詢最佳卡片"):
    try:
        results = svc.recommend_by_category(
            category=category,
            amount=float(amount),
            region=region.strip() or "all",
        )
        if results:
            df = pd.DataFrame([{
                "卡片名稱": r["card_name"],
                "回饋金額": f"NT${r['reward_amount']:,.1f}",
                "手續費": f"NT${r['fee_amount']:,.1f}",
                "淨回饋": f"NT${r['net_benefit']:,.1f}",
                "回饋率": f"{r['reward_rate']:.1f}%",
                "回饋類型": r["reward_type"],
            } for r in results])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("目前無卡片資料，已自動初始化")
    except ValueError as e:
        st.error(str(e))

st.markdown("---")

# 所有卡片
st.subheader("信用卡資料庫")
cards = svc.get_all_cards()
if cards:
    with st.expander("檢視所有卡片", expanded=False):
        for card in cards:
            st.markdown(f"**{card['card_name']}**（{card['issuer']}）"
                        f" — 年費 NT${card['annual_fee']:,.0f}"
                        f" ｜ 海外手續費 {card['overseas_fee_pct']:.1f}%")
            if card["rewards"]:
                reward_rows = [{
                    "類別": r["category"],
                    "地區": r["region"],
                    "類型": r["reward_type"],
                    "回饋率": f"{r['reward_rate']:.1f}%",
                    "上限": r.get("reward_cap") or "無",
                } for r in card["rewards"]]
                st.dataframe(pd.DataFrame(reward_rows), use_container_width=True, hide_index=True)
            st.markdown("---")

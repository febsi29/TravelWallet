import streamlit as st
import os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
from src.planner import TripPlanner, DESTINATION_FACTORS, CATEGORY_RATIOS

st.title("行程規劃")
st.caption("依據政府統計資料的預算建議")
planner = TripPlanner()

st.markdown("---")
c1,c2,c3 = st.columns(3)
with c1:
    destination = st.selectbox("目的地", list(DESTINATION_FACTORS.keys()), index=0)
with c2:
    days = st.slider("天數", 1, 30, 5)
with c3:
    travelers = st.slider("人數", 1, 10, 4)

if st.button("產生預算建議", type="primary", use_container_width=True):
    plan = planner.suggest_budget(destination, days, travelers)
    st.markdown("---")
    st.subheader(f"{destination} {days} 天 {travelers} 人預算")
    st.caption(f"資料來源：{plan['data_source']}")
    st.caption(f"全國日均 NT${plan['avg_daily_base']:,}/人 x {plan['destination_factor']}x")

    tier_cols = st.columns(3)
    for i, key in enumerate(["budget","standard","premium"]):
        tier = plan["tiers"][key]
        with tier_cols[i]:
            st.markdown(f"#### {tier['label']}")
            st.caption(tier["description"])
            st.metric("每人總計", f"NT${tier['total_per_person']:,}")
            st.metric("每人每日", f"NT${tier['daily_per_person']:,}")
            if travelers > 1:
                st.metric(f"{travelers} 人總計", f"NT${tier['total_group']:,}")
            st.markdown("**費用明細：**")
            for cat, amt in tier["breakdown"].items():
                pct = CATEGORY_RATIOS[cat]*100
                st.markdown(f"- {cat}：NT${amt:,}（{pct:.0f}%）")

    st.markdown("---")
    st.subheader("目的地比較")
    comparisons = planner.compare_destinations(days=days, num_travelers=1)
    import plotly.express as px
    comp_df = pd.DataFrame(comparisons)
    fig = px.bar(comp_df, x="destination", y="total_per_person",
        color="total_per_person", color_continuous_scale=["#BFDBFE","#1D4ED8"],
        text="total_per_person")
    fig.update_traces(texttemplate="NT$%{text:,.0f}", textposition="outside")
    fig.update_layout(xaxis_title="目的地", yaxis_title="預算 (NT$)",
        coloraxis_showscale=False, margin=dict(t=40,b=40), height=400)
    st.plotly_chart(fig, use_container_width=True)

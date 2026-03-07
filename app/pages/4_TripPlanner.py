import streamlit as st
import os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
from src.planner import TripPlanner, DESTINATION_FACTORS, CATEGORY_RATIOS

st.set_page_config(page_title="Trip Planner", page_icon="TP", layout="wide")
st.title("Trip Planner")
st.caption("Budget suggestions based on government statistics")
planner = TripPlanner()

st.markdown("---")
c1,c2,c3 = st.columns(3)
with c1:
    destination = st.selectbox("Destination", list(DESTINATION_FACTORS.keys()), index=0)
with c2:
    days = st.slider("Days", 1, 30, 5)
with c3:
    travelers = st.slider("Travelers", 1, 10, 4)

if st.button("Generate Budget Suggestion", type="primary", use_container_width=True):
    plan = planner.suggest_budget(destination, days, travelers)
    st.markdown("---")
    st.subheader(f"{destination} {days}D {travelers}P Budget")
    st.caption(f"Source: {plan['data_source']}")
    st.caption(f"National avg daily NT${plan['avg_daily_base']:,}/person x {plan['destination_factor']}x")

    tier_cols = st.columns(3)
    for i, key in enumerate(["budget","standard","premium"]):
        tier = plan["tiers"][key]
        with tier_cols[i]:
            st.markdown(f"#### {tier['label']}")
            st.caption(tier["description"])
            st.metric("Per Person Total", f"NT${tier['total_per_person']:,}")
            st.metric("Per Person Daily", f"NT${tier['daily_per_person']:,}")
            if travelers > 1:
                st.metric(f"{travelers}P Total", f"NT${tier['total_group']:,}")
            st.markdown("**Breakdown:**")
            for cat, amt in tier["breakdown"].items():
                pct = CATEGORY_RATIOS[cat]*100
                st.markdown(f"- {cat}: NT${amt:,} ({pct:.0f}%)")

    st.markdown("---")
    st.subheader("Destination Comparison")
    comparisons = planner.compare_destinations(days=days, num_travelers=1)
    import plotly.express as px
    comp_df = pd.DataFrame(comparisons)
    fig = px.bar(comp_df, x="destination", y="total_per_person",
        color="total_per_person", color_continuous_scale=["#B7E4C7","#2D6A4F"],
        text="total_per_person")
    fig.update_traces(texttemplate="NT$%{text:,.0f}", textposition="outside")
    fig.update_layout(xaxis_title="Destination", yaxis_title="Budget (NT$)",
        coloraxis_showscale=False, margin=dict(t=40,b=40), height=400)
    st.plotly_chart(fig, use_container_width=True)

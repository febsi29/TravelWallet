import streamlit as st
import sqlite3, os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
from src.analytics import Analytics

st.set_page_config(page_title="Analytics", page_icon="AN", layout="wide")
st.title("Analytics")
ana = Analytics(DB_PATH)
conn = sqlite3.connect(DB_PATH)
trips = pd.read_sql_query("SELECT trip_id, trip_name FROM trips", conn)
conn.close()
if trips.empty:
    st.warning("No trips"); st.stop()

selected = st.selectbox("Select trip", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"]==selected]["trip_id"].values[0])

tab1,tab2,tab3,tab4 = st.tabs(["Personal vs National","Category","Daily Trend","Split Behavior"])

with tab1:
    pvn = ana.personal_vs_national(trip_id)
    p,n,c = pvn["personal"],pvn["national"],pvn["comparison"]
    c1,c2,c3 = st.columns(3)
    c1.metric("Your Per Person", f"NT${p['per_person_total']:,}")
    c2.metric(f"National Avg ({n['year']})", f"NT${n['avg_total']:,.0f}")
    c3.metric("Difference", f"{c['diff_pct']:+.1f}%", delta=f"NT${c['diff_total']:+,.0f}")
    st.info(c["verdict"])
    import plotly.graph_objects as go
    fig = go.Figure(data=[
        go.Bar(name="Your Trip", x=["Total","Daily"], y=[p["per_person_total"],p["per_person_daily"]], marker_color="#2D6A4F"),
        go.Bar(name="National", x=["Total","Daily"], y=[n["avg_total"],n["avg_daily"]], marker_color="#95D5B2"),
    ])
    fig.update_layout(barmode="group", height=350)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    cat_comp = ana.category_vs_national(trip_id)
    cats = [c["category"] for c in cat_comp]
    pers = [c["personal_pct"] for c in cat_comp]
    natl = [c["national_pct"] for c in cat_comp]
    import plotly.graph_objects as go
    fig = go.Figure(data=[
        go.Bar(name="Personal", x=cats, y=pers, marker_color="#2D6A4F"),
        go.Bar(name="National", x=cats, y=natl, marker_color="#95D5B2"),
    ])
    fig.update_layout(barmode="group", yaxis_title="Percentage (%)", height=400)
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    daily = ana.daily_spending(trip_id)
    if daily:
        import plotly.graph_objects as go
        dlbl = [f"Day {d['day']}" for d in daily]
        damt = [d["daily_twd"] for d in daily]
        camt = [d["cumulative_twd"] for d in daily]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Daily", x=dlbl, y=damt, marker_color="#40916C",
            text=[f"NT${a:,.0f}" for a in damt], textposition="outside"))
        fig.add_trace(go.Scatter(name="Cumulative", x=dlbl, y=camt,
            mode="lines+markers", line=dict(color="#E63946",width=2), yaxis="y2"))
        fig.update_layout(yaxis=dict(title="Daily (NT$)"),
            yaxis2=dict(title="Cumulative (NT$)", overlaying="y", side="right"), height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    split = ana.split_behavior(trip_id)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Payer Ranking**")
        for p in split["payer_ranking"]:
            st.markdown(f"- {p['name']}: NT${p['total_twd']:,.0f} ({p['times']}x)")
    with c2:
        st.markdown("**Actual Share**")
        for s in split["share_ranking"]:
            st.markdown(f"- {s['name']}: NT${s['total_twd']:,.0f}")

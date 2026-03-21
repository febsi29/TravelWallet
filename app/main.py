"""
TravelWallet - Main Streamlit App
"""
import streamlit as st
import sqlite3
import os
import sys

# Add project root to path so we can import src modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.set_page_config(
    page_title="TravelWallet",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1B4332;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #52796F;
        margin-top: -10px;
        margin-bottom: 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #D8F3DC 0%, #B7E4C7 100%);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #95D5B2;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1B4332;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #52796F;
        margin-top: 4px;
    }
    .stMetric > div {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border-radius: 10px;
        padding: 12px;
        border: 1px solid #bbf7d0;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown('<p class="main-header"> TravelWallet</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header"> — Smart Travel Wallet for Taiwanese Travelers</p>', unsafe_allow_html=True)

# --- Load Data ---
@st.cache_data
def load_trip_list():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT trip_id, trip_name, destination, start_date, end_date, status FROM trips ORDER BY start_date DESC")
    trips = cursor.fetchall()
    conn.close()
    return trips

@st.cache_data
def load_dashboard_data(trip_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Trip info
    cursor.execute("""
        SELECT trip_name, destination, currency_code, start_date, end_date, total_budget,
               julianday(end_date) - julianday(start_date) + 1
        FROM trips WHERE trip_id = ?
    """, (trip_id,))
    trip = cursor.fetchone()

    # Member count
    cursor.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,))
    members = cursor.fetchone()[0]

    # Transaction stats
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount_twd), 0), COALESCE(SUM(amount), 0)
        FROM transactions WHERE trip_id = ?
    """, (trip_id,))
    txn_count, total_twd, total_original = cursor.fetchone()

    # Pending settlements
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount_twd), 0)
        FROM settlements WHERE trip_id = ? AND status = 'pending'
    """, (trip_id,))
    pending_count, pending_twd = cursor.fetchone()

    # Category breakdown
    cursor.execute("""
        SELECT category, SUM(amount_twd) FROM transactions
        WHERE trip_id = ? GROUP BY category ORDER BY SUM(amount_twd) DESC
    """, (trip_id,))
    categories = cursor.fetchall()

    # Daily spending
    cursor.execute("""
        SELECT DATE(txn_datetime), SUM(amount_twd) FROM transactions
        WHERE trip_id = ? GROUP BY DATE(txn_datetime) ORDER BY DATE(txn_datetime)
    """, (trip_id,))
    daily = cursor.fetchall()

    # Recent transactions
    cursor.execute("""
        SELECT t.txn_datetime, t.amount, t.currency_code, t.amount_twd,
               t.category, t.description, u.display_name, t.is_anomaly
        FROM transactions t
        JOIN users u ON t.paid_by = u.user_id
        WHERE t.trip_id = ?
        ORDER BY t.txn_datetime DESC LIMIT 10
    """, (trip_id,))
    recent = cursor.fetchall()

    conn.close()

    return {
        "trip": trip, "members": members,
        "txn_count": txn_count, "total_twd": total_twd, "total_original": total_original,
        "pending_count": pending_count, "pending_twd": pending_twd,
        "categories": categories, "daily": daily, "recent": recent,
    }

# --- Sidebar ---
trips = load_trip_list()

if not trips:
    st.warning(" seed_data.py ")
    st.stop()

st.sidebar.markdown("###  ")
trip_options = {f"{t[1]} ({t[3][:7]})": t[0] for t in trips}
selected_trip_label = st.sidebar.selectbox("", list(trip_options.keys()), label_visibility="collapsed")
selected_trip_id = trip_options[selected_trip_label]

st.sidebar.markdown("---")
st.sidebar.markdown("###  ")
st.sidebar.markdown("""
-  Dashboard ()
-  [Transactions](./2_Transactions)
-  [Split Bill](./3_SplitBill)
-  [Trip Planner](./4_TripPlanner)
-  [Exchange](./5_Exchange)
-  [Analytics](./6_Analytics)
-  [Alerts](./7_Alerts)
""")

# --- Dashboard Content ---
data = load_dashboard_data(selected_trip_id)
trip = data["trip"]
# trip: (name, destination, currency, start, end, budget, days)

st.markdown("---")

# Top metrics
col1, col2, col3, col4 = st.columns(4)
per_person = round(data["total_twd"] / data["members"]) if data["members"] > 0 else 0
budget = trip[5] if trip[5] else 0
remaining = budget - per_person

with col1:
    st.metric(" ", f"NT${data['total_twd']:,.0f}", help="")
with col2:
    st.metric(" ", f"NT${per_person:,}", help=" / ")
with col3:
    delta_color = "normal" if remaining >= 0 else "inverse"
    st.metric(" ", f"NT${remaining:,.0f}", delta=f" NT${budget:,.0f}", delta_color=delta_color)
with col4:
    st.metric(" ", f"{data['pending_count']} ", delta=f"NT${data['pending_twd']:,.0f}")

# Trip info bar
st.markdown("---")
info_cols = st.columns(5)
info_cols[0].markdown(f"** :** {trip[1]}")
info_cols[1].markdown(f"** :** {trip[2]}")
info_cols[2].markdown(f"** :** {trip[3]} ~ {trip[4]}")
info_cols[3].markdown(f"** :** {data['members']} ")
info_cols[4].markdown(f"** :** {data['txn_count']} ")

st.markdown("---")

# Charts row
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("####  ")
    if data["categories"]:
        import plotly.express as px
        cat_names = [c[0] for c in data["categories"]]
        cat_values = [c[1] for c in data["categories"]]
        colors = ["#2D6A4F", "#40916C", "#52B788", "#74C69D", "#95D5B2", "#B7E4C7"]
        fig = px.pie(
            names=cat_names, values=cat_values,
            color_discrete_sequence=colors,
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="label+percent")
        fig.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.markdown("####  ")
    if data["daily"]:
        import plotly.graph_objects as go
        days = [f"Day {i+1}" for i in range(len(data["daily"]))]
        amounts = [d[1] for d in data["daily"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=days, y=amounts,
            marker_color="#40916C",
            text=[f"NT${a:,.0f}" for a in amounts],
            textposition="outside",
        ))
        if budget > 0 and data["members"] > 0:
            daily_budget = budget / int(trip[6])
            fig.add_hline(
                y=daily_budget, line_dash="dash", line_color="#E63946",
                annotation_text=f" NT${daily_budget:,.0f}",
            )
        fig.update_layout(
            yaxis_title=" (NT$)",
            margin=dict(t=20, b=40, l=40, r=20),
            height=350,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

# Recent transactions
st.markdown("---")
st.markdown("####  ")

if data["recent"]:
    import pandas as pd
    df = pd.DataFrame(data["recent"], columns=[
        "", "()", "", "(TWD)", "", "", "", ""
    ])
    df[""] = df[""].str[:16]
    df["()"] = df["()"].apply(lambda x: f"{x:,.0f}")
    df["(TWD)"] = df["(TWD)"].apply(lambda x: f"NT${x:,.0f}")
    df[""] = df[""].apply(lambda x: "" if x else "")
    st.dataframe(df, use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.caption("TravelWallet v1.0 | Data Source:  | Built with Streamlit")

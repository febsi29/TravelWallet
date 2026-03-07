import streamlit as st
import sqlite3, os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
from src.split import SplitEngine

st.set_page_config(page_title="Split Bill", page_icon="SB", layout="wide")
st.title("Split Bill Center")
engine = SplitEngine(DB_PATH)
conn = sqlite3.connect(DB_PATH)
trips = pd.read_sql_query("SELECT trip_id, trip_name FROM trips", conn)
if trips.empty:
    st.warning("No trips"); conn.close(); st.stop()
selected = st.selectbox("Select trip", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"]==selected]["trip_id"].values[0])

st.markdown("---")
st.subheader("Net Balances")
balances = engine.get_net_balances(trip_id)
cols = st.columns(len(balances))
for i,(uid,info) in enumerate(balances.items()):
    with cols[i]:
        b = info["balance"]
        lbl = "owed" if b>0 else ("owes" if b<0 else "settled")
        st.metric(info["name"], f"Y{b:,.0f}", delta=lbl)

st.markdown("---")
st.subheader("Settlement Plan")
transfers = engine.settle_trip(trip_id)
if transfers:
    for t in transfers:
        st.info(f"{t['from_name']} pays {t['to_name']}: Y{t['amount']:,.0f} (NT${t['amount_twd']:,})")
    st.success(f"Only {len(transfers)} transfers needed!")
else:
    st.success("All settled!")

st.markdown("---")
st.subheader("Trip Summary")
summary = engine.get_trip_summary(trip_id)
c1,c2 = st.columns(2)
with c1:
    st.markdown("**Payer Ranking**")
    for p in summary["payers"]:
        pct = p["amount"]/summary["total_amount"]*100 if summary["total_amount"]>0 else 0
        st.markdown(f"{p['name']}: Y{p['amount']:,.0f} ({p['count']}x)")
        st.progress(pct/100)
with c2:
    st.markdown("**Categories**")
    for c in summary["categories"]:
        pct = c["amount"]/summary["total_amount"]*100 if summary["total_amount"]>0 else 0
        st.markdown(f"{c['category']}: Y{c['amount']:,.0f} ({pct:.0f}%)")
        st.progress(pct/100)
conn.close()

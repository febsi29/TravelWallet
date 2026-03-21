"""Transactions Page"""
import streamlit as st
import sqlite3
import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.set_page_config(page_title="Transactions", page_icon="", layout="wide")
st.title(" ")

conn = sqlite3.connect(DB_PATH)
trips = pd.read_sql_query("SELECT trip_id, trip_name FROM trips", conn)
if trips.empty:
    st.warning("")
    st.stop()

selected = st.selectbox("", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"] == selected]["trip_id"].values[0])

st.markdown("---")
col1, col2, col3 = st.columns(3)

categories = pd.read_sql_query(
    "SELECT DISTINCT category FROM transactions WHERE trip_id = ?",
    conn, params=(trip_id,)
)["category"].tolist()

with col1:
    cat_filter = st.multiselect("", categories, default=categories)
with col2:
    sort_by = st.selectbox("", ["()", "()", "()", "()"])
with col3:
    search = st.text_input("", "")

sort_map = {
    "()": "t.txn_datetime DESC",
    "()": "t.txn_datetime ASC",
    "()": "t.amount_twd DESC",
    "()": "t.amount_twd ASC",
}
order = sort_map[sort_by]
placeholders = ",".join(["?" for _ in cat_filter])
query = f"""
    SELECT t.txn_datetime, u.display_name, t.amount, t.currency_code,
           t.amount_twd, t.category, t.description, t.location,
           t.payment_method, t.split_type, t.is_anomaly
    FROM transactions t
    JOIN users u ON t.paid_by = u.user_id
    WHERE t.trip_id = ? AND t.category IN ({placeholders})
"""
params = [trip_id] + cat_filter
if search:
    query += " AND t.description LIKE ?"
    params.append(f"%{search}%")
query += f" ORDER BY {order}"

df = pd.read_sql_query(query, conn, params=params)

st.markdown("---")
s1, s2, s3, s4 = st.columns(4)
s1.metric("", f"{len(df)} ")
s2.metric("", f"NT${df['amount_twd'].sum():,.0f}" if not df.empty else "NT$0")
s3.metric("", f"NT${df['amount_twd'].mean():,.0f}" if not df.empty else "NT$0")
s4.metric("", f"NT${df['amount_twd'].max():,.0f}" if not df.empty else "NT$0")

st.markdown("---")
if not df.empty:
    ddf = df.copy()
    ddf.columns = ["","","","","TWD","","","","","",""]
    ddf[""] = ddf[""].str[:16]
    ddf[""] = ddf[""].apply(lambda x: f"{x:,.0f}")
    ddf["TWD"] = ddf["TWD"].apply(lambda x: f"NT${x:,.0f}")
    pay_labels = {"cash": "", "credit_card": "", "mobile_pay": ""}
    ddf[""] = ddf[""].map(pay_labels).fillna(ddf[""])
    ddf[""] = ddf[""].apply(lambda x: "" if x else "")
    st.dataframe(ddf, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(" CSV", csv, "transactions.csv", "text/csv")
else:
    st.info("")
conn.close()

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

st.set_page_config(page_title="Transactions", page_icon="💰", layout="wide")
st.title("💰 交易紀錄")

conn = sqlite3.connect(DB_PATH)
trips = pd.read_sql_query("SELECT trip_id, trip_name FROM trips", conn)
if trips.empty:
    st.warning("沒有旅行紀錄")
    st.stop()

selected = st.selectbox("選擇旅行", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"] == selected]["trip_id"].values[0])

st.markdown("---")
col1, col2, col3 = st.columns(3)

categories = pd.read_sql_query(
    "SELECT DISTINCT category FROM transactions WHERE trip_id = ?",
    conn, params=(trip_id,)
)["category"].tolist()

with col1:
    cat_filter = st.multiselect("類別篩選", categories, default=categories)
with col2:
    sort_by = st.selectbox("排序", ["時間(新到舊)", "時間(舊到新)", "金額(高到低)", "金額(低到高)"])
with col3:
    search = st.text_input("搜尋說明", "")

sort_map = {
    "時間(新到舊)": "t.txn_datetime DESC",
    "時間(舊到新)": "t.txn_datetime ASC",
    "金額(高到低)": "t.amount_twd DESC",
    "金額(低到高)": "t.amount_twd ASC",
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
s1.metric("筆數", f"{len(df)} 筆")
s2.metric("總金額", f"NT${df['amount_twd'].sum():,.0f}" if not df.empty else "NT$0")
s3.metric("平均每筆", f"NT${df['amount_twd'].mean():,.0f}" if not df.empty else "NT$0")
s4.metric("最高單筆", f"NT${df['amount_twd'].max():,.0f}" if not df.empty else "NT$0")

st.markdown("---")
if not df.empty:
    ddf = df.copy()
    ddf.columns = ["時間","付款人","金額原幣","幣別","金額TWD","類別","說明","地點","付款方式","分帳","異常"]
    ddf["時間"] = ddf["時間"].str[:16]
    ddf["金額原幣"] = ddf["金額原幣"].apply(lambda x: f"{x:,.0f}")
    ddf["金額TWD"] = ddf["金額TWD"].apply(lambda x: f"NT${x:,.0f}")
    pay_labels = {"cash": "現金", "credit_card": "信用卡", "mobile_pay": "行動支付"}
    ddf["付款方式"] = ddf["付款方式"].map(pay_labels).fillna(ddf["付款方式"])
    ddf["異常"] = ddf["異常"].apply(lambda x: "⚠️" if x else "")
    st.dataframe(ddf, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("匯出 CSV", csv, "transactions.csv", "text/csv")
else:
    st.info("沒有符合條件的交易紀錄")
conn.close()

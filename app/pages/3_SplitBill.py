import streamlit as st
import sqlite3, os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
from src.split import SplitEngine

st.title("分帳中心")
engine = SplitEngine(DB_PATH)
uid = st.session_state.get("user_id", 1)
conn = sqlite3.connect(DB_PATH)
trips = pd.read_sql_query(
    """SELECT DISTINCT t.trip_id, t.trip_name FROM trips t
       JOIN trip_members tm ON t.trip_id = tm.trip_id
       WHERE tm.user_id = ?""",
    conn, params=(uid,)
)
if trips.empty:
    st.warning("尚無旅行紀錄"); conn.close(); st.stop()
selected = st.selectbox("選擇旅行", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"]==selected]["trip_id"].values[0])

st.markdown("---")
st.subheader("各人餘額")
balances = engine.get_net_balances(trip_id)
cols = st.columns(len(balances))
for i,(uid,info) in enumerate(balances.items()):
    with cols[i]:
        b = info["balance"]
        lbl = "應收" if b>0 else ("應付" if b<0 else "已結清")
        st.metric(info["name"], f"Y{b:,.0f}", delta=lbl)

st.markdown("---")
st.subheader("結算方案")
transfers = engine.settle_trip(trip_id)
if transfers:
    for t in transfers:
        st.info(f"{t['from_name']} 付給 {t['to_name']}：Y{t['amount']:,.0f}（NT${t['amount_twd']:,}）")
    st.success(f"只需 {len(transfers)} 筆轉帳即可完成結算！")
else:
    st.success("全部結清！")

st.markdown("---")
st.subheader("行程摘要")
summary = engine.get_trip_summary(trip_id)
c1,c2 = st.columns(2)
with c1:
    st.markdown("**付款排行**")
    for p in summary["payers"]:
        pct = p["amount"]/summary["total_amount"]*100 if summary["total_amount"]>0 else 0
        st.markdown(f"{p['name']}：Y{p['amount']:,.0f}（{p['count']} 次）")
        st.progress(pct/100)
with c2:
    st.markdown("**消費類別**")
    for c in summary["categories"]:
        pct = c["amount"]/summary["total_amount"]*100 if summary["total_amount"]>0 else 0
        st.markdown(f"{c['category']}：Y{c['amount']:,.0f}（{pct:.0f}%）")
        st.progress(pct/100)
conn.close()

st.markdown("---")
with st.expander("新增交易"):
    FALLBACK_RATES = {"JPY": 0.217, "USD": 32.0, "TWD": 1.0}
    CATEGORIES = ["餐飲", "交通", "住宿", "購物", "娛樂", "其他"]

    with sqlite3.connect(DB_PATH) as _conn:
        _users = pd.read_sql_query("SELECT user_id, name FROM users", _conn)
        _members = pd.read_sql_query(
            "SELECT user_id FROM trip_members WHERE trip_id = ?", _conn, params=(trip_id,)
        )

    member_ids = set(_members["user_id"].tolist())
    member_users = _users[_users["user_id"].isin(member_ids)]

    if member_users.empty:
        st.warning("此行程尚無成員，請先新增成員。")
    else:
        desc = st.text_input("說明", key="tx_desc")
        amount = st.number_input("金額", min_value=0.0, step=1.0, key="tx_amount")
        currency = st.selectbox("幣別", ["JPY", "TWD", "USD"], key="tx_currency")
        payer_name = st.selectbox("付款人", member_users["name"].tolist(), key="tx_payer")
        payer_id = int(member_users[member_users["name"] == payer_name]["user_id"].values[0])
        category = st.selectbox("類別", CATEGORIES, key="tx_category")
        split_method = st.selectbox("分帳方式", ["平均", "自訂"], key="tx_split")

        if st.button("送出", key="tx_submit"):
            if not desc.strip():
                st.error("說明不可為空。")
            elif amount <= 0:
                st.error("金額必須大於零。")
            else:
                amount_twd = round(amount * FALLBACK_RATES[currency])
                with sqlite3.connect(DB_PATH) as _conn:
                    cur = _conn.execute(
                        """INSERT INTO transactions
                           (trip_id, description, amount, currency, amount_twd, paid_by, category, split_method)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (trip_id, desc.strip(), amount, currency, amount_twd, payer_id, category, split_method),
                    )
                    tx_id = cur.lastrowid
                    member_count = len(member_ids)
                    share_amount = round(amount / member_count, 2) if member_count > 0 else amount
                    share_amount_twd = round(amount_twd / member_count) if member_count > 0 else amount_twd
                    for uid in member_ids:
                        _conn.execute(
                            """INSERT INTO split_details
                               (transaction_id, user_id, share_amount, share_amount_twd)
                               VALUES (?, ?, ?, ?)""",
                            (tx_id, uid, share_amount, share_amount_twd),
                        )
                    _conn.commit()
                st.success(f"交易「{desc.strip()}」已成功新增！")
                st.rerun()

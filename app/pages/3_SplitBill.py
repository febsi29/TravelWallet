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
st.subheader("還款進度")

# 從 settlements 讀取實際記錄（有 status）
with sqlite3.connect(DB_PATH) as _sc:
    _sdf = pd.read_sql_query("""
        SELECT s.settlement_id, s.from_user, s.to_user,
               s.amount, s.currency_code, s.amount_twd, s.status,
               fu.display_name AS from_name, tu.display_name AS to_name
        FROM settlements s
        JOIN users fu ON s.from_user = fu.user_id
        JOIN users tu ON s.to_user   = tu.user_id
        WHERE s.trip_id = ?
        ORDER BY s.settlement_id
    """, _sc, params=(trip_id,))

if _sdf.empty:
    # 尚無 settlements 記錄，用即時計算結果顯示
    transfers = engine.settle_trip(trip_id)
    if transfers:
        for t in transfers:
            st.markdown(
                f"<div style='padding:10px;margin:6px 0;border-radius:8px;background:#1e3a5f'>"
                f"<span style='color:#fca5a5;font-weight:bold'>{t['from_name']}</span>"
                f" → <span style='color:#86efac;font-weight:bold'>{t['to_name']}</span>"
                f"　<span style='color:#fbbf24;font-weight:bold'>¥{t['amount']:,.0f}</span>"
                f" <span style='color:#94a3b8'>（NT${t['amount_twd']:,}）</span></div>",
                unsafe_allow_html=True
            )
    else:
        st.success("全部結清！")
else:
    done = (_sdf["status"] == "completed").sum()
    total_s = len(_sdf)
    st.progress(done / total_s, text=f"已還款 {done} / {total_s} 筆")
    for _, row in _sdf.iterrows():
        paid = row["status"] == "completed"
        col_card, col_btn = st.columns([5, 1])
        bg = "#052e16" if paid else "#1e3a5f"
        badge = "<span style='color:#4ade80'>✓ 已還</span>" if paid else "<span style='color:#fbbf24'>⏳ 未還</span>"
        with col_card:
            st.markdown(
                f"<div style='padding:10px;border-radius:8px;background:{bg};margin:4px 0'>"
                f"<span style='color:#fca5a5;font-weight:bold'>{row['from_name']}</span>"
                f" → <span style='color:#86efac;font-weight:bold'>{row['to_name']}</span>"
                f"　<span style='color:#fbbf24;font-weight:bold'>{row['currency_code']} {row['amount']:,.0f}</span>"
                f" <span style='color:#94a3b8'>（NT${row['amount_twd']:,.0f}）</span>"
                f"　{badge}</div>",
                unsafe_allow_html=True
            )
        with col_btn:
            if not paid:
                if st.button("標記已還", key=f"settle_{row['settlement_id']}"):
                    with sqlite3.connect(DB_PATH) as _uc:
                        _uc.execute(
                            "UPDATE settlements SET status='completed', settled_at=datetime('now') WHERE settlement_id=?",
                            (int(row["settlement_id"]),)
                        )
                    st.rerun()
            else:
                if st.button("取消", key=f"unsettle_{row['settlement_id']}"):
                    with sqlite3.connect(DB_PATH) as _uc:
                        _uc.execute(
                            "UPDATE settlements SET status='pending', settled_at=NULL WHERE settlement_id=?",
                            (int(row["settlement_id"]),)
                        )
                    st.rerun()

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
        _all_users = pd.read_sql_query("SELECT user_id, display_name AS name FROM users", _conn)
        _members = pd.read_sql_query(
            "SELECT user_id FROM trip_members WHERE trip_id = ?", _conn, params=(trip_id,)
        )

    member_ids = set(_members["user_id"].tolist())

    if not member_ids:
        st.warning("此行程尚無成員，請先新增成員。")
    else:
        desc = st.text_input("說明", key="tx_desc")
        amount = st.number_input("金額", min_value=0.0, step=1.0, key="tx_amount")
        currency = st.selectbox("幣別", ["JPY", "TWD", "USD"], key="tx_currency")
        payer_name = st.selectbox("付款人", _all_users["name"].tolist(), key="tx_payer")
        payer_id = int(_all_users[_all_users["name"] == payer_name]["user_id"].values[0])
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

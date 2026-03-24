"""
10_Wallet.py - 多幣別電子錢包頁面
"""
import streamlit as st
import os, sys, pandas as pd
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.wallet import WalletService
from src.currency import COMMON_CURRENCIES

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("多幣別電子錢包")

user_id = st.session_state.get("user_id", 1)
svc = WalletService(DB_PATH)

# 總資產
try:
    total = svc.get_total_balance_twd(user_id)
    st.metric("總資產（台幣換算）", f"NT${total['total_twd']:,.0f}",
              help="以最新匯率換算各幣別餘額總和")
except Exception as e:
    st.error(str(e))
    total = {"total_twd": 0, "wallets": []}

# 錢包餘額列表
wallets = svc.get_all_wallets(user_id)
if wallets:
    st.subheader("各幣別餘額")
    rows = []
    for w in wallets:
        rows.append({
            "幣別": w["currency_code"],
            "餘額": f"{w['balance']:,.4f}",
            "鎖定中": f"{w['locked_balance']:,.4f}",
            "可用": f"{w['balance'] - w['locked_balance']:,.4f}",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 圓餅圖
    if total.get("wallets"):
        twd_list = total["wallets"]
        pie_data = pd.DataFrame([
            {"幣別": x["currency_code"], "台幣價值": x["balance_twd"]}
            for x in twd_list if x["balance_twd"] > 0
        ])
        if not pie_data.empty:
            fig = px.pie(pie_data, names="幣別", values="台幣價值",
                         title="資產分佈", color_discrete_sequence=px.colors.sequential.Blues_r)
            st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("尚無錢包，請先存款建立")

st.markdown("---")

# 操作區
tab1, tab2, tab3 = st.tabs(["存款", "提款", "兌換"])

currency_options = ["TWD"] + [c for c in COMMON_CURRENCIES.keys() if c != "TWD"]

with tab1:
    st.subheader("存款")
    dep_cur = st.selectbox("幣別", currency_options, key="dep_cur")
    dep_amt = st.number_input("金額", min_value=0.0001, value=10000.0, step=100.0, key="dep_amt")
    dep_note = st.text_input("備註", key="dep_note")
    if st.button("確認存款", type="primary"):
        try:
            result = svc.deposit(user_id, dep_cur, dep_amt, dep_note or None)
            st.success(f"存款成功！{dep_cur} 餘額：{result['balance']:,.4f}")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

with tab2:
    st.subheader("提款")
    wd_cur = st.selectbox("幣別", currency_options, key="wd_cur")
    wd_amt = st.number_input("金額", min_value=0.0001, value=1000.0, step=100.0, key="wd_amt")
    wd_note = st.text_input("備註", key="wd_note")
    if st.button("確認提款", type="primary"):
        try:
            result = svc.withdraw(user_id, wd_cur, wd_amt, wd_note or None)
            st.success(f"提款成功！{wd_cur} 餘額：{result['balance']:,.4f}")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

with tab3:
    st.subheader("幣別兌換")
    col1, col2 = st.columns(2)
    with col1:
        from_cur = st.selectbox("從", currency_options, key="tr_from")
        tr_amt = st.number_input("兌換金額", min_value=0.0001, value=1000.0, step=100.0)
    with col2:
        to_cur = st.selectbox("換成", currency_options, index=1, key="tr_to")
        locked_rate = st.number_input("鎖定匯率（0=市價）", min_value=0.0, value=0.0, format="%.4f")
    if st.button("確認兌換", type="primary"):
        try:
            result = svc.transfer(
                user_id, from_cur, to_cur, tr_amt,
                locked_rate=locked_rate if locked_rate > 0 else None,
            )
            st.success(
                f"兌換成功！{from_cur} {tr_amt:,.4f} -> {to_cur} {result['to_amount']:,.4f}"
                f"（匯率 {result['rate']:.6f}）"
            )
            st.rerun()
        except ValueError as e:
            st.error(str(e))

# 交易紀錄
st.markdown("---")
st.subheader("最近交易紀錄")
history = svc.get_transaction_history(user_id, limit=20)
if history:
    rows = []
    for h in history:
        rows.append({
            "時間": h.get("created_at", "")[:16],
            "類型": h["txn_type"],
            "金額": f"{h['amount']:,.4f}",
            "幣別": h["currency_code"],
            "匯率": f"{h.get('exchange_rate') or '--'}",
            "備註": h.get("note") or "",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.caption("尚無交易紀錄")

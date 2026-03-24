"""
13_Payment.py - 分帳付款整合頁面
"""
import streamlit as st
import os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.payment import PaymentService

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("分帳付款整合")
st.caption("產生付款連結，讓旅伴透過 LINE Pay / JKO Pay / PayPal 付款")

user_id = st.session_state.get("user_id", 1)
svc = PaymentService(DB_PATH)

PROVIDER_LABELS = {
    "line_pay": "LINE Pay",
    "jko_pay": "街口支付",
    "paypal": "PayPal",
}

# 查詢我的待付款
st.subheader("我的待付款")
try:
    pending = svc.get_pending_payments(user_id=user_id)
    if pending:
        rows = []
        for p in pending:
            rows.append({
                "結算 ID": p["settlement_id"],
                "付給": p.get("to_name", "--"),
                "金額": f"{p['amount']:,.2f}",
                "幣別": p["currency_code"],
                "狀態": p["status"],
                "付款平台": PROVIDER_LABELS.get(p.get("provider", ""), p.get("provider", "--")),
                "連結": p.get("payment_url", "--"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("目前沒有待付款項目")
except ValueError as e:
    st.error(str(e))

st.markdown("---")

# 產生付款連結
st.subheader("產生付款連結")
col1, col2, col3 = st.columns(3)
with col1:
    settlement_id = st.number_input("結算 ID", min_value=1, step=1, value=1)
with col2:
    provider = st.selectbox("付款方式", list(PROVIDER_LABELS.keys()),
                            format_func=lambda x: PROVIDER_LABELS[x])
with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    gen_btn = st.button("產生連結", type="primary", use_container_width=True)

if gen_btn:
    try:
        link = svc.generate_payment_link(settlement_id=int(settlement_id), provider=provider)
        st.session_state["generated_link"] = link
        st.success(f"付款連結已產生！")
    except ValueError as e:
        st.error(str(e))

if "generated_link" in st.session_state:
    link = st.session_state["generated_link"]
    st.info(f"**{PROVIDER_LABELS.get(link['provider'])}** 付款連結")
    st.code(link["payment_url"])
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("金額", f"{link['amount']:,.2f} {link['currency_code']}")
    col_b.metric("付款方", link.get("from_name", "--"))
    col_c.metric("收款方", link.get("to_name", "--"))

    if link.get("qr_code_data"):
        st.caption("QR Code 資料（可複製後轉換）")
        st.code(link["qr_code_data"][:100] + "..." if len(link.get("qr_code_data", "")) > 100 else link["qr_code_data"])

    sim_col, _ = st.columns([1, 2])
    with sim_col:
        if st.button("模擬付款（DEMO）"):
            try:
                result = svc.simulate_payment(link["link_id"])
                st.success(f"付款成功！參考號：{result['provider_ref']}")
                del st.session_state["generated_link"]
                st.rerun()
            except ValueError as e:
                st.error(str(e))

# 查詢結算的付款紀錄
st.markdown("---")
st.subheader("結算付款紀錄查詢")
query_sid = st.number_input("結算 ID", min_value=1, step=1, value=1, key="query_sid")
if st.button("查詢"):
    try:
        records = svc.get_settlement_payments(settlement_id=int(query_sid))
        if records:
            rows = []
            for r in records:
                rows.append({
                    "連結 ID": r["link_id"],
                    "付款方式": PROVIDER_LABELS.get(r.get("provider", ""), r.get("provider", "--")),
                    "狀態": r["status"],
                    "金額": f"{r['amount']:,.2f} {r['currency_code']}",
                    "建立時間": r.get("created_at", "")[:16],
                    "付款時間": r.get("paid_at", "--"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("此結算尚無付款紀錄")
    except ValueError as e:
        st.error(str(e))

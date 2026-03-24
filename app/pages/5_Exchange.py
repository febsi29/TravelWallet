import streamlit as st
import os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
from src.currency import CurrencyManager, COMMON_CURRENCIES, FALLBACK_RATES
from src.rate_alert import RateAlertService

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("匯率查詢")
cm = CurrencyManager()

st.subheader("匯率（以台幣為基準）")
rate_data = []
for code, info in COMMON_CURRENCIES.items():
    try:
        rate = cm.get_rate(code)
    except Exception:
        rate = FALLBACK_RATES.get(code, 0)
    twd_per = round(1/rate, 2) if rate > 0 else 0
    rate_data.append({"貨幣": f"{info['symbol']} {code}", "名稱": info["name"],
        "國家": info["country"], "1 TWD =": f"{rate:.4f} {code}", "1 單位 =": f"NT${twd_per:,.2f}"})
st.dataframe(pd.DataFrame(rate_data), use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("換算工具")
c1,c2,c3 = st.columns([2,1,2])
currency_list = ["TWD"] + list(COMMON_CURRENCIES.keys())
with c1:
    amount = st.number_input("金額", value=10000, min_value=0, step=100)
    from_curr = st.selectbox("從", currency_list, index=currency_list.index("JPY"))
with c2:
    st.markdown("<br><br><p style='text-align:center; font-size:2rem'>-></p>", unsafe_allow_html=True)
with c3:
    to_curr = st.selectbox("換", currency_list, index=0)
    if st.button("換算", type="primary", use_container_width=True):
        result = cm.convert(amount, from_curr, to_curr)
        from_str = cm.format_amount(amount, from_curr) if from_curr != "TWD" else f"NT${amount:,}"
        to_str = cm.format_amount(result["amount"], to_curr) if to_curr != "TWD" else f"NT${result['amount']:,.0f}"
        st.success(f"{from_str} = **{to_str}**")
        st.caption(f"匯率：{result['rate']:.6f}")

# ── 匯率到價提醒區塊 ──────────────────────────────────────────
st.markdown("---")
st.subheader("匯率到價提醒")

user_id = st.session_state.get("user_id", 1)
svc = RateAlertService(DB_PATH)

# 建立新提醒
with st.expander("新增提醒", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        alert_currency = st.selectbox("目標貨幣", list(COMMON_CURRENCIES.keys()), key="alert_cur")
    with col2:
        try:
            cur_rate = cm.get_rate(alert_currency)
        except Exception:
            cur_rate = FALLBACK_RATES.get(alert_currency, 1.0)
        alert_rate = st.number_input("目標匯率（1 TWD =）", value=float(round(cur_rate, 4)),
                                     min_value=0.0001, format="%.4f", step=0.01)
    with col3:
        direction = st.selectbox("方向", ["above", "below"], format_func=lambda x: "高於" if x == "above" else "低於")
    with col4:
        note = st.text_input("備註（選填）")

    if st.button("建立提醒", type="primary"):
        try:
            svc.create_alert(user_id=user_id, target_currency=alert_currency,
                             target_rate=alert_rate, direction=direction,
                             note=note or None)
            st.success("提醒已建立")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

# 檢查並顯示已觸發的提醒
triggered = svc.get_triggered_alerts(user_id)
if triggered:
    st.warning(f"有 {len(triggered)} 個匯率提醒已達到目標！")
    for t in triggered:
        st.info(
            f"{t['target_currency']}：目標 {t['target_rate']:.4f}，"
            f"目前 {t.get('current_rate', 0):.4f}（{'高於' if t['direction'] == 'above' else '低於'}）"
            + (f" — {t['note']}" if t.get('note') else "")
        )

# 顯示啟用中的提醒列表
alerts = svc.get_alerts(user_id, active_only=True)
if alerts:
    st.markdown("**啟用中的提醒**")
    rows = []
    for a in alerts:
        try:
            cur = cm.get_rate(a["target_currency"])
        except Exception:
            cur = FALLBACK_RATES.get(a["target_currency"], 0)
        rows.append({
            "ID": a["alert_id"],
            "貨幣": a["target_currency"],
            "目標": f"{a['target_rate']:.4f}",
            "方向": "高於" if a["direction"] == "above" else "低於",
            "目前匯率": f"{cur:.4f}",
            "備註": a.get("note") or "",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    deactivate_id = st.number_input("停用提醒 ID（0=不停用）", min_value=0, step=1, value=0)
    if st.button("停用") and deactivate_id > 0:
        try:
            svc.deactivate_alert(deactivate_id)
            st.success(f"提醒 #{deactivate_id} 已停用")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
else:
    st.caption("目前沒有啟用中的提醒")

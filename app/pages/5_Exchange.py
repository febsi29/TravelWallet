import streamlit as st
import os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
from src.currency import CurrencyManager, COMMON_CURRENCIES, FALLBACK_RATES

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

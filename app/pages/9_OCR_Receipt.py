"""
9_OCR_Receipt.py - 電子收據 OCR 掃描頁面
"""
import streamlit as st
import os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.ocr import ReceiptOCR

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

st.title("收據 OCR 掃描")
st.caption("上傳收據圖片，自動辨識金額、商家、日期與類別")

user_id = st.session_state.get("user_id", 1)
ocr = ReceiptOCR(DB_PATH)

# 上傳區
col1, col2 = st.columns([1, 1])
with col1:
    uploaded = st.file_uploader("上傳收據圖片", type=["jpg", "jpeg", "png", "bmp"])
    trip_id_input = st.number_input("旅行 ID（選填）", min_value=0, step=1, value=1)

    if st.button("開始掃描", type="primary", disabled=(uploaded is None)):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        try:
            result = ocr.scan_receipt(
                image_path=tmp_path,
                user_id=user_id,
                trip_id=int(trip_id_input) if trip_id_input > 0 else None,
            )
            st.session_state["last_scan"] = result
            st.success("掃描完成")
        except ValueError as e:
            st.error(str(e))
        finally:
            os.unlink(tmp_path)

with col2:
    if "last_scan" in st.session_state:
        r = st.session_state["last_scan"]
        st.subheader("辨識結果")
        st.metric("信心指數", f"{r['confidence']*100:.0f}%")
        cols = st.columns(2)
        cols[0].metric("金額", f"{r.get('extracted_amount') or '--'}")
        cols[1].metric("幣別", r.get("extracted_currency") or "--")
        st.write(f"**商家：** {r.get('extracted_merchant') or '未辨識'}")
        st.write(f"**類別：** {r.get('extracted_category') or '其他'}")
        st.write(f"**日期：** {r.get('extracted_date') or '未辨識'}")

        st.markdown("---")
        col_ok, col_rej = st.columns(2)
        with col_ok:
            if st.button("確認並建立交易", type="primary"):
                try:
                    txn = ocr.confirm_and_create_txn(r["receipt_id"])
                    st.success(f"交易已建立：txn_id={txn['txn_id']}")
                    del st.session_state["last_scan"]
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        with col_rej:
            if st.button("拒絕此收據"):
                ocr.reject_receipt(r["receipt_id"])
                st.info("已標記為拒絕")
                del st.session_state["last_scan"]
                st.rerun()

# 歷史收據列表
st.markdown("---")
st.subheader("收據紀錄")

filter_trip = st.number_input("依旅行 ID 篩選（0=全部）", min_value=0, step=1, value=0)
try:
    receipts = ocr.get_receipts(
        user_id=user_id,
        trip_id=int(filter_trip) if filter_trip > 0 else None,
    )
except ValueError as e:
    st.error(str(e))
    receipts = []

if receipts:
    rows = []
    for r in receipts:
        rows.append({
            "ID": r["receipt_id"],
            "商家": r.get("extracted_merchant") or "--",
            "金額": r.get("extracted_amount") or 0,
            "幣別": r.get("extracted_currency") or "--",
            "類別": r.get("extracted_category") or "--",
            "日期": r.get("extracted_date") or "--",
            "狀態": r.get("status", "--"),
            "信心": f"{(r.get('confidence') or 0)*100:.0f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.caption("尚無收據紀錄")

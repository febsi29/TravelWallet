import streamlit as st
import sqlite3, os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
from src.anomaly import AnomalyDetector

st.title("異常偵測")
st.caption("使用 Z-Score、IQR、隔離森林演算法進行多數投票")
detector = AnomalyDetector(DB_PATH)
uid = st.session_state.get("user_id", 1)
with sqlite3.connect(DB_PATH) as conn:
    trips = pd.read_sql_query(
        """SELECT DISTINCT t.trip_id, t.trip_name FROM trips t
           JOIN trip_members tm ON t.trip_id = tm.trip_id
           WHERE tm.user_id = ?""",
        conn, params=(uid,)
    )
if trips.empty:
    st.warning("尚無旅行紀錄"); st.stop()

selected = st.selectbox("選擇旅行", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"]==selected]["trip_id"].values[0])

st.markdown("---")
with st.expander("偵測參數"):
    c1,c2,c3 = st.columns(3)
    with c1: z_th = st.slider("Z-Score 門檻", 1.0, 3.0, 2.0, 0.1)
    with c2: iqr_m = st.slider("IQR 倍數", 1.0, 3.0, 1.5, 0.1)
    with c3: if_c = st.slider("隔離森林污染率", 0.05, 0.3, 0.1, 0.01)

if st.button("執行偵測", type="primary", use_container_width=True):
    with st.spinner("分析中..."):
        results = detector.detect_all(trip_id, z_th, iqr_m, if_c)
    anomalies = [r for r in results if r["is_anomaly"]]

    st.markdown("---")
    c1,c2,c3 = st.columns(3)
    c1.metric("總筆數", f"{len(results)}")
    c2.metric("異常筆數", f"{len(anomalies)}")
    c3.metric("異常率", f"{len(anomalies)/len(results)*100:.1f}%" if results else "0%")

    z_n = sum(1 for r in results if r["is_anomaly_zscore"])
    iq_n = sum(1 for r in results if r["is_anomaly_iqr"])
    if_n = sum(1 for r in results if r["is_anomaly_if"])
    m1,m2,m3 = st.columns(3)
    m1.metric("Z-Score 標記", f"{z_n}")
    m2.metric("IQR 標記", f"{iq_n}")
    m3.metric("隔離森林標記", f"{if_n}")

    if anomalies:
        st.markdown("---")
        st.subheader("異常交易")
        for a in anomalies:
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                st.error(f"#{a['txn_id']} | NT${a['amount_twd']:,.0f} | {a['category']} | {a['description']} | 標記 {a['flags']}/3")
            with col_btn:
                if st.button("標記為正常", key=f"false_positive_{a['txn_id']}"):
                    try:
                        conn_upd = sqlite3.connect(DB_PATH)
                        conn_upd.execute(
                            "UPDATE transactions SET is_anomaly = 0 WHERE txn_id = ?",
                            (a["txn_id"],)
                        )
                        conn_upd.commit()
                        conn_upd.close()
                        st.success(f"交易 #{a['txn_id']} 已標記為正常")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新失敗：{e}")
    else:
        st.success("未偵測到異常！所有交易均在正常範圍內。")

    st.markdown("---")
    st.subheader("完整結果")
    df = pd.DataFrame(results)
    dcols = ["txn_id","amount_twd","category","description","zscore","is_anomaly_zscore","is_anomaly_iqr","is_anomaly_if","flags","is_anomaly"]
    ddf = df[dcols].copy()
    ddf.columns = ["交易ID","金額","類別","說明","Z-Score","Z","IQR","IF","標記","結果"]
    ddf["金額"] = ddf["金額"].apply(lambda x: f"NT${x:,.0f}")
    ddf["Z"] = ddf["Z"].apply(lambda x: "!!" if x else "")
    ddf["IQR"] = ddf["IQR"].apply(lambda x: "!!" if x else "")
    ddf["IF"] = ddf["IF"].apply(lambda x: "!!" if x else "")
    ddf["結果"] = ddf["結果"].apply(lambda x: "異常" if x else "正常")
    st.dataframe(ddf, use_container_width=True, hide_index=True)

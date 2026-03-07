import streamlit as st
import sqlite3, os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
from src.anomaly import AnomalyDetector

st.set_page_config(page_title="Anomaly Alerts", page_icon="AL", layout="wide")
st.title("Anomaly Detection")
st.caption("Z-Score + IQR + Isolation Forest with majority vote")
detector = AnomalyDetector(DB_PATH)
conn = sqlite3.connect(DB_PATH)
trips = pd.read_sql_query("SELECT trip_id, trip_name FROM trips", conn)
conn.close()
if trips.empty:
    st.warning("No trips"); st.stop()

selected = st.selectbox("Select trip", trips["trip_name"].tolist())
trip_id = int(trips[trips["trip_name"]==selected]["trip_id"].values[0])

st.markdown("---")
with st.expander("Detection Parameters"):
    c1,c2,c3 = st.columns(3)
    with c1: z_th = st.slider("Z-Score threshold", 1.0, 3.0, 2.0, 0.1)
    with c2: iqr_m = st.slider("IQR multiplier", 1.0, 3.0, 1.5, 0.1)
    with c3: if_c = st.slider("IF contamination", 0.05, 0.3, 0.1, 0.01)

if st.button("Run Detection", type="primary", use_container_width=True):
    with st.spinner("Analyzing..."):
        results = detector.detect_all(trip_id, z_th, iqr_m, if_c)
    anomalies = [r for r in results if r["is_anomaly"]]

    st.markdown("---")
    c1,c2,c3 = st.columns(3)
    c1.metric("Total", f"{len(results)}")
    c2.metric("Anomalies", f"{len(anomalies)}")
    c3.metric("Rate", f"{len(anomalies)/len(results)*100:.1f}%" if results else "0%")

    z_n = sum(1 for r in results if r["is_anomaly_zscore"])
    iq_n = sum(1 for r in results if r["is_anomaly_iqr"])
    if_n = sum(1 for r in results if r["is_anomaly_if"])
    m1,m2,m3 = st.columns(3)
    m1.metric("Z-Score flagged", f"{z_n}")
    m2.metric("IQR flagged", f"{iq_n}")
    m3.metric("IF flagged", f"{if_n}")

    if anomalies:
        st.markdown("---")
        st.subheader("Flagged Transactions")
        for a in anomalies:
            st.error(f"txn#{a['txn_id']} | NT${a['amount_twd']:,.0f} | {a['category']} | {a['description']} | Flags: {a['flags']}/3")
    else:
        st.success("No anomalies detected! All transactions are within normal range.")

    st.markdown("---")
    st.subheader("Full Results")
    df = pd.DataFrame(results)
    dcols = ["txn_id","amount_twd","category","description","zscore","is_anomaly_zscore","is_anomaly_iqr","is_anomaly_if","flags","is_anomaly"]
    ddf = df[dcols].copy()
    ddf.columns = ["ID","Amount","Category","Description","Z-Score","Z","IQR","IF","Flags","Final"]
    ddf["Amount"] = ddf["Amount"].apply(lambda x: f"NT${x:,.0f}")
    ddf["Z"] = ddf["Z"].apply(lambda x: "!!" if x else "")
    ddf["IQR"] = ddf["IQR"].apply(lambda x: "!!" if x else "")
    ddf["IF"] = ddf["IF"].apply(lambda x: "!!" if x else "")
    ddf["Final"] = ddf["Final"].apply(lambda x: "ANOMALY" if x else "normal")
    st.dataframe(ddf, use_container_width=True, hide_index=True)

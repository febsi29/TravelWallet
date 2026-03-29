import streamlit as st
import sqlite3, os, sys, pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
from src.analytics import Analytics

st.title("消費分析")
ana = Analytics(DB_PATH)
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

tab1,tab2,tab3,tab4 = st.tabs(["本團 vs 全國","類別分析","每日趨勢","分帳行為"])

with tab1:
    pvn = ana.personal_vs_national(trip_id)
    p,n,c = pvn["personal"],pvn["national"],pvn["comparison"]
    # 從 DB 取成員數與全團總計
    with sqlite3.connect(DB_PATH) as _c:
        nm = _c.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id=?", (trip_id,)).fetchone()[0]
        tot = _c.execute("SELECT COALESCE(SUM(amount_twd),0) FROM transactions WHERE trip_id=?", (trip_id,)).fetchone()[0]
    c0,c1,c2,c3 = st.columns(4)
    c0.metric("全團總計", f"NT${tot:,.0f}", help=f"{nm} 人")
    c1.metric("每人平均", f"NT${p['per_person_total']:,}")
    c2.metric(f"全國平均（{n['year']}）", f"NT${n['avg_total']:,.0f}")
    c3.metric("差距", f"{c['diff_pct']:+.1f}%", delta=f"NT${c['diff_total']:+,.0f}")
    st.info(c["verdict"])
    import plotly.graph_objects as go
    fig = go.Figure(data=[
        go.Bar(name="本團每人平均", x=["行程總計","每日平均"], y=[p["per_person_total"],p["per_person_daily"]], marker_color="#2563EB"),
        go.Bar(name="全國每人平均", x=["行程總計","每日平均"], y=[n["avg_total"],n["avg_daily"]], marker_color="#93C5FD"),
    ])
    fig.update_layout(barmode="group", height=350, yaxis_title="NT$（每人）")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    cat_comp = ana.category_vs_national(trip_id)
    cats = [c["category"] for c in cat_comp]
    pers = [c["personal_pct"] for c in cat_comp]
    natl = [c["national_pct"] for c in cat_comp]
    import plotly.graph_objects as go
    fig = go.Figure(data=[
        go.Bar(name="本團", x=cats, y=pers, marker_color="#2563EB"),
        go.Bar(name="全國平均", x=cats, y=natl, marker_color="#93C5FD"),
    ])
    fig.update_layout(barmode="group", yaxis_title="百分比 (%)", height=400)
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    daily = ana.daily_spending(trip_id)
    if daily:
        import plotly.graph_objects as go
        dlbl = [f"第 {d['day']} 天" for d in daily]
        damt = [d["daily_twd"] for d in daily]
        camt = [d["cumulative_twd"] for d in daily]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="每日", x=dlbl, y=damt, marker_color="#2563EB",
            text=[f"NT${a:,.0f}" for a in damt], textposition="outside"))
        fig.add_trace(go.Scatter(name="累計", x=dlbl, y=camt,
            mode="lines+markers", line=dict(color="#DC2626",width=2), yaxis="y2"))
        fig.update_layout(yaxis=dict(title="每日消費 (NT$)"),
            yaxis2=dict(title="累計消費 (NT$)", overlaying="y", side="right"), height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    split = ana.split_behavior(trip_id)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**付款排行**")
        for p in split["payer_ranking"]:
            st.markdown(f"- {p['name']}：NT${p['total_twd']:,.0f}（{p['times']} 次）")
    with c2:
        st.markdown("**實際分擔**")
        for s in split["share_ranking"]:
            st.markdown(f"- {s['name']}：NT${s['total_twd']:,.0f}")

st.divider()
st.subheader("匯出分析報告")

col1, col2, col3 = st.columns(3)

with col1:
    try:
        cat_comp = ana.category_vs_national(trip_id)
        cat_df = pd.DataFrame(cat_comp)
        csv_cat = cat_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="匯出類別分析",
            data=csv_cat,
            file_name=f"類別分析_{selected}.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.warning(f"類別分析匯出失敗：{e}")

with col2:
    try:
        daily = ana.daily_spending(trip_id)
        daily_df = pd.DataFrame(daily) if daily else pd.DataFrame()
        csv_daily = daily_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="匯出每日趨勢",
            data=csv_daily,
            file_name=f"每日趨勢_{selected}.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.warning(f"每日趨勢匯出失敗：{e}")

with col3:
    try:
        pvn = ana.personal_vs_national(trip_id)
        pvn_rows = [
            {"項目": "每人總花費 (NT$)", "個人": pvn["personal"]["per_person_total"], "全國平均": pvn["national"]["avg_total"]},
            {"項目": "每人每日花費 (NT$)", "個人": pvn["personal"]["per_person_daily"], "全國平均": pvn["national"]["avg_daily"]},
            {"項目": "差距百分比 (%)", "個人": pvn["comparison"]["diff_pct"], "全國平均": ""},
            {"項目": "差距金額 (NT$)", "個人": pvn["comparison"]["diff_total"], "全國平均": ""},
            {"項目": "結論", "個人": pvn["comparison"]["verdict"], "全國平均": ""},
        ]
        pvn_df = pd.DataFrame(pvn_rows)
        csv_pvn = pvn_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="匯出個人 vs 全國",
            data=csv_pvn,
            file_name=f"個人vs全國_{selected}.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.warning(f"個人 vs 全國匯出失敗：{e}")

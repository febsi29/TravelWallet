"""
TravelWallet - Main Streamlit App
"""
import streamlit as st
import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


def _bootstrap_db() -> None:
    """若資料庫不存在或 trips 資料表為空，自動執行 schema + seed。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    schema_path = os.path.join(BASE_DIR, "database", "schema.sql")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 建立 schema（IF NOT EXISTS，安全重複執行）
            if os.path.exists(schema_path):
                with open(schema_path, encoding="utf-8") as f:
                    conn.executescript(f.read())
            # 若 users 表空才跑 seed
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count == 0:
                from database import seed_data  # noqa: F401
    except Exception:
        pass  # 初始化失敗不阻擋 UI 啟動


_bootstrap_db()

st.set_page_config(
    page_title="智慧旅遊錢包",
    page_icon="TW",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Global CSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        text-align: center;
        margin-top: 0;
        margin-bottom: 16px;
        font-weight: 400;
    }
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
        border-radius: 10px;
        padding: 16px;
        border: 1px solid #BFDBFE;
    }
    [data-testid="metric-container"] label {
        font-size: 0.95rem;
        font-weight: 600;
        color: #1E3A5F;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F172A;
    }
</style>
""", unsafe_allow_html=True)


# --- Data Loading ---
@st.cache_data
def load_trip_list():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT trip_id, trip_name, destination, start_date, end_date, status FROM trips ORDER BY start_date DESC")
    trips = cursor.fetchall()
    conn.close()
    return trips


@st.cache_data
def load_dashboard_data(trip_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT trip_name, destination, currency_code, start_date, end_date, total_budget,
               julianday(end_date) - julianday(start_date) + 1
        FROM trips WHERE trip_id = ?
    """, (trip_id,))
    trip = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,))
    members = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount_twd), 0), COALESCE(SUM(amount), 0)
        FROM transactions WHERE trip_id = ?
    """, (trip_id,))
    txn_count, total_twd, total_original = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount_twd), 0)
        FROM settlements WHERE trip_id = ? AND status = 'pending'
    """, (trip_id,))
    pending_count, pending_twd = cursor.fetchone()

    cursor.execute("""
        SELECT category, SUM(amount_twd) FROM transactions
        WHERE trip_id = ? GROUP BY category ORDER BY SUM(amount_twd) DESC
    """, (trip_id,))
    categories = cursor.fetchall()

    cursor.execute("""
        SELECT DATE(txn_datetime), SUM(amount_twd) FROM transactions
        WHERE trip_id = ? GROUP BY DATE(txn_datetime) ORDER BY DATE(txn_datetime)
    """, (trip_id,))
    daily = cursor.fetchall()

    cursor.execute("""
        SELECT t.txn_datetime, t.amount, t.currency_code, t.amount_twd,
               t.category, t.description, u.display_name, t.is_anomaly
        FROM transactions t
        JOIN users u ON t.paid_by = u.user_id
        WHERE t.trip_id = ?
        ORDER BY t.txn_datetime DESC LIMIT 10
    """, (trip_id,))
    recent = cursor.fetchall()

    conn.close()

    return {
        "trip": trip, "members": members,
        "txn_count": txn_count, "total_twd": total_twd, "total_original": total_original,
        "pending_count": pending_count, "pending_twd": pending_twd,
        "categories": categories, "daily": daily, "recent": recent,
    }


# --- Dashboard Page ---
def dashboard():
    st.markdown('<p class="main-header">智慧旅遊錢包</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">你的貼身旅遊財務管家</p>', unsafe_allow_html=True)

    trips = load_trip_list()
    if not trips:
        st.warning("還沒有任何旅行紀錄，請先執行 seed_data.py 生成測試資料")
        st.stop()

    st.sidebar.markdown("### 選擇旅行")
    trip_options = {f"{t[1]} ({t[3][:7]})": t[0] for t in trips}
    selected_trip_label = st.sidebar.selectbox("旅行", list(trip_options.keys()), label_visibility="collapsed")
    selected_trip_id = trip_options[selected_trip_label]

    data = load_dashboard_data(selected_trip_id)
    trip = data["trip"]

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    per_person = round(data["total_twd"] / data["members"]) if data["members"] > 0 else 0
    budget = trip[5] if trip[5] else 0
    remaining = budget - per_person

    with col1:
        st.metric("總花費", f"NT${data['total_twd']:,.0f}", help="全團總消費（台幣）")
    with col2:
        st.metric("每人花費", f"NT${per_person:,}", help="總花費 / 人數")
    with col3:
        delta_color = "normal" if remaining >= 0 else "inverse"
        st.metric("預算剩餘", f"NT${remaining:,.0f}", delta=f"預算 NT${budget:,.0f}", delta_color=delta_color)
    with col4:
        st.metric("未結清分帳", f"{data['pending_count']} 筆", delta=f"NT${data['pending_twd']:,.0f}")

    st.markdown("---")
    info_cols = st.columns(5)
    info_cols[0].markdown(f"**目的地:** {trip[1]}")
    info_cols[1].markdown(f"**幣別:** {trip[2]}")
    info_cols[2].markdown(f"**日期:** {trip[3]} ~ {trip[4]}")
    info_cols[3].markdown(f"**人數:** {data['members']} 人")
    info_cols[4].markdown(f"**交易:** {data['txn_count']} 筆")

    st.markdown("---")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("#### 消費類別分佈")
        if data["categories"]:
            import plotly.express as px
            cat_names = [c[0] for c in data["categories"]]
            cat_values = [c[1] for c in data["categories"]]
            colors = ["#1D4ED8", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"]
            fig = px.pie(
                names=cat_names, values=cat_values,
                color_discrete_sequence=colors,
                hole=0.4,
            )
            fig.update_traces(textposition="inside", textinfo="label+percent")
            fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=350)
            st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        st.markdown("#### 每日消費趨勢")
        if data["daily"]:
            import plotly.graph_objects as go
            days = [f"第 {i+1} 天" for i in range(len(data["daily"]))]
            amounts = [d[1] for d in data["daily"]]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=days, y=amounts,
                marker_color="#2563EB",
                text=[f"NT${a:,.0f}" for a in amounts],
                textposition="outside",
            ))
            if budget > 0 and data["members"] > 0:
                daily_budget = budget / int(trip[6])
                fig.add_hline(
                    y=daily_budget, line_dash="dash", line_color="#DC2626",
                    annotation_text=f"每人每日預算 NT${daily_budget:,.0f}",
                )
            fig.update_layout(
                yaxis_title="消費金額 (NT$)",
                margin=dict(t=20, b=40, l=40, r=20),
                height=350,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 最近交易紀錄")
    if data["recent"]:
        import pandas as pd
        df = pd.DataFrame(data["recent"], columns=[
            "時間", "金額(原幣)", "幣別", "金額(TWD)", "類別", "說明", "付款人", "異常"
        ])
        df["時間"] = df["時間"].str[:16]
        df["金額(原幣)"] = df["金額(原幣)"].apply(lambda x: f"{x:,.0f}")
        df["金額(TWD)"] = df["金額(TWD)"].apply(lambda x: f"NT${x:,.0f}")
        df["異常"] = df["異常"].apply(lambda x: "[!]" if x else "")
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption("TravelWallet v1.0 | 資料來源：交通部觀光署 | Built with Streamlit")


# --- 側邊欄使用者切換 ---
def _load_users() -> list[tuple[int, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, display_name FROM users ORDER BY user_id")
        return cursor.fetchall()


def render_user_selector() -> None:
    st.sidebar.markdown("### 目前使用者")
    try:
        users = _load_users()
        if users:
            user_labels = [u[1] for u in users]
            user_ids = [u[0] for u in users]

            current_id = st.session_state.get("user_id")
            default_index = user_ids.index(current_id) if current_id in user_ids else 0

            selected_label = st.sidebar.selectbox(
                "使用者",
                user_labels,
                index=default_index,
                label_visibility="collapsed",
            )
            selected_index = user_labels.index(selected_label)
            st.session_state["user_id"] = user_ids[selected_index]
            st.session_state["user_name"] = selected_label
            st.sidebar.caption(f"已選擇：{selected_label}")
        else:
            st.sidebar.warning("資料庫中尚無使用者資料")
    except Exception as e:
        st.sidebar.warning(f"無法讀取使用者清單：{e}")

    st.sidebar.markdown("---")


render_user_selector()

# --- Navigation ---
pg = st.navigation([
    st.Page(dashboard, title="儀表板"),
    st.Page("pages/2_Transactions.py", title="交易紀錄"),
    st.Page("pages/3_SplitBill.py", title="分帳中心"),
    st.Page("pages/4_TripPlanner.py", title="行程規劃"),
    st.Page("pages/5_Exchange.py", title="匯率查詢"),
    st.Page("pages/6_Analytics.py", title="消費分析"),
    st.Page("pages/7_Alerts.py", title="異常偵測"),
    st.Page("pages/8_AI_Assistant.py", title="AI 助手"),
])
pg.run()

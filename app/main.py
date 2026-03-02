"""
TravelWallet - 台灣旅人智慧旅遊錢包
Streamlit 主頁面
"""
import streamlit as st

st.set_page_config(
    page_title="TravelWallet 旅遊錢包",
    page_icon="🧳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🧳 TravelWallet")
st.subheader("台灣旅人智慧旅遊錢包")

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("本趟總花費", "NT$ --")
with col2:
    st.metric("剩餘預算", "NT$ --")
with col3:
    st.metric("未結清分帳", "NT$ --")
with col4:
    st.metric("旅行天數", "-- 天")

st.markdown("---")
st.info("👈 從左側選單選擇功能開始使用")

# TODO: Week 6 完善 Dashboard

"""
01_EDA_gov_data.py - 政府開放資料探索性分析

分析「歷年國人出國旅遊重要指標統計表」
產出圖表存入 docs/demo_screenshots/

使用方式：
  cd C:\\Users\\newbi\\Desktop\\TravelWallet
  python notebooks/01_EDA_gov_data.py
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import os

# 設定中文字型（Windows）
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial"]
matplotlib.rcParams["axes.unicode_minus"] = False

# 路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "docs", "demo_screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data():
    """從資料庫載入政府統計資料"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM gov_outbound_stats ORDER BY year", conn)
    conn.close()
    print(f"📂 載入 {len(df)} 筆資料 ({df['year'].min()}~{df['year'].max()})")
    return df


# ============================================================
#  圖表 1：歷年國人出國人次趨勢
# ============================================================
def plot_outbound_trend(df):
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ["#2196F3"] * len(df)
    # 疫情年份標紅
    for i, year in enumerate(df["year"]):
        if year in [2020, 2021, 2022]:
            colors[i] = "#FF5252"

    bars = ax.bar(df["year"], df["total_outbound_trips"] / 10000, color=colors, width=0.7)

    # 加上數字標籤
    for bar, val in zip(bars, df["total_outbound_trips"]):
        if pd.notna(val):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20,
                    f"{val / 10000:.0f}萬", ha="center", va="bottom", fontsize=9)

    ax.set_title("歷年國人出國人次趨勢", fontsize=18, fontweight="bold", pad=15)
    ax.set_xlabel("年份", fontsize=13)
    ax.set_ylabel("出國人次（萬）", fontsize=13)
    ax.set_xticks(df["year"])
    ax.set_xticklabels(df["year"], rotation=45)

    # 加上疫情標註
    ax.annotate("COVID-19\n疫情期間", xy=(2021, 36), fontsize=11,
                ha="center", color="#FF5252", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFEBEE", edgecolor="#FF5252"))

    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "01_outbound_trend.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ 儲存: {path}")


# ============================================================
#  圖表 2：每人每次平均消費支出變化
# ============================================================
def plot_spending_trend(df):
    # 過濾掉疫情缺值年份
    df_valid = df[df["avg_spending_twd"].notna()].copy()

    fig, ax1 = plt.subplots(figsize=(12, 6))

    # 台幣（長條圖）
    bars = ax1.bar(df_valid["year"], df_valid["avg_spending_twd"],
                   color="#4CAF50", alpha=0.7, width=0.6, label="新台幣（元）")
    ax1.set_ylabel("平均消費（新台幣 元）", fontsize=13, color="#4CAF50")
    ax1.tick_params(axis="y", labelcolor="#4CAF50")

    # 美金（折線圖，右軸）
    ax2 = ax1.twinx()
    ax2.plot(df_valid["year"], df_valid["avg_spending_usd"],
             color="#FF9800", marker="o", linewidth=2.5, markersize=8, label="美金（元）")
    ax2.set_ylabel("平均消費（美金 元）", fontsize=13, color="#FF9800")
    ax2.tick_params(axis="y", labelcolor="#FF9800")

    # 標註 2023 年數值
    last = df_valid.iloc[-1]
    ax1.annotate(f"NT${last['avg_spending_twd']:,.0f}",
                 xy=(last["year"], last["avg_spending_twd"]),
                 xytext=(last["year"] - 1.5, last["avg_spending_twd"] + 3000),
                 fontsize=11, fontweight="bold", color="#2E7D32",
                 arrowprops=dict(arrowstyle="->", color="#2E7D32"))

    ax1.set_title("歷年國人出國每人每次平均消費支出", fontsize=18, fontweight="bold", pad=15)
    ax1.set_xlabel("年份", fontsize=13)
    ax1.set_xticks(df_valid["year"])
    ax1.set_xticklabels(df_valid["year"].astype(int), rotation=45)
    ax1.grid(axis="y", alpha=0.3)
    ax1.spines["top"].set_visible(False)

    # 合併圖例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=11)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "02_spending_trend.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ 儲存: {path}")


# ============================================================
#  圖表 3：出國消費總支出趨勢
# ============================================================
def plot_total_spending(df):
    df_valid = df[df["total_spending_twd_100m"].notna()].copy()

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.fill_between(df_valid["year"], df_valid["total_spending_twd_100m"],
                    alpha=0.3, color="#9C27B0")
    ax.plot(df_valid["year"], df_valid["total_spending_twd_100m"],
            color="#9C27B0", marker="o", linewidth=2.5, markersize=8)

    for _, row in df_valid.iterrows():
        ax.text(row["year"], row["total_spending_twd_100m"] + 100,
                f"{row['total_spending_twd_100m']:,.0f}億", ha="center", fontsize=9)

    ax.set_title("歷年國人出國旅遊消費總支出（含國際機票）", fontsize=18, fontweight="bold", pad=15)
    ax.set_xlabel("年份", fontsize=13)
    ax.set_ylabel("消費總支出（新台幣 億元）", fontsize=13)
    ax.set_xticks(df_valid["year"])
    ax.set_xticklabels(df_valid["year"].astype(int), rotation=45)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "03_total_spending.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ 儲存: {path}")


# ============================================================
#  圖表 4：平均停留夜數變化
# ============================================================
def plot_stay_nights(df):
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ["#00BCD4" if y not in [2020, 2021, 2022] else "#FF5252" for y in df["year"]]
    ax.bar(df["year"], df["avg_stay_nights"], color=colors, width=0.6)

    for _, row in df.iterrows():
        if pd.notna(row["avg_stay_nights"]):
            ax.text(row["year"], row["avg_stay_nights"] + 0.3,
                    f"{row['avg_stay_nights']:.1f}", ha="center", fontsize=9)

    ax.set_title("歷年國人出國平均停留夜數", fontsize=18, fontweight="bold", pad=15)
    ax.set_xlabel("年份", fontsize=13)
    ax.set_ylabel("平均停留夜數（晚）", fontsize=13)
    ax.set_xticks(df["year"])
    ax.set_xticklabels(df["year"], rotation=45)

    # 標註疫情影響
    ax.annotate("疫情期間\n出國者多為長期居留",
                xy=(2021, 32.19), xytext=(2017, 28),
                fontsize=10, color="#FF5252",
                arrowprops=dict(arrowstyle="->", color="#FF5252"),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFEBEE", edgecolor="#FF5252"))

    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "04_stay_nights.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ 儲存: {path}")


# ============================================================
#  圖表 5：關鍵發現摘要
# ============================================================
def print_key_findings(df):
    df_valid = df[df["avg_spending_twd"].notna()]

    print("\n" + "=" * 50)
    print("📊 關鍵發現 Key Findings")
    print("=" * 50)

    # 出國人次高峰
    peak = df.loc[df["total_outbound_trips"].idxmax()]
    print(f"\n1️⃣  出國人次高峰: {int(peak['year'])} 年 {peak['total_outbound_trips']:,.0f} 人次")

    # 疫情衝擊
    pre_covid = df[df["year"] == 2019]["total_outbound_trips"].values[0]
    covid_low = df[df["year"] == 2021]["total_outbound_trips"].values[0]
    drop_pct = (1 - covid_low / pre_covid) * 100
    print(f"2️⃣  疫情衝擊: 2021 年出國人次僅 {covid_low:,.0f}，較 2019 年下降 {drop_pct:.1f}%")

    # 復甦狀況
    recovery = df[df["year"] == 2023]["total_outbound_trips"].values[0]
    recovery_pct = recovery / pre_covid * 100
    print(f"3️⃣  2023 復甦: {recovery:,.0f} 人次，恢復至疫前 {recovery_pct:.1f}%")

    # 消費成長
    first_spend = df_valid.iloc[0]["avg_spending_twd"]
    last_spend = df_valid.iloc[-1]["avg_spending_twd"]
    spend_growth = (last_spend / first_spend - 1) * 100
    print(f"4️⃣  每人平均消費: NT${first_spend:,.0f}({int(df_valid.iloc[0]['year'])}) → NT${last_spend:,.0f}({int(df_valid.iloc[-1]['year'])}), 成長 {spend_growth:.1f}%")

    # 停留天數趨勢
    normal_nights = df[(df["year"] >= 2013) & (df["year"] <= 2019)]["avg_stay_nights"]
    print(f"5️⃣  疫前平均停留: {normal_nights.mean():.1f} 晚（逐年縮短趨勢，短天數旅行增加）")

    print("\n" + "=" * 50)


# ============================================================
#  主程式
# ============================================================
if __name__ == "__main__":
    print("🧳 TravelWallet - 政府開放資料 EDA")
    print("=" * 40)

    df = load_data()

    print("\n📈 產生圖表...")
    plot_outbound_trend(df)
    plot_spending_trend(df)
    plot_total_spending(df)
    plot_stay_nights(df)

    print_key_findings(df)

    print(f"\n🎉 EDA 完成！圖表已儲存至 docs/demo_screenshots/")

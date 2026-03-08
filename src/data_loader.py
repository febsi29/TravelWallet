"""
- 載入政府開放資料CSV
- 資料清洗（民國年轉西元、移除逗號空格、處理缺值）
- 匯入 SQLite
"""

import pandas as pd
import sqlite3
import os
from contextlib import closing


# === 路徑設定 ===

# 自動偵測專案根目錄（從 src/ 往上一層）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")


# === 工具函式 ===

def clean_number(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s == "-" or s == "":
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def roc_to_ad(roc_year):
    try:
        return int(roc_year) + 1911
    except (ValueError, TypeError):
        return None


# === 核心載入函式 ===

def load_outbound_stats(filepath=None):
    """
    載入並清洗「歷年國人出國旅遊重要指標統計表」

    Returns:
        pd.DataFrame: 清洗後的資料
    """
    if filepath is None:
        filepath = os.path.join(RAW_DIR, "tw_outbound_stats.csv")

    print(f" 載入: {filepath}")

    # 讀取 CSV
    df = pd.read_csv(filepath, encoding="utf-8")

    # 過濾掉註記行（年度欄位為空的行）
    df = df[df["年度"].notna()].copy()
    df = df[df["年度"].apply(lambda x: pd.notna(x) and str(x).replace(".", "").strip().isdigit())].copy()

    # 民國年轉西元年
    df["year"] = df["年度"].apply(roc_to_ad)

    # 清洗數字欄位
    df["total_outbound_trips"] = df["國人出國總人次"].apply(clean_number)
    df["avg_stay_nights"] = df["平均停留夜數"].apply(clean_number)
    df["avg_spending_twd"] = df["每人每次平均消費支出_新台幣_元"].apply(clean_number)
    df["avg_spending_usd"] = df["每人每次平均消費支出_美金_元"].apply(clean_number)
    df["total_spending_twd_100m"] = df["出國旅遊消費總支出_含國際機票_新台幣_億元"].apply(clean_number)
    df["total_spending_usd_100m"] = df["出國旅遊消費總支出_含國際機票_美金_億元"].apply(clean_number)

    # 只保留需要的欄位
    result = df[[
        "year",
        "total_outbound_trips",
        "avg_stay_nights",
        "avg_spending_twd",
        "avg_spending_usd",
        "total_spending_twd_100m",
        "total_spending_usd_100m"
    ]].copy()

    # 轉換型別
    result["year"] = result["year"].astype(int)
    result["total_outbound_trips"] = result["total_outbound_trips"].astype("Int64")

    print(f"載入完成: {len(result)} 筆資料 ({result['year'].min()}~{result['year'].max()})")
    return result


def save_processed_csv(df, filename="cleaned_outbound_stats.csv"):
    """
    儲存清洗後的資料為 CSV
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    filepath = os.path.join(PROCESSED_DIR, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"已儲存: {filepath}")


# === 資料庫操作 ===

def init_database():
    """
    根據 schema.sql 初始化資料庫
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    print(f"資料庫初始化完成: {DB_PATH}")


def load_to_database(df):
    """
    將清洗後的政府資料匯入 SQLite 的 gov_outbound_stats 表（使用參數化查詢）
    """
    inserted = 0
    skipped = 0

    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO gov_outbound_stats
                    (year, total_outbound_trips, avg_stay_nights,
                     avg_spending_twd, avg_spending_usd,
                     total_spending_twd_100m, total_spending_usd_100m)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(row["year"]),
                    int(row["total_outbound_trips"]) if pd.notna(row["total_outbound_trips"]) else None,
                    float(row["avg_stay_nights"]) if pd.notna(row["avg_stay_nights"]) else None,
                    float(row["avg_spending_twd"]) if pd.notna(row["avg_spending_twd"]) else None,
                    float(row["avg_spending_usd"]) if pd.notna(row["avg_spending_usd"]) else None,
                    float(row["total_spending_twd_100m"]) if pd.notna(row["total_spending_twd_100m"]) else None,
                    float(row["total_spending_usd_100m"]) if pd.notna(row["total_spending_usd_100m"]) else None,
                ))
                inserted += 1
            except sqlite3.Error as e:
                print(f"跳過 {row['year']}: {e}")
                skipped += 1
        conn.commit()

    print(f"匯入資料庫完成: {inserted} 筆成功, {skipped} 筆跳過")


def verify_database():
    """
    驗證資料庫內容
    """
    with closing(sqlite3.connect(DB_PATH)) as conn:
        df = pd.read_sql_query("SELECT * FROM gov_outbound_stats ORDER BY year", conn)

    print(f"\n資料庫驗證 — gov_outbound_stats ({len(df)} 筆)")
    print("=" * 70)
    print(df.to_string(index=False))
    print("=" * 70)
    return df


# === 主程式 ===

if __name__ == "__main__":
    print("TravelWallet - 資料載入程式")
    print("=" * 40)

    # Step 1: 初始化資料庫
    init_database()

    # Step 2: 載入並清洗 CSV
    df = load_outbound_stats()

    # Step 3: 儲存清洗後的 CSV
    save_processed_csv(df)

    # Step 4: 匯入資料庫
    load_to_database(df)

    # Step 5: 驗證
    verify_database()

    print("\n資料載入流程完成！")

"""
- CSV
- 
-  SQLite
"""

import pandas as pd
import sqlite3
import os
from contextlib import closing


# ===  ===

#  src/ 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")


# ===  ===

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


# ===  ===

def load_outbound_stats(filepath=None):
    """
    

    Returns:
        pd.DataFrame: 
    """
    if filepath is None:
        filepath = os.path.join(RAW_DIR, "tw_outbound_stats.csv")

    print(f" : {filepath}")

    #  CSV
    df = pd.read_csv(filepath, encoding="utf-8")

    # 
    df = df[df[""].notna()].copy()
    df = df[df[""].apply(lambda x: pd.notna(x) and str(x).replace(".", "").strip().isdigit())].copy()

    # 
    df["year"] = df[""].apply(roc_to_ad)

    # 
    df["total_outbound_trips"] = df[""].apply(clean_number)
    df["avg_stay_nights"] = df[""].apply(clean_number)
    df["avg_spending_twd"] = df["__"].apply(clean_number)
    df["avg_spending_usd"] = df["__"].apply(clean_number)
    df["total_spending_twd_100m"] = df["___"].apply(clean_number)
    df["total_spending_usd_100m"] = df["___"].apply(clean_number)

    # 
    result = df[[
        "year",
        "total_outbound_trips",
        "avg_stay_nights",
        "avg_spending_twd",
        "avg_spending_usd",
        "total_spending_twd_100m",
        "total_spending_usd_100m"
    ]].copy()

    # 
    result["year"] = result["year"].astype(int)
    result["total_outbound_trips"] = result["total_outbound_trips"].astype("Int64")

    print(f": {len(result)}  ({result['year'].min()}~{result['year'].max()})")
    return result


def save_processed_csv(df, filename="cleaned_outbound_stats.csv"):
    """
     CSV
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    filepath = os.path.join(PROCESSED_DIR, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f": {filepath}")


# ===  ===

def init_database():
    """
     schema.sql 
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    print(f": {DB_PATH}")


def load_to_database(df):
    """
     SQLite  gov_outbound_stats 
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
                print(f" {row['year']}: {e}")
                skipped += 1
        conn.commit()

    print(f": {inserted} , {skipped} ")


def verify_database():
    """
    
    """
    with closing(sqlite3.connect(DB_PATH)) as conn:
        df = pd.read_sql_query("SELECT * FROM gov_outbound_stats ORDER BY year", conn)

    print(f"\n — gov_outbound_stats ({len(df)} )")
    print("=" * 70)
    print(df.to_string(index=False))
    print("=" * 70)
    return df


# ===  ===

if __name__ == "__main__":
    print("TravelWallet - ")
    print("=" * 40)

    # Step 1: 
    init_database()

    # Step 2:  CSV
    df = load_outbound_stats()

    # Step 3:  CSV
    save_processed_csv(df)

    # Step 4: 
    load_to_database(df)

    # Step 5: 
    verify_database()

    print("\n")

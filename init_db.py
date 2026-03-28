# -*- coding: utf-8 -*-
"""
資料庫初始化腳本。
部署時執行此腳本以建立資料表結構並套用遷移。
執行方式：python init_db.py
"""

import sqlite3
import sys
from pathlib import Path

from config import settings

# 資料庫相關 SQL 檔案路徑
_BASE_DIR = Path(__file__).parent
_SCHEMA_PATH = _BASE_DIR / "database" / "schema.sql"
_MIGRATION_001_PATH = _BASE_DIR / "database" / "migration_001_line.sql"


def _read_sql_file(path: Path) -> str:
    """讀取 SQL 檔案內容，若檔案不存在則拋出錯誤。"""
    if not path.exists():
        raise FileNotFoundError(f"找不到 SQL 檔案：{path}")
    return path.read_text(encoding="utf-8")


def _execute_schema(conn: sqlite3.Connection, sql: str) -> None:
    """執行 schema SQL（允許多個陳述式）。"""
    conn.executescript(sql)
    conn.commit()
    print("schema.sql 執行完成。")


def _execute_migration(conn: sqlite3.Connection, sql: str, migration_name: str) -> None:
    """
    逐條執行遷移 SQL 陳述式。
    遇到 "duplicate column name" 錯誤時忽略（代表欄位已存在）。
    """
    # 過濾空白行與純註解行，逐條執行
    statements = [
        stmt.strip()
        for stmt in sql.split(";")
        if stmt.strip() and not stmt.strip().startswith("--")
    ]

    for stmt in statements:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as exc:
            error_msg = str(exc).lower()
            if "duplicate column name" in error_msg:
                print(f"略過（欄位已存在）：{stmt[:60]}...")
            else:
                raise

    conn.commit()
    print(f"{migration_name} 執行完成。")


def init_database() -> None:
    """建立資料庫目錄（若不存在）、執行 schema 與遷移腳本。"""
    db_path = Path(settings.DB_PATH)

    # 確保資料庫目錄存在
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"資料庫路徑：{db_path}")

    with sqlite3.connect(str(db_path)) as conn:
        # 執行主 schema
        schema_sql = _read_sql_file(_SCHEMA_PATH)
        _execute_schema(conn, schema_sql)

        # 執行 LINE 相關遷移
        migration_sql = _read_sql_file(_MIGRATION_001_PATH)
        _execute_migration(conn, migration_sql, "migration_001_line.sql")

    print("資料庫初始化完成。")


if __name__ == "__main__":
    try:
        init_database()
    except FileNotFoundError as exc:
        print(f"檔案錯誤：{exc}", file=sys.stderr)
        sys.exit(1)
    except sqlite3.Error as exc:
        print(f"資料庫錯誤：{exc}", file=sys.stderr)
        sys.exit(1)

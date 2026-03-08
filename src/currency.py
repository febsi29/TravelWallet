"""
currency.py - 匯率處理模組

功能：
- 串接 ExchangeRate-API 取得即時匯率
- 歷史匯率查詢與儲存
- 幣別換算（原幣 ↔ TWD）
- 常用幣別管理

使用方式：
  from src.currency import CurrencyManager
  cm = CurrencyManager(db_path)
  rate = cm.get_rate("JPY")
  twd = cm.convert(10000, "JPY", "TWD")
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# API Key 必須透過環境變數設定，絕不在程式碼中硬編碼
API_KEY = os.environ.get("EXCHANGE_RATE_API_KEY", "")
API_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD" if API_KEY else ""

# 台灣人常去的旅遊目的地幣別
COMMON_CURRENCIES = {
    "JPY": {"name": "日圓", "symbol": "¥", "country": "日本"},
    "USD": {"name": "美元", "symbol": "$", "country": "美國"},
    "KRW": {"name": "韓元", "symbol": "₩", "country": "韓國"},
    "THB": {"name": "泰銖", "symbol": "฿", "country": "泰國"},
    "VND": {"name": "越南盾", "symbol": "₫", "country": "越南"},
    "SGD": {"name": "新加坡幣", "symbol": "S$", "country": "新加坡"},
    "MYR": {"name": "馬來幣", "symbol": "RM", "country": "馬來西亞"},
    "HKD": {"name": "港幣", "symbol": "HK$", "country": "香港"},
    "EUR": {"name": "歐元", "symbol": "€", "country": "歐洲"},
    "GBP": {"name": "英鎊", "symbol": "£", "country": "英國"},
    "AUD": {"name": "澳幣", "symbol": "A$", "country": "澳洲"},
    "CNY": {"name": "人民幣", "symbol": "¥", "country": "中國"},
}

# 備用匯率（當 API 無法使用時的離線模式）
# 以 1 TWD 可以換多少外幣為基準（2024 年底約略值）
FALLBACK_RATES = {
    "JPY": 4.61,    # 1 TWD ≈ 4.61 JPY
    "USD": 0.031,   # 1 TWD ≈ 0.031 USD
    "KRW": 43.5,    # 1 TWD ≈ 43.5 KRW
    "THB": 1.07,    # 1 TWD ≈ 1.07 THB
    "VND": 780.0,   # 1 TWD ≈ 780 VND
    "SGD": 0.042,   # 1 TWD ≈ 0.042 SGD
    "MYR": 0.138,   # 1 TWD ≈ 0.138 MYR
    "HKD": 0.241,   # 1 TWD ≈ 0.241 HKD
    "EUR": 0.029,   # 1 TWD ≈ 0.029 EUR
    "GBP": 0.025,   # 1 TWD ≈ 0.025 GBP
    "AUD": 0.049,   # 1 TWD ≈ 0.049 AUD
    "CNY": 0.224,   # 1 TWD ≈ 0.224 CNY
}


class CurrencyManager:
    """匯率管理模組"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn, conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ============================================================
    #  即時匯率
    # ============================================================

    def fetch_live_rates(self) -> dict | None:
        """
        從 ExchangeRate-API 取得即時匯率（以 TWD 為基準）

        回傳：
            dict: {幣別代碼: 匯率}，匯率含義：1 TWD 可以換多少外幣
        """
        if not API_KEY:
            print("未設定 EXCHANGE_RATE_API_KEY 環境變數，使用離線匯率")
            return None

        try:
            import requests
            response = requests.get(API_URL, timeout=10)
            data = response.json()

            if data.get("result") == "success":
                usd_rates = data["conversion_rates"]
                twd_per_usd = usd_rates.get("TWD", 32.0)
                rates = {}
                for code in COMMON_CURRENCIES:
                    if code in usd_rates:
                        rates[code] = round(usd_rates[code] / twd_per_usd, 6)
                print(f"取得即時匯率: {len(rates)} 個幣別 (1 USD = {twd_per_usd} TWD)")
                return rates
            else:
                print(f"API 回傳錯誤: {data.get('error-type', 'unknown')}")
                return None

        except ImportError:
            print("未安裝 requests 套件，使用離線匯率")
            return None
        except Exception as e:
            print(f"API 連線失敗: {e}")
            return None

    def get_rate(self, target_currency: str, use_date: str = None) -> float:
        """
        取得 TWD 對某幣別的匯率

        優先順序：
        1. 資料庫中該日期的匯率
        2. 即時 API 匯率
        3. 備用離線匯率

        參數：
            target_currency: 目標幣別，例如 "JPY"
            use_date: 指定日期（預設今天）

        回傳：
            float: 匯率（1 TWD = ? 外幣）
        """
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency 必須為非空字串，收到: {target_currency!r}")

        target_currency = target_currency.upper()
        if use_date is None:
            use_date = date.today().isoformat()

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT rate FROM exchange_rates
                WHERE target_currency = ? AND recorded_date = ?
            """, (target_currency, use_date))
            row = cursor.fetchone()

        if row:
            return row[0]

        rates = self.fetch_live_rates()
        if rates and target_currency in rates:
            rate = rates[target_currency]
            self.save_rate(target_currency, rate, use_date)
            return rate

        if target_currency in FALLBACK_RATES:
            print(f"使用備用匯率: 1 TWD = {FALLBACK_RATES[target_currency]} {target_currency}")
            return FALLBACK_RATES[target_currency]

        raise ValueError(f"找不到 {target_currency} 的匯率")

    # ============================================================
    #  幣別換算
    # ============================================================

    def convert(self, amount: float, from_currency: str, to_currency: str, rate: float = None) -> dict:
        """
        幣別換算

        參數：
            amount: 金額
            from_currency: 來源幣別
            to_currency: 目標幣別
            rate: 自訂匯率（不指定則自動取得）

        回傳：
            dict: {"amount": 換算後金額, "rate": 使用的匯率}
        """
        if amount < 0:
            raise ValueError(f"amount 不可為負數，收到: {amount}")
        if not from_currency or not isinstance(from_currency, str):
            raise ValueError(f"from_currency 必須為非空字串，收到: {from_currency!r}")
        if not to_currency or not isinstance(to_currency, str):
            raise ValueError(f"to_currency 必須為非空字串，收到: {to_currency!r}")

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return {"amount": amount, "rate": 1.0}

        if rate is not None:
            return {"amount": round(amount * rate, 2), "rate": rate}

        if from_currency == "TWD":
            r = self.get_rate(to_currency)
            return {"amount": round(amount * r, 2), "rate": r}
        elif to_currency == "TWD":
            r = self.get_rate(from_currency)
            return {"amount": round(amount / r, 2), "rate": round(1 / r, 6)}
        else:
            r_from = self.get_rate(from_currency)
            r_to = self.get_rate(to_currency)
            twd_amount = amount / r_from
            return {"amount": round(twd_amount * r_to, 2), "rate": round(r_to / r_from, 6)}

    def quick_convert(self, amount: float, from_currency: str, to_currency: str = "TWD") -> float:
        """快速換算，只回傳金額"""
        return self.convert(amount, from_currency, to_currency)["amount"]

    # ============================================================
    #  匯率儲存與歷史查詢
    # ============================================================

    def save_rate(self, target_currency: str, rate: float, recorded_date: str = None) -> None:
        """儲存匯率到資料庫"""
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency 必須為非空字串，收到: {target_currency!r}")
        if rate <= 0:
            raise ValueError(f"rate 必須大於 0，收到: {rate}")

        if recorded_date is None:
            recorded_date = date.today().isoformat()

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT OR REPLACE INTO exchange_rates
                (base_currency, target_currency, rate, recorded_date, source)
                VALUES ('TWD', ?, ?, ?, 'ExchangeRate-API')
            """, (target_currency, rate, recorded_date))

    def save_all_rates(self, rates: dict, recorded_date: str = None) -> None:
        """批次儲存多個幣別的匯率"""
        for currency, rate in rates.items():
            self.save_rate(currency, rate, recorded_date)
        print(f"儲存 {len(rates)} 個幣別匯率")

    def get_rate_history(self, target_currency: str, days: int = 30) -> list:
        """查詢某幣別的歷史匯率"""
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency 必須為非空字串，收到: {target_currency!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days 必須為正整數，收到: {days!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT recorded_date, rate
                FROM exchange_rates
                WHERE target_currency = ?
                ORDER BY recorded_date DESC
                LIMIT ?
            """, (target_currency, days))
            rows = cursor.fetchall()

        return [{"date": r[0], "rate": r[1]} for r in reversed(rows)]

    # ============================================================
    #  工具函式
    # ============================================================

    def get_currency_info(self, currency_code: str) -> dict:
        """取得幣別的中文名稱、符號等資訊"""
        code = currency_code.upper()
        return COMMON_CURRENCIES.get(code, {"name": code, "symbol": code, "country": "未知"})

    def format_amount(self, amount: float, currency_code: str) -> str:
        """格式化金額顯示"""
        info = self.get_currency_info(currency_code)
        if currency_code.upper() == "TWD":
            return f"NT${amount:,.0f}"
        return f"{info['symbol']}{amount:,.0f}"

    def list_currencies(self) -> dict:
        """列出所有支援的幣別"""
        return COMMON_CURRENCIES.copy()


if __name__ == "__main__":
    print("TravelWallet - 匯率模組測試")
    print("=" * 50)

    cm = CurrencyManager()

    print("\n支援幣別:")
    for code, info in COMMON_CURRENCIES.items():
        print(f"  {info['symbol']} {code} - {info['name']} ({info['country']})")

    print("\n匯率查詢（備用離線匯率）:")
    for code in ["JPY", "USD", "KRW", "THB", "EUR"]:
        rate = cm.get_rate(code)
        info = cm.get_currency_info(code)
        twd_per_unit = round(1 / rate, 2)
        print(f"  {info['name']}({code}): 1 TWD = {rate} {code} | 1 {code} = NT${twd_per_unit}")

    print("\n幣別換算範例:")
    result = cm.convert(10000, "JPY", "TWD")
    print(f"  10,000 JPY = NT${result['amount']:,.0f}")
    result = cm.convert(5000, "TWD", "JPY")
    print(f"  NT$5,000 = {result['amount']:,.0f} JPY")

    cm.save_all_rates(FALLBACK_RATES)
    print("\nDone!")

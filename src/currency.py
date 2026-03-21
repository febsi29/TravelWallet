"""
currency.py - 


-  ExchangeRate-API 
- 
-  ↔ TWD
- 


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

# API Key 
API_KEY = os.environ.get("EXCHANGE_RATE_API_KEY", "")
API_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD" if API_KEY else ""

# 
COMMON_CURRENCIES = {
    "JPY": {"name": "", "symbol": "¥", "country": ""},
    "USD": {"name": "", "symbol": "$", "country": ""},
    "KRW": {"name": "", "symbol": "₩", "country": ""},
    "THB": {"name": "", "symbol": "฿", "country": ""},
    "VND": {"name": "", "symbol": "₫", "country": ""},
    "SGD": {"name": "", "symbol": "S$", "country": ""},
    "MYR": {"name": "", "symbol": "RM", "country": ""},
    "HKD": {"name": "", "symbol": "HK$", "country": ""},
    "EUR": {"name": "", "symbol": "€", "country": ""},
    "GBP": {"name": "", "symbol": "£", "country": ""},
    "AUD": {"name": "", "symbol": "A$", "country": ""},
    "CNY": {"name": "", "symbol": "¥", "country": ""},
}

#  API 
#  1 TWD 2024 
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
    """"""

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
    #  
    # ============================================================

    def fetch_live_rates(self) -> dict | None:
        """
         ExchangeRate-API  TWD 

        
            dict: {: }1 TWD 
        """
        if not API_KEY:
            print(" EXCHANGE_RATE_API_KEY ")
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
                print(f": {len(rates)}  (1 USD = {twd_per_usd} TWD)")
                return rates
            else:
                print(f"API : {data.get('error-type', 'unknown')}")
                return None

        except ImportError:
            print(" requests ")
            return None
        except Exception as e:
            print(f"API : {e}")
            return None

    def get_rate(self, target_currency: str, use_date: str = None) -> float:
        """
         TWD 

        
        1. 
        2.  API 
        3. 

        
            target_currency:  "JPY"
            use_date: 

        
            float: 1 TWD = ? 
        """
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency : {target_currency!r}")

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
            print(f": 1 TWD = {FALLBACK_RATES[target_currency]} {target_currency}")
            return FALLBACK_RATES[target_currency]

        raise ValueError(f" {target_currency} ")

    # ============================================================
    #  
    # ============================================================

    def convert(self, amount: float, from_currency: str, to_currency: str, rate: float = None) -> dict:
        """
        

        
            amount: 
            from_currency: 
            to_currency: 
            rate: 

        
            dict: {"amount": , "rate": }
        """
        if amount < 0:
            raise ValueError(f"amount : {amount}")
        if not from_currency or not isinstance(from_currency, str):
            raise ValueError(f"from_currency : {from_currency!r}")
        if not to_currency or not isinstance(to_currency, str):
            raise ValueError(f"to_currency : {to_currency!r}")

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
        """"""
        return self.convert(amount, from_currency, to_currency)["amount"]

    # ============================================================
    #  
    # ============================================================

    def save_rate(self, target_currency: str, rate: float, recorded_date: str = None) -> None:
        """"""
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency : {target_currency!r}")
        if rate <= 0:
            raise ValueError(f"rate  0: {rate}")

        if recorded_date is None:
            recorded_date = date.today().isoformat()

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT OR REPLACE INTO exchange_rates
                (base_currency, target_currency, rate, recorded_date, source)
                VALUES ('TWD', ?, ?, ?, 'ExchangeRate-API')
            """, (target_currency, rate, recorded_date))

    def save_all_rates(self, rates: dict, recorded_date: str = None) -> None:
        """"""
        for currency, rate in rates.items():
            self.save_rate(currency, rate, recorded_date)
        print(f" {len(rates)} ")

    def get_rate_history(self, target_currency: str, days: int = 30) -> list:
        """"""
        if not target_currency or not isinstance(target_currency, str):
            raise ValueError(f"target_currency : {target_currency!r}")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days : {days!r}")

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
    #  
    # ============================================================

    def get_currency_info(self, currency_code: str) -> dict:
        """"""
        code = currency_code.upper()
        return COMMON_CURRENCIES.get(code, {"name": code, "symbol": code, "country": ""})

    def format_amount(self, amount: float, currency_code: str) -> str:
        """"""
        info = self.get_currency_info(currency_code)
        if currency_code.upper() == "TWD":
            return f"NT${amount:,.0f}"
        return f"{info['symbol']}{amount:,.0f}"

    def list_currencies(self) -> dict:
        """"""
        return COMMON_CURRENCIES.copy()


if __name__ == "__main__":
    print("TravelWallet - ")
    print("=" * 50)

    cm = CurrencyManager()

    print("\n:")
    for code, info in COMMON_CURRENCIES.items():
        print(f"  {info['symbol']} {code} - {info['name']} ({info['country']})")

    print("\n:")
    for code in ["JPY", "USD", "KRW", "THB", "EUR"]:
        rate = cm.get_rate(code)
        info = cm.get_currency_info(code)
        twd_per_unit = round(1 / rate, 2)
        print(f"  {info['name']}({code}): 1 TWD = {rate} {code} | 1 {code} = NT${twd_per_unit}")

    print("\n:")
    result = cm.convert(10000, "JPY", "TWD")
    print(f"  10,000 JPY = NT${result['amount']:,.0f}")
    result = cm.convert(5000, "TWD", "JPY")
    print(f"  NT$5,000 = {result['amount']:,.0f} JPY")

    cm.save_all_rates(FALLBACK_RATES)
    print("\nDone!")

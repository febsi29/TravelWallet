"""
wallet.py - 多幣別電子錢包模組

功能：
- 建立並管理多幣別錢包帳戶
- 存入、提取、跨幣別轉帳
- 鎖定匯率預換功能
- 交易記錄查詢

使用方式：
  from src.wallet import WalletService
  ws = WalletService(db_path)
  ws.deposit(user_id=1, currency_code="JPY", amount=50000)
  ws.transfer(user_id=1, from_currency="TWD", to_currency="JPY", amount=10000)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

VALID_TXN_TYPES = ("deposit", "withdraw", "transfer_in", "transfer_out", "lock", "unlock")


class WalletService:
    """多幣別電子錢包服務"""

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
    #  錢包管理
    # ============================================================

    def get_or_create_wallet(self, user_id: int, currency_code: str) -> dict:
        """
        取得或建立指定幣別的錢包

        參數：
            user_id: 使用者 ID
            currency_code: 幣別代碼（例如 "JPY"）

        回傳：
            dict: 錢包資料
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not currency_code or not isinstance(currency_code, str):
            raise ValueError(f"currency_code 必須為非空字串，收到: {currency_code!r}")

        currency_code = currency_code.upper()

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT OR IGNORE INTO wallets (user_id, currency_code, balance, locked_balance)
                VALUES (?, ?, 0, 0)
            """, (user_id, currency_code))

            cursor.execute("""
                SELECT wallet_id, user_id, currency_code, balance, locked_balance, created_at
                FROM wallets WHERE user_id = ? AND currency_code = ?
            """, (user_id, currency_code))
            row = cursor.fetchone()

        return self._wallet_row_to_dict(row)

    def get_all_wallets(self, user_id: int) -> list:
        """
        取得使用者所有幣別的錢包

        參數：
            user_id: 使用者 ID

        回傳：
            list[dict]: 錢包列表，依幣別代碼排序
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT wallet_id, user_id, currency_code, balance, locked_balance, created_at
                FROM wallets WHERE user_id = ?
                ORDER BY currency_code
            """, (user_id,))
            rows = cursor.fetchall()

        return [self._wallet_row_to_dict(r) for r in rows]

    def get_total_balance_twd(self, user_id: int) -> dict:
        """
        計算使用者所有錢包的台幣總資產

        參數：
            user_id: 使用者 ID

        回傳：
            dict: {"total_twd": float, "breakdown": [{currency, balance, balance_twd}, ...]}
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        wallets = self.get_all_wallets(user_id)

        try:
            from src.currency import CurrencyManager, FALLBACK_RATES
            cm = CurrencyManager(self.db_path)
        except ImportError:
            cm = None

        breakdown = []
        total_twd = 0.0

        for w in wallets:
            currency = w["currency_code"]
            balance = w["balance"]

            if currency == "TWD":
                balance_twd = balance
            elif cm:
                try:
                    rate = cm.get_rate(currency)
                    balance_twd = round(balance / rate, 2) if rate > 0 else 0
                except Exception:
                    balance_twd = 0.0
            else:
                balance_twd = 0.0

            total_twd += balance_twd
            breakdown.append({
                "currency": currency,
                "balance": balance,
                "balance_twd": round(balance_twd, 2),
            })

        return {"total_twd": round(total_twd, 2), "breakdown": breakdown}

    def _wallet_row_to_dict(self, row: tuple) -> dict:
        keys = ["wallet_id", "user_id", "currency_code", "balance", "locked_balance", "created_at"]
        return dict(zip(keys, row))

    # ============================================================
    #  存入 / 提取
    # ============================================================

    def deposit(self, user_id: int, currency_code: str, amount: float, note: str = None) -> dict:
        """
        存入金額至錢包

        參數：
            user_id: 使用者 ID
            currency_code: 幣別代碼
            amount: 存入金額（必須大於 0）
            note: 備註

        回傳：
            dict: 更新後的錢包資料
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError(f"amount 必須大於 0，收到: {amount!r}")

        wallet = self.get_or_create_wallet(user_id, currency_code)
        wallet_id = wallet["wallet_id"]

        with self._db() as (conn, cursor):
            cursor.execute(
                "UPDATE wallets SET balance = balance + ? WHERE wallet_id = ?",
                (float(amount), wallet_id)
            )
            cursor.execute("""
                INSERT INTO wallet_transactions
                (wallet_id, txn_type, amount, currency_code, note)
                VALUES (?, 'deposit', ?, ?, ?)
            """, (wallet_id, float(amount), currency_code.upper(), note))

        return self.get_or_create_wallet(user_id, currency_code)

    def withdraw(self, user_id: int, currency_code: str, amount: float, note: str = None) -> dict:
        """
        從錢包提取金額

        參數：
            user_id: 使用者 ID
            currency_code: 幣別代碼
            amount: 提取金額（必須大於 0）
            note: 備註

        回傳：
            dict: 更新後的錢包資料

        例外：
            ValueError: 餘額不足時拋出
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError(f"amount 必須大於 0，收到: {amount!r}")

        wallet = self.get_or_create_wallet(user_id, currency_code)
        if wallet["balance"] < amount:
            raise ValueError(
                f"餘額不足：目前 {wallet['balance']} {currency_code}，"
                f"嘗試提取 {amount} {currency_code}"
            )

        wallet_id = wallet["wallet_id"]

        with self._db() as (conn, cursor):
            cursor.execute(
                "UPDATE wallets SET balance = balance - ? WHERE wallet_id = ?",
                (float(amount), wallet_id)
            )
            cursor.execute("""
                INSERT INTO wallet_transactions
                (wallet_id, txn_type, amount, currency_code, note)
                VALUES (?, 'withdraw', ?, ?, ?)
            """, (wallet_id, float(amount), currency_code.upper(), note))

        return self.get_or_create_wallet(user_id, currency_code)

    # ============================================================
    #  跨幣別轉帳
    # ============================================================

    def transfer(
        self,
        user_id: int,
        from_currency: str,
        to_currency: str,
        amount: float,
        locked_rate: float = None,
    ) -> dict:
        """
        跨幣別轉帳

        參數：
            user_id: 使用者 ID
            from_currency: 來源幣別
            to_currency: 目標幣別
            amount: 轉帳金額（來源幣別）
            locked_rate: 鎖定匯率（None 則使用即時匯率）

        回傳：
            dict: {"from_wallet", "to_wallet", "rate", "converted_amount"}
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError(f"amount 必須大於 0，收到: {amount!r}")
        if not from_currency or not to_currency:
            raise ValueError("來源幣別和目標幣別不可為空")

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        from_wallet = self.get_or_create_wallet(user_id, from_currency)
        if from_wallet["balance"] < amount:
            raise ValueError(
                f"餘額不足：目前 {from_wallet['balance']} {from_currency}，"
                f"嘗試轉出 {amount} {from_currency}"
            )

        # 計算換算金額
        if from_currency == to_currency:
            converted_amount = amount
            rate = 1.0
        elif locked_rate is not None:
            if locked_rate <= 0:
                raise ValueError(f"locked_rate 必須大於 0，收到: {locked_rate!r}")
            converted_amount = round(amount * locked_rate, 2)
            rate = locked_rate
        else:
            try:
                from src.currency import CurrencyManager
                cm = CurrencyManager(self.db_path)
                result = cm.convert(amount, from_currency, to_currency)
                converted_amount = result["amount"]
                rate = result["rate"]
            except Exception:
                raise ValueError(f"無法取得 {from_currency} → {to_currency} 的匯率")

        from_wallet_id = from_wallet["wallet_id"]
        to_wallet = self.get_or_create_wallet(user_id, to_currency)
        to_wallet_id = to_wallet["wallet_id"]

        with self._db() as (conn, cursor):
            # 扣除來源錢包
            cursor.execute(
                "UPDATE wallets SET balance = balance - ? WHERE wallet_id = ?",
                (float(amount), from_wallet_id)
            )
            cursor.execute("""
                INSERT INTO wallet_transactions
                (wallet_id, txn_type, amount, currency_code, exchange_rate, locked_rate)
                VALUES (?, 'transfer_out', ?, ?, ?, ?)
            """, (from_wallet_id, float(amount), from_currency, rate, locked_rate))
            out_txn_id = cursor.lastrowid

            # 增加目標錢包
            cursor.execute(
                "UPDATE wallets SET balance = balance + ? WHERE wallet_id = ?",
                (float(converted_amount), to_wallet_id)
            )
            cursor.execute("""
                INSERT INTO wallet_transactions
                (wallet_id, txn_type, amount, currency_code, exchange_rate, locked_rate, related_wtxn_id)
                VALUES (?, 'transfer_in', ?, ?, ?, ?, ?)
            """, (to_wallet_id, float(converted_amount), to_currency, rate, locked_rate, out_txn_id))

        return {
            "from_wallet": self.get_or_create_wallet(user_id, from_currency),
            "to_wallet": self.get_or_create_wallet(user_id, to_currency),
            "rate": rate,
            "converted_amount": converted_amount,
        }

    # ============================================================
    #  交易紀錄
    # ============================================================

    def get_transaction_history(self, user_id: int, limit: int = 50) -> list:
        """
        查詢使用者的錢包交易紀錄

        參數：
            user_id: 使用者 ID
            limit: 最多回傳筆數

        回傳：
            list[dict]: 交易紀錄列表
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit 必須為正整數，收到: {limit!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT wt.wtxn_id, w.currency_code, wt.txn_type,
                       wt.amount, wt.exchange_rate, wt.locked_rate,
                       wt.note, wt.created_at
                FROM wallet_transactions wt
                JOIN wallets w ON wt.wallet_id = w.wallet_id
                WHERE w.user_id = ?
                ORDER BY wt.created_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

        keys = ["wtxn_id", "currency_code", "txn_type", "amount",
                "exchange_rate", "locked_rate", "note", "created_at"]
        return [dict(zip(keys, r)) for r in rows]

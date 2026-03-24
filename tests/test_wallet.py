"""
test_wallet.py - 多幣別電子錢包模組測試
"""

import pytest
from src.wallet import WalletService


class TestGetOrCreateWallet:
    def test_create_new_wallet(self, db_path):
        ws = WalletService(db_path)
        wallet = ws.get_or_create_wallet(user_id=1, currency_code="JPY")
        assert wallet["user_id"] == 1
        assert wallet["currency_code"] == "JPY"
        assert wallet["balance"] == 0.0
        assert wallet["wallet_id"] is not None

    def test_idempotent(self, db_path):
        ws = WalletService(db_path)
        w1 = ws.get_or_create_wallet(user_id=1, currency_code="TWD")
        w2 = ws.get_or_create_wallet(user_id=1, currency_code="TWD")
        assert w1["wallet_id"] == w2["wallet_id"]

    def test_invalid_user_id(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.get_or_create_wallet(user_id=0, currency_code="JPY")

    def test_invalid_currency(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.get_or_create_wallet(user_id=1, currency_code="")


class TestDeposit:
    def test_deposit_increases_balance(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="JPY", amount=10000)
        wallet = ws.get_or_create_wallet(user_id=1, currency_code="JPY")
        assert wallet["balance"] == 10000.0

    def test_multiple_deposits(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=5000)
        ws.deposit(user_id=1, currency_code="TWD", amount=3000)
        wallet = ws.get_or_create_wallet(user_id=1, currency_code="TWD")
        assert wallet["balance"] == 8000.0

    def test_deposit_invalid_amount(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.deposit(user_id=1, currency_code="JPY", amount=0)

    def test_deposit_negative_amount(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.deposit(user_id=1, currency_code="JPY", amount=-100)


class TestWithdraw:
    def test_withdraw_decreases_balance(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=2, currency_code="TWD", amount=10000)
        ws.withdraw(user_id=2, currency_code="TWD", amount=3000)
        wallet = ws.get_or_create_wallet(user_id=2, currency_code="TWD")
        assert wallet["balance"] == 7000.0

    def test_withdraw_insufficient_funds(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=2, currency_code="JPY", amount=1000)
        with pytest.raises(ValueError, match="餘額不足"):
            ws.withdraw(user_id=2, currency_code="JPY", amount=9999)

    def test_withdraw_invalid_amount(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.withdraw(user_id=1, currency_code="TWD", amount=-50)


class TestTransfer:
    def test_transfer_reduces_source(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=50000)
        ws.transfer(user_id=1, from_currency="TWD", to_currency="JPY", amount=10000)
        source = ws.get_or_create_wallet(user_id=1, currency_code="TWD")
        assert source["balance"] == 40000.0

    def test_transfer_increases_target(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=50000)
        result = ws.transfer(user_id=1, from_currency="TWD", to_currency="JPY", amount=10000)
        assert result["to_wallet"]["balance"] > 0
        assert result["converted_amount"] > 0

    def test_transfer_insufficient_funds(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError, match="餘額不足"):
            ws.transfer(user_id=3, from_currency="USD", to_currency="JPY", amount=99999)

    def test_transfer_with_locked_rate(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=50000)
        result = ws.transfer(
            user_id=1, from_currency="TWD", to_currency="JPY",
            amount=1000, locked_rate=4.5
        )
        assert result["converted_amount"] == 4500.0
        assert result["rate"] == 4.5

    def test_transfer_invalid_locked_rate(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=50000)
        with pytest.raises(ValueError):
            ws.transfer(
                user_id=1, from_currency="TWD", to_currency="JPY",
                amount=1000, locked_rate=-1.0
            )


class TestGetTotalBalanceTwd:
    def test_total_balance_structure(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=10000)
        result = ws.get_total_balance_twd(user_id=1)
        assert "total_twd" in result
        assert "breakdown" in result
        assert isinstance(result["breakdown"], list)
        assert result["total_twd"] >= 10000.0

    def test_invalid_user_id(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.get_total_balance_twd(user_id=-1)


class TestGetAllWallets:
    def test_returns_list(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="JPY", amount=5000)
        ws.deposit(user_id=1, currency_code="TWD", amount=1000)
        wallets = ws.get_all_wallets(user_id=1)
        assert isinstance(wallets, list)
        assert len(wallets) >= 2


class TestTransactionHistory:
    def test_history_returns_list(self, db_path):
        ws = WalletService(db_path)
        ws.deposit(user_id=1, currency_code="TWD", amount=5000)
        history = ws.get_transaction_history(user_id=1)
        assert isinstance(history, list)
        assert len(history) >= 1
        assert "txn_type" in history[0]

    def test_history_invalid_user_id(self, db_path):
        ws = WalletService(db_path)
        with pytest.raises(ValueError):
            ws.get_transaction_history(user_id=0)

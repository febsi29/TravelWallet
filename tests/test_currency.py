"""test_currency.py - CurrencyManager 單元測試"""

import pytest
from src.currency import CurrencyManager, FALLBACK_RATES


class TestConvert:
    def test_same_currency_returns_same_amount(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.convert(1000, "TWD", "TWD")
        assert result["amount"] == 1000
        assert result["rate"] == 1.0

    def test_twd_to_jpy_uses_fallback(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.convert(1000, "TWD", "JPY")
        expected = round(1000 * FALLBACK_RATES["JPY"], 2)
        assert result["amount"] == expected
        assert result["rate"] == FALLBACK_RATES["JPY"]

    def test_jpy_to_twd_uses_fallback(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.convert(10000, "JPY", "TWD")
        expected = round(10000 / FALLBACK_RATES["JPY"], 2)
        assert result["amount"] == expected

    def test_cross_currency_jpy_to_usd(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.convert(10000, "JPY", "USD")
        assert result["amount"] > 0
        assert result["rate"] > 0

    def test_custom_rate_overrides_lookup(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.convert(1000, "TWD", "JPY", rate=5.0)
        assert result["amount"] == 5000.0
        assert result["rate"] == 5.0

    def test_zero_amount(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.convert(0, "TWD", "JPY")
        assert result["amount"] == 0

    def test_negative_amount_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.convert(-100, "TWD", "JPY")

    def test_empty_from_currency_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.convert(100, "", "JPY")

    def test_case_insensitive(self, db_path):
        cm = CurrencyManager(db_path)
        result_upper = cm.convert(1000, "TWD", "JPY")
        result_lower = cm.convert(1000, "twd", "jpy")
        assert result_upper["amount"] == result_lower["amount"]


class TestGetRate:
    def test_get_rate_from_db(self, db_path):
        cm = CurrencyManager(db_path)
        # 種子資料有 JPY 在 2025-03-01
        rate = cm.get_rate("JPY", use_date="2025-03-01")
        assert rate == 4.61

    def test_get_rate_falls_back_to_fallback(self, db_path):
        cm = CurrencyManager(db_path)
        # USD 只有 2025-03-01 的資料，查詢其他日期應走 fallback
        rate = cm.get_rate("USD", use_date="2000-01-01")
        assert rate == FALLBACK_RATES["USD"]

    def test_unknown_currency_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.get_rate("XYZ")

    def test_empty_currency_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.get_rate("")


class TestSaveRate:
    def test_save_and_retrieve_rate(self, db_path):
        cm = CurrencyManager(db_path)
        cm.save_rate("EUR", 0.029, "2025-01-01")
        rate = cm.get_rate("EUR", use_date="2025-01-01")
        assert rate == 0.029

    def test_save_invalid_rate_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.save_rate("JPY", -1.0)

    def test_save_zero_rate_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.save_rate("JPY", 0)


class TestFormatAmount:
    def test_format_twd(self, db_path):
        cm = CurrencyManager(db_path)
        assert cm.format_amount(2170, "TWD") == "NT$2,170"

    def test_format_jpy(self, db_path):
        cm = CurrencyManager(db_path)
        assert cm.format_amount(10000, "JPY") == "¥10,000"

    def test_format_unknown_uses_code(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.format_amount(100, "XYZ")
        assert "100" in result


class TestGetRateHistory:
    def test_history_returns_sorted(self, db_path):
        cm = CurrencyManager(db_path)
        history = cm.get_rate_history("JPY", days=10)
        dates = [h["date"] for h in history]
        assert dates == sorted(dates)

    def test_history_invalid_days_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.get_rate_history("JPY", days=0)

    def test_history_empty_currency_raises(self, db_path):
        cm = CurrencyManager(db_path)
        with pytest.raises(ValueError):
            cm.get_rate_history("")


class TestQuickConvert:
    def test_quick_convert_returns_float(self, db_path):
        cm = CurrencyManager(db_path)
        result = cm.quick_convert(10000, "JPY")
        assert isinstance(result, float)
        assert result > 0

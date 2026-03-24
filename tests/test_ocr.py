"""
test_ocr.py - 電子收據 OCR 掃描模組測試
"""

import pytest
from src.ocr import ReceiptOCR


class TestExtractAmount:
    def test_jpy_symbol(self, db_path):
        ocr = ReceiptOCR(db_path)
        amount, currency = ocr._extract_amount("¥3,500")
        assert amount == 3500.0
        assert currency == "JPY"

    def test_usd_symbol(self, db_path):
        ocr = ReceiptOCR(db_path)
        amount, currency = ocr._extract_amount("$45.99")
        assert amount == 45.99
        assert currency == "USD"

    def test_ntd_symbol(self, db_path):
        ocr = ReceiptOCR(db_path)
        amount, currency = ocr._extract_amount("NT$1,200")
        assert amount == 1200.0
        assert currency == "TWD"

    def test_total_keyword(self, db_path):
        ocr = ReceiptOCR(db_path)
        amount, currency = ocr._extract_amount("Total: 8,500")
        assert amount == 8500.0

    def test_no_amount(self, db_path):
        ocr = ReceiptOCR(db_path)
        amount, currency = ocr._extract_amount("Hello World")
        assert amount is None
        assert currency is None

    def test_jpy_with_spaces(self, db_path):
        ocr = ReceiptOCR(db_path)
        amount, currency = ocr._extract_amount("¥ 12,000")
        assert amount == 12000.0
        assert currency == "JPY"


class TestExtractDate:
    def test_slash_format_yyyy(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_date("2025/03/15")
        assert result == "2025-03-15"

    def test_dash_format(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_date("2025-12-01")
        assert result == "2025-12-01"

    def test_no_date(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_date("Hello World ¥3500")
        assert result is None

    def test_date_in_text(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_date("RECEIPT 2025/06/20 Total: ¥1000")
        assert result == "2025-06-20"


class TestExtractMerchant:
    def test_returns_first_line(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_merchant("Sakura Restaurant\nTotal: ¥3,500")
        assert result == "Sakura Restaurant"

    def test_skips_numeric_lines(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_merchant("1234567\nRamen Shop\nTotal: ¥800")
        assert result == "Ramen Shop"

    def test_empty_text(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._extract_merchant("")
        assert result is None


class TestGuessCategory:
    def test_restaurant_keyword(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._guess_category("ramen shop lunch", "Ramen Restaurant")
        assert result == "餐飲"

    def test_hotel_keyword(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._guess_category("hotel check-in", "Grand Hotel Tokyo")
        assert result == "住宿"

    def test_transport_keyword(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._guess_category("train ticket", "Tokyo Metro")
        assert result == "交通"

    def test_shopping_keyword(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._guess_category("pharmacy cosmetic", "Matsumoto Kiyoshi")
        assert result == "購物"

    def test_default_other(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._guess_category("xyzxyz", "Unknown Place")
        assert result == "其他"

    def test_chinese_keyword(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr._guess_category("藥妝店 購物", "松本清")
        assert result == "購物"


class TestScanReceipt:
    def test_scan_creates_record(self, db_path):
        ocr = ReceiptOCR(db_path)
        # 使用不存在的圖片路徑，scan 會降級到 mock text
        result = ocr.scan_receipt(image_path="fake_receipt.jpg", user_id=1, trip_id=1)
        assert "receipt_id" in result
        assert result["receipt_id"] is not None
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0

    def test_invalid_user_id(self, db_path):
        ocr = ReceiptOCR(db_path)
        with pytest.raises(ValueError):
            ocr.scan_receipt(image_path="fake.jpg", user_id=0)

    def test_invalid_image_path(self, db_path):
        ocr = ReceiptOCR(db_path)
        with pytest.raises(ValueError):
            ocr.scan_receipt(image_path="", user_id=1)


class TestGetReceipts:
    def test_returns_list(self, db_path):
        ocr = ReceiptOCR(db_path)
        ocr.scan_receipt(image_path="fake.jpg", user_id=1, trip_id=1)
        results = ocr.get_receipts(user_id=1)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_filter_by_trip(self, db_path):
        ocr = ReceiptOCR(db_path)
        ocr.scan_receipt(image_path="fake.jpg", user_id=1, trip_id=1)
        results = ocr.get_receipts(user_id=1, trip_id=1)
        assert all(r["trip_id"] == 1 for r in results)

    def test_invalid_user_id(self, db_path):
        ocr = ReceiptOCR(db_path)
        with pytest.raises(ValueError):
            ocr.get_receipts(user_id=-1)


class TestRejectReceipt:
    def test_reject_changes_status(self, db_path):
        ocr = ReceiptOCR(db_path)
        result = ocr.scan_receipt(image_path="fake.jpg", user_id=1, trip_id=1)
        receipt_id = result["receipt_id"]
        ocr.reject_receipt(receipt_id)
        receipts = ocr.get_receipts(user_id=1)
        rejected = [r for r in receipts if r["receipt_id"] == receipt_id]
        assert len(rejected) == 1
        assert rejected[0]["status"] == "rejected"

"""
ocr.py - 電子收據 OCR 掃描模組

功能：
- 上傳收據圖片，使用 pytesseract 進行文字辨識
- 以正則表達式解析金額、幣別、商家名稱、日期、消費類別
- 確認後自動建立交易紀錄
- 歷史掃描紀錄管理

使用方式：
  from src.ocr import ReceiptOCR
  ocr = ReceiptOCR(db_path)
  result = ocr.scan_receipt(image_path="receipt.jpg", user_id=1, trip_id=1)
  ocr.confirm_and_create_txn(receipt_id=result["receipt_id"])

注意：
  需要系統安裝 Tesseract-OCR 及對應語言包（jpn、chi_tra 等）
  若未安裝，模組會自動使用模擬文字進行示範
"""

import sqlite3
import os
import re
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# 關鍵字分類規則
CATEGORY_KEYWORDS = {
    "餐飲": [
        "restaurant", "cafe", "coffee", "food", "ramen", "sushi", "burger",
        "mcdonald", "pizza", "noodle", "breakfast", "lunch", "dinner",
        "餐", "食", "拉麵", "壽司", "咖啡", "飲食", "餐廳", "小吃",
    ],
    "交通": [
        "train", "taxi", "bus", "metro", "subway", "station", "airport",
        "flight", "ticket", "transport", "rail",
        "電車", "地鐵", "計程車", "公車", "機場", "新幹線", "巴士",
    ],
    "住宿": [
        "hotel", "inn", "hostel", "airbnb", "resort", "motel",
        "旅館", "飯店", "民宿", "住宿",
    ],
    "購物": [
        "shop", "store", "mall", "market", "pharmacy", "cosmetic", "drug",
        "duty free", "mart", "supermarket",
        "藥妝", "便利", "超市", "購物", "百貨", "免稅",
    ],
    "娛樂": [
        "museum", "park", "theme", "cinema", "movie", "ticket", "show",
        "博物館", "公園", "遊樂", "電影", "展覽",
    ],
}


class ReceiptOCR:
    """電子收據 OCR 掃描服務"""

    def __init__(self, db_path=None, engine: str = "auto"):
        """
        engine 參數：
            "auto"      — 優先嘗試 Claude Vision，失敗則 fallback 至 pytesseract
            "claude"    — 強制使用 Claude Vision
            "tesseract" — 強制使用 pytesseract（原有行為）
        """
        self.db_path = db_path or DB_PATH
        self.engine = engine
        self._vision_parser = None  # 懶載入

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
    #  OCR 掃描
    # ============================================================

    def _get_vision_parser(self):
        """懶載入 ReceiptVisionParser，無 API Key 時返回 None。"""
        if self._vision_parser is not None:
            return self._vision_parser
        try:
            from src.ai_agent import AIAgentService
            svc = AIAgentService(self.db_path)
            if svc.is_available:
                self._vision_parser = svc.vision_parser
                return self._vision_parser
        except ImportError:
            pass
        return None

    def scan_receipt(self, image_path: str, user_id: int, trip_id: int = None) -> dict:
        """
        掃描收據圖片並解析資料

        參數：
            image_path: 圖片檔案路徑
            user_id: 使用者 ID
            trip_id: 旅行 ID（選填）

        回傳：
            dict: 解析結果，包含 receipt_id 及所有解析欄位
        """
        if not image_path or not isinstance(image_path, str):
            raise ValueError(f"image_path 必須為非空字串，收到: {image_path!r}")
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        # 路徑安全：驗證副檔名在允許白名單內，防止路徑遍歷與危險檔案類型
        _ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in _ALLOWED_EXTS:
            raise ValueError(f"不支援的圖片格式 '{ext}'，僅允許：{', '.join(_ALLOWED_EXTS)}")
        # 確保路徑在系統暫存目錄或允許的目錄內
        import tempfile
        abs_path = os.path.realpath(image_path)
        tmp_dir = os.path.realpath(tempfile.gettempdir())
        if not abs_path.startswith(tmp_dir + os.sep) and abs_path != tmp_dir:
            raise ValueError("image_path 必須位於系統暫存目錄內")

        raw_text = self._do_ocr(image_path)

        # 若 Claude Vision 已解析結構化資料，直接使用（更準確）
        claude_parsed = getattr(self, "_claude_parsed", None)
        if claude_parsed:
            amount = claude_parsed.get("amount")
            currency = claude_parsed.get("currency")
            merchant = claude_parsed.get("merchant")
            date_str = claude_parsed.get("date")
            category = claude_parsed.get("category") or "其他"
            confidence = float(claude_parsed.get("confidence") or 0.75)
        else:
            amount, currency = self._extract_amount(raw_text)
            merchant = self._extract_merchant(raw_text)
            date_str = self._extract_date(raw_text)
            category = self._guess_category(raw_text, merchant or "")
            fields_extracted = sum([
                amount is not None,
                currency is not None,
                merchant is not None,
                date_str is not None,
            ])
            confidence = round(fields_extracted / 4, 2)

        result = {
            "raw_text": raw_text,
            "extracted_amount": amount,
            "extracted_currency": currency,
            "extracted_merchant": merchant,
            "extracted_category": category,
            "extracted_date": date_str,
            "confidence": confidence,
        }

        receipt_id = self.save_receipt({
            **result,
            "user_id": user_id,
            "trip_id": trip_id,
            "image_path": image_path,
        })
        result["receipt_id"] = receipt_id
        return result

    def _do_ocr(self, image_path: str) -> str:
        """
        執行 OCR 辨識。引擎選擇順序：
          engine="auto"     → Claude Vision → pytesseract → 模擬文字
          engine="claude"   → Claude Vision → 模擬文字
          engine="tesseract"→ pytesseract → 模擬文字（原有行為）
        """
        self._claude_parsed = None
        use_claude = self.engine in ("auto", "claude")
        use_tesseract = self.engine in ("auto", "tesseract")

        # 嘗試 Claude Vision
        if use_claude and os.path.exists(image_path):
            parser = self._get_vision_parser()
            if parser:
                result = parser.parse_image(image_path)
                if result and result.get("raw_text"):
                    self._claude_parsed = result
                    return result["raw_text"]

        # Fallback: pytesseract
        if use_tesseract:
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(image_path)
                text = pytesseract.image_to_string(img, lang="jpn+chi_tra+eng")
                return text.strip()
            except ImportError:
                pass
            except Exception:
                pass

        # 最終 Fallback：模擬文字
        return "RECEIPT\nTotal: ¥3,500\n2025/03/15\nRestaurant Sakura"

    # ============================================================
    #  文字解析
    # ============================================================

    def _extract_amount(self, text: str) -> tuple:
        """
        從 OCR 文字解析金額和幣別

        回傳：
            tuple: (amount: float or None, currency: str or None)
        """
        patterns = [
            (r"NT\$\s*([\d,]+(?:\.\d+)?)", "TWD"),
            (r"¥\s*([\d,]+(?:\.\d+)?)", "JPY"),
            (r"\$\s*([\d,]+(?:\.\d{2}))", "USD"),
            (r"₩\s*([\d,]+)", "KRW"),
            (r"฿\s*([\d,]+(?:\.\d+)?)", "THB"),
            (r"(?:Total|合計|小計|TOTAL)[:\s]+[\$¥]?\s*([\d,]+(?:\.\d+)?)", None),
        ]

        for pattern, currency in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                    return amount, currency
                except ValueError:
                    continue

        return None, None

    def _extract_merchant(self, text: str) -> str | None:
        """
        從 OCR 文字解析商家名稱（取第一個有意義的文字行）

        回傳：
            str or None: 商家名稱
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            # 跳過純數字行、日期行
            if re.match(r"^[\d\s\-/:.¥$₩฿,]+$", line):
                continue
            if len(line) < 2:
                continue
            return line[:50]
        return None

    def _extract_date(self, text: str) -> str | None:
        """
        從 OCR 文字解析日期（轉換為 ISO 格式 YYYY-MM-DD）

        回傳：
            str or None: ISO 格式日期字串
        """
        patterns = [
            (r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", "{0}-{1:02d}-{2:02d}"),
            (r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", "{2}-{0:02d}-{1:02d}"),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, text)
            if match:
                groups = [int(g) for g in match.groups()]
                try:
                    if fmt.startswith("{0}"):
                        # YYYY-MM-DD
                        result = fmt.format(groups[0], groups[1], groups[2])
                    else:
                        # DD-MM-YYYY
                        result = fmt.format(groups[0], groups[1], groups[2])
                    # 驗證日期有效性
                    datetime.strptime(result, "%Y-%m-%d")
                    return result
                except (ValueError, IndexError):
                    continue

        return None

    def _guess_category(self, text: str, merchant: str) -> str:
        """
        依關鍵字猜測消費類別

        參數：
            text: OCR 完整文字
            merchant: 商家名稱

        回傳：
            str: 消費類別（預設 '其他'）
        """
        combined = (text + " " + merchant).lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    return category

        return "其他"

    # ============================================================
    #  資料庫操作
    # ============================================================

    def save_receipt(self, data: dict) -> int:
        """
        儲存 OCR 掃描結果至資料庫

        參數：
            data: 包含 user_id, trip_id, image_path 及解析結果的字典

        回傳：
            int: 新建立的 receipt_id
        """
        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT INTO ocr_receipts
                (user_id, trip_id, image_path, raw_text, extracted_amount,
                 extracted_currency, extracted_merchant, extracted_category,
                 extracted_date, confidence, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                data["user_id"],
                data.get("trip_id"),
                data["image_path"],
                data.get("raw_text"),
                data.get("extracted_amount"),
                data.get("extracted_currency"),
                data.get("extracted_merchant"),
                data.get("extracted_category"),
                data.get("extracted_date"),
                data.get("confidence"),
            ))
            return cursor.lastrowid

    def confirm_and_create_txn(
        self, receipt_id: int, corrections: dict = None
    ) -> dict:
        """
        確認 OCR 結果並建立對應的交易紀錄

        參數：
            receipt_id: 收據 ID
            corrections: 覆蓋解析結果的修正值（例如 {"amount": 3500, "category": "餐飲"}）

        回傳：
            dict: {"receipt": dict, "transaction_id": int}
        """
        if not isinstance(receipt_id, int) or receipt_id <= 0:
            raise ValueError(f"receipt_id 必須為正整數，收到: {receipt_id!r}")

        # 取得收據資料
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT receipt_id, user_id, trip_id, extracted_amount,
                       extracted_currency, extracted_merchant, extracted_category,
                       extracted_date, status
                FROM ocr_receipts WHERE receipt_id = ?
            """, (receipt_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"找不到 receipt_id={receipt_id}")

        keys = ["receipt_id", "user_id", "trip_id", "amount", "currency",
                "merchant", "category", "date", "status"]
        receipt = dict(zip(keys, row))

        if receipt["status"] != "pending":
            raise ValueError(f"收據狀態為 {receipt['status']}，無法重複確認")

        # 套用修正
        if corrections:
            for k, v in corrections.items():
                if k in receipt:
                    receipt[k] = v

        # 建立交易紀錄
        amount = receipt["amount"] or 0.0
        currency = receipt["currency"] or "JPY"
        category = receipt["category"] or "其他"
        description = receipt["merchant"] or "OCR 掃描收據"
        trip_id = receipt["trip_id"]
        user_id = receipt["user_id"]
        txn_datetime = receipt["date"] or datetime.now().strftime("%Y-%m-%d") + " 12:00:00"

        # 取得匯率
        try:
            from src.currency import CurrencyManager
            cm = CurrencyManager(self.db_path)
            rate = cm.get_rate(currency)
            amount_twd = round(amount / rate) if rate > 0 else round(amount)
        except Exception:
            rate = 1.0
            amount_twd = round(amount)

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT INTO transactions
                (trip_id, paid_by, amount, currency_code, amount_twd, exchange_rate,
                 category, description, payment_method, txn_datetime, split_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'cash', ?, 'none')
            """, (
                trip_id, user_id, float(amount), currency,
                float(amount_twd), float(rate),
                category, description, txn_datetime,
            ))
            txn_id = cursor.lastrowid

            cursor.execute("""
                UPDATE ocr_receipts
                SET status = 'confirmed', linked_txn_id = ?
                WHERE receipt_id = ?
            """, (txn_id, receipt_id))

        receipt["linked_txn_id"] = txn_id
        return {"receipt": receipt, "transaction_id": txn_id}

    def get_receipts(self, user_id: int, trip_id: int = None) -> list:
        """
        查詢使用者的收據掃描歷史

        參數：
            user_id: 使用者 ID
            trip_id: 旅行 ID（選填，若指定則只回傳該旅行的收據）

        回傳：
            list[dict]: 收據列表，依時間倒序排列
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        query = """
            SELECT receipt_id, user_id, trip_id, image_path, extracted_amount,
                   extracted_currency, extracted_merchant, extracted_category,
                   extracted_date, confidence, status, linked_txn_id, created_at
            FROM ocr_receipts WHERE user_id = ?
        """
        params = [user_id]

        if trip_id is not None:
            if not isinstance(trip_id, int) or trip_id <= 0:
                raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")
            query += " AND trip_id = ?"
            params.append(trip_id)

        query += " ORDER BY created_at DESC"

        with self._db() as (conn, cursor):
            cursor.execute(query, params)
            rows = cursor.fetchall()

        keys = ["receipt_id", "user_id", "trip_id", "image_path", "extracted_amount",
                "extracted_currency", "extracted_merchant", "extracted_category",
                "extracted_date", "confidence", "status", "linked_txn_id", "created_at"]
        return [dict(zip(keys, r)) for r in rows]

    def reject_receipt(self, receipt_id: int) -> None:
        """
        拒絕 OCR 掃描結果

        參數：
            receipt_id: 收據 ID
        """
        if not isinstance(receipt_id, int) or receipt_id <= 0:
            raise ValueError(f"receipt_id 必須為正整數，收到: {receipt_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute(
                "UPDATE ocr_receipts SET status = 'rejected' WHERE receipt_id = ?",
                (receipt_id,)
            )

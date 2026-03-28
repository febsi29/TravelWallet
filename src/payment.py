"""
payment.py - 分帳付款整合模組

功能：
- 為結算紀錄產生付款連結（LINE Pay / 街口支付 / PayPal 模擬）
- QR code 產生（需安裝 qrcode 套件）
- 付款狀態追蹤
- 模擬付款完成（開發測試用）

使用方式：
  from src.payment import PaymentService
  svc = PaymentService(db_path)
  link = svc.generate_payment_link(settlement_id=1, provider="line_pay")
  svc.simulate_payment(link["link_id"])

注意：
  LINE Pay / 街口支付 / PayPal 均為模擬連結，非實際串接
  實際串接需依各平台 API 文件實作
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

VALID_PROVIDERS = ("line_pay", "jko_pay", "paypal")
VALID_STATUSES = ("pending", "paid", "expired", "cancelled")

PROVIDER_NAMES = {
    "line_pay": "LINE Pay",
    "jko_pay":  "街口支付",
    "paypal":   "PayPal",
}


class PaymentService:
    """付款整合服務"""

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
    #  產生付款連結
    # ============================================================

    def generate_payment_link(self, settlement_id: int, provider: str) -> dict:
        """
        為指定結算紀錄產生付款連結

        參數：
            settlement_id: 結算紀錄 ID
            provider: 付款提供商（"line_pay" / "jko_pay" / "paypal"）

        回傳：
            dict: 付款連結資料
        """
        if not isinstance(settlement_id, int) or settlement_id <= 0:
            raise ValueError(f"settlement_id 必須為正整數，收到: {settlement_id!r}")
        if provider not in VALID_PROVIDERS:
            raise ValueError(
                f"provider 必須為 {VALID_PROVIDERS}，收到: {provider!r}"
            )

        # 取得結算資訊
        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT s.settlement_id, s.amount, s.currency_code, s.amount_twd,
                       uf.display_name AS from_name, ut.display_name AS to_name
                FROM settlements s
                JOIN users uf ON s.from_user = uf.user_id
                JOIN users ut ON s.to_user  = ut.user_id
                WHERE s.settlement_id = ?
            """, (settlement_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"找不到 settlement_id={settlement_id}")

        sid, amount, currency, amount_twd, from_name, to_name = row

        payment_url = self._build_payment_url(provider, amount, currency, from_name, to_name)
        qr_code_data = self.generate_qr_code(payment_url)
        expires_at = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT INTO payment_links
                (settlement_id, provider, payment_url, qr_code_data,
                 amount, currency_code, status, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (settlement_id, provider, payment_url, qr_code_data,
                  float(amount), currency, expires_at))
            link_id = cursor.lastrowid

        return {
            "link_id": link_id,
            "settlement_id": settlement_id,
            "provider": provider,
            "provider_name": PROVIDER_NAMES[provider],
            "payment_url": payment_url,
            "qr_code_data": qr_code_data,
            "amount": float(amount),
            "currency_code": currency,
            "amount_twd": float(amount_twd),
            "from_name": from_name,
            "to_name": to_name,
            "status": "pending",
            "expires_at": expires_at,
        }

    def _build_payment_url(
        self,
        provider: str,
        amount: float,
        currency: str,
        from_name: str,
        to_name: str,
    ) -> str:
        """建立各平台的付款連結（模擬）"""
        from urllib.parse import urlencode
        memo = f"TravelWallet-{from_name}-to-{to_name}"

        if provider == "line_pay":
            return "https://line.me/pay/request?" + urlencode(
                {"amount": amount, "currency": currency, "memo": memo}
            )
        elif provider == "jko_pay":
            return "https://payment.jkopay.com/request?" + urlencode(
                {"amount": amount, "currency": currency, "note": memo}
            )
        elif provider == "paypal":
            return f"https://paypal.me/TravelWallet/{amount}{currency}"
        else:
            return f"https://pay.example.com/{provider}?amount={amount}"

    def generate_qr_code(self, payment_data: str) -> str:
        """
        產生 QR code（Base64 PNG 字串）

        若未安裝 qrcode 套件，直接回傳原始 URL 字串

        參數：
            payment_data: QR code 內容（通常為付款 URL）

        回傳：
            str: Base64 編碼的 PNG 圖片，或原始 URL（降級）
        """
        try:
            import qrcode
            import io
            import base64

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=2,
            )
            qr.add_data(payment_data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return "data:image/png;base64," + base64.b64encode(buffer.read()).decode()

        except ImportError:
            # qrcode 未安裝，回傳原始 URL
            return payment_data

    # ============================================================
    #  付款狀態管理
    # ============================================================

    def get_payment_status(self, link_id: int) -> dict:
        """
        查詢付款連結狀態

        參數：
            link_id: 付款連結 ID

        回傳：
            dict: 付款連結完整資料
        """
        if not isinstance(link_id, int) or link_id <= 0:
            raise ValueError(f"link_id 必須為正整數，收到: {link_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT link_id, settlement_id, provider, payment_url, qr_code_data,
                       amount, currency_code, status, expires_at, paid_at, provider_ref,
                       created_at
                FROM payment_links WHERE link_id = ?
            """, (link_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"找不到 link_id={link_id}")

        keys = ["link_id", "settlement_id", "provider", "payment_url", "qr_code_data",
                "amount", "currency_code", "status", "expires_at", "paid_at",
                "provider_ref", "created_at"]
        return dict(zip(keys, row))

    def update_payment_status(
        self, link_id: int, status: str, provider_ref: str = None
    ) -> None:
        """
        更新付款連結狀態

        參數：
            link_id: 付款連結 ID
            status: 新狀態（"pending" / "paid" / "expired" / "cancelled"）
            provider_ref: 第三方支付參考號
        """
        if not isinstance(link_id, int) or link_id <= 0:
            raise ValueError(f"link_id 必須為正整數，收到: {link_id!r}")
        if status not in VALID_STATUSES:
            raise ValueError(f"status 必須為 {VALID_STATUSES}，收到: {status!r}")

        paid_at = "datetime('now')" if status == "paid" else "NULL"

        with self._db() as (conn, cursor):
            cursor.execute(f"""
                UPDATE payment_links
                SET status = ?,
                    paid_at = CASE WHEN ? = 'paid' THEN datetime('now') ELSE NULL END,
                    provider_ref = ?
                WHERE link_id = ?
            """, (status, status, provider_ref, link_id))

    def get_pending_payments(self, user_id: int) -> list:
        """
        查詢使用者的待付款清單

        參數：
            user_id: 使用者 ID

        回傳：
            list[dict]: 待付款項目列表
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT pl.link_id, pl.settlement_id, pl.provider,
                       pl.payment_url, pl.amount, pl.currency_code,
                       pl.status, s.from_user, s.to_user,
                       uf.display_name AS from_name, ut.display_name AS to_name
                FROM payment_links pl
                JOIN settlements s ON pl.settlement_id = s.settlement_id
                JOIN users uf ON s.from_user = uf.user_id
                JOIN users ut ON s.to_user   = ut.user_id
                WHERE s.from_user = ? AND pl.status = 'pending'
                ORDER BY pl.created_at DESC
            """, (user_id,))
            rows = cursor.fetchall()

        keys = ["link_id", "settlement_id", "provider", "payment_url",
                "amount", "currency_code", "status", "from_user", "to_user",
                "from_name", "to_name"]
        return [dict(zip(keys, r)) for r in rows]

    def get_settlement_payments(self, settlement_id: int) -> list:
        """
        查詢某結算紀錄的所有付款連結

        參數：
            settlement_id: 結算紀錄 ID

        回傳：
            list[dict]: 付款連結列表
        """
        if not isinstance(settlement_id, int) or settlement_id <= 0:
            raise ValueError(f"settlement_id 必須為正整數，收到: {settlement_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT link_id, settlement_id, provider, payment_url,
                       amount, currency_code, status, expires_at, paid_at, created_at
                FROM payment_links
                WHERE settlement_id = ?
                ORDER BY created_at DESC
            """, (settlement_id,))
            rows = cursor.fetchall()

        keys = ["link_id", "settlement_id", "provider", "payment_url",
                "amount", "currency_code", "status", "expires_at", "paid_at", "created_at"]
        return [dict(zip(keys, r)) for r in rows]

    def simulate_payment(self, link_id: int) -> dict:
        """
        模擬付款完成（開發測試用）

        參數：
            link_id: 付款連結 ID

        回傳：
            dict: 更新後的付款連結資料
        """
        if not isinstance(link_id, int) or link_id <= 0:
            raise ValueError(f"link_id 必須為正整數，收到: {link_id!r}")

        self.update_payment_status(
            link_id, "paid", provider_ref=f"DEMO_{link_id:06d}"
        )
        return self.get_payment_status(link_id)

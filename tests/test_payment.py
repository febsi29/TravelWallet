"""
test_payment.py - 分帳付款整合模組測試
"""

import pytest
from src.payment import PaymentService


class TestGeneratePaymentLink:
    def test_line_pay_link(self, db_path):
        svc = PaymentService(db_path)
        result = svc.generate_payment_link(settlement_id=1, provider="line_pay")
        assert "link_id" in result
        assert result["provider"] == "line_pay"
        assert "line.me" in result["payment_url"]
        assert result["amount"] > 0

    def test_jko_pay_link(self, db_path):
        svc = PaymentService(db_path)
        result = svc.generate_payment_link(settlement_id=1, provider="jko_pay")
        assert "jkopay.com" in result["payment_url"]

    def test_paypal_link(self, db_path):
        svc = PaymentService(db_path)
        result = svc.generate_payment_link(settlement_id=1, provider="paypal")
        assert "paypal.me" in result["payment_url"]

    def test_invalid_provider(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.generate_payment_link(settlement_id=1, provider="bitcoin")

    def test_invalid_settlement_id(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.generate_payment_link(settlement_id=0, provider="line_pay")

    def test_nonexistent_settlement(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.generate_payment_link(settlement_id=9999, provider="line_pay")

    def test_link_has_all_fields(self, db_path):
        svc = PaymentService(db_path)
        result = svc.generate_payment_link(settlement_id=1, provider="line_pay")
        for field in ["link_id", "settlement_id", "provider", "payment_url",
                      "amount", "currency_code", "status", "from_name", "to_name"]:
            assert field in result


class TestUpdatePaymentStatus:
    def test_mark_as_paid(self, db_path):
        svc = PaymentService(db_path)
        link = svc.generate_payment_link(settlement_id=1, provider="line_pay")
        svc.update_payment_status(link["link_id"], "paid")
        updated = svc.get_payment_status(link["link_id"])
        assert updated["status"] == "paid"

    def test_mark_as_expired(self, db_path):
        svc = PaymentService(db_path)
        link = svc.generate_payment_link(settlement_id=1, provider="jko_pay")
        svc.update_payment_status(link["link_id"], "expired")
        updated = svc.get_payment_status(link["link_id"])
        assert updated["status"] == "expired"

    def test_invalid_status(self, db_path):
        svc = PaymentService(db_path)
        link = svc.generate_payment_link(settlement_id=1, provider="line_pay")
        with pytest.raises(ValueError):
            svc.update_payment_status(link["link_id"], "unknown_status")

    def test_invalid_link_id(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.update_payment_status(link_id=0, status="paid")


class TestGetPendingPayments:
    def test_returns_list(self, db_path):
        svc = PaymentService(db_path)
        # seed data 有 user 3 欠 user 1
        result = svc.get_pending_payments(user_id=3)
        assert isinstance(result, list)

    def test_invalid_user_id(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.get_pending_payments(user_id=-1)


class TestGetSettlementPayments:
    def test_returns_list(self, db_path):
        svc = PaymentService(db_path)
        svc.generate_payment_link(settlement_id=1, provider="line_pay")
        result = svc.get_settlement_payments(settlement_id=1)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_invalid_settlement_id(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.get_settlement_payments(settlement_id=0)


class TestSimulatePayment:
    def test_simulation_marks_paid(self, db_path):
        svc = PaymentService(db_path)
        link = svc.generate_payment_link(settlement_id=1, provider="paypal")
        result = svc.simulate_payment(link["link_id"])
        assert result["status"] == "paid"
        assert result["provider_ref"] is not None
        assert "DEMO" in result["provider_ref"]

    def test_invalid_link_id(self, db_path):
        svc = PaymentService(db_path)
        with pytest.raises(ValueError):
            svc.simulate_payment(link_id=0)

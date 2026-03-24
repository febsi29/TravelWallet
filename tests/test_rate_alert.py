"""
test_rate_alert.py - 匯率到價提醒模組測試
"""

import pytest
from src.rate_alert import RateAlertService


class TestCreateAlert:
    def test_create_alert_basic(self, db_path):
        svc = RateAlertService(db_path)
        alert = svc.create_alert(
            user_id=1, target_currency="JPY", target_rate=4.8, direction="above"
        )
        assert alert["alert_id"] is not None
        assert alert["user_id"] == 1
        assert alert["target_currency"] == "JPY"
        assert alert["target_rate"] == 4.8
        assert alert["direction"] == "above"
        assert alert["is_active"] == 1
        assert alert["is_triggered"] == 0

    def test_create_alert_below(self, db_path):
        svc = RateAlertService(db_path)
        alert = svc.create_alert(
            user_id=1, target_currency="USD", target_rate=0.029, direction="below", note="測試備註"
        )
        assert alert["direction"] == "below"
        assert alert["note"] == "測試備註"

    def test_invalid_user_id(self, db_path):
        svc = RateAlertService(db_path)
        with pytest.raises(ValueError):
            svc.create_alert(user_id=0, target_currency="JPY", target_rate=4.8)

    def test_invalid_direction(self, db_path):
        svc = RateAlertService(db_path)
        with pytest.raises(ValueError):
            svc.create_alert(user_id=1, target_currency="JPY", target_rate=4.8, direction="sideways")

    def test_invalid_rate(self, db_path):
        svc = RateAlertService(db_path)
        with pytest.raises(ValueError):
            svc.create_alert(user_id=1, target_currency="JPY", target_rate=-1.0)

    def test_invalid_currency(self, db_path):
        svc = RateAlertService(db_path)
        with pytest.raises(ValueError):
            svc.create_alert(user_id=1, target_currency="", target_rate=4.8)


class TestGetAlerts:
    def test_get_active_only(self, db_path):
        svc = RateAlertService(db_path)
        svc.create_alert(user_id=1, target_currency="JPY", target_rate=4.8)
        alerts = svc.get_alerts(user_id=1, active_only=True)
        assert isinstance(alerts, list)
        assert len(alerts) >= 1
        assert all(a["is_active"] == 1 for a in alerts)

    def test_get_all_including_inactive(self, db_path):
        svc = RateAlertService(db_path)
        alert = svc.create_alert(user_id=1, target_currency="JPY", target_rate=4.8)
        svc.deactivate_alert(alert["alert_id"])

        active_alerts = svc.get_alerts(user_id=1, active_only=True)
        all_alerts = svc.get_alerts(user_id=1, active_only=False)
        assert len(all_alerts) >= len(active_alerts)

    def test_invalid_user_id(self, db_path):
        svc = RateAlertService(db_path)
        with pytest.raises(ValueError):
            svc.get_alerts(user_id=-1)


class TestCheckAlerts:
    def test_check_returns_list(self, db_path):
        svc = RateAlertService(db_path)
        # 建立一個高目標匯率的提醒（不太可能觸發）
        svc.create_alert(user_id=1, target_currency="JPY", target_rate=999.0, direction="above")
        triggered = svc.check_alerts(user_id=1)
        assert isinstance(triggered, list)

    def test_check_triggers_below_alert(self, db_path):
        svc = RateAlertService(db_path)
        # 建立一個低目標匯率的 below 提醒（備用匯率為 4.61，目標 10.0 一定滿足 below 條件不成立）
        # 目標: 低於 999 一定觸發
        svc.create_alert(user_id=2, target_currency="JPY", target_rate=999.0, direction="below")
        triggered = svc.check_alerts(user_id=2)
        # 因為備用匯率 4.61 < 999，所以 below 條件成立
        assert isinstance(triggered, list)
        assert len(triggered) >= 1


class TestDeactivateAlert:
    def test_deactivate(self, db_path):
        svc = RateAlertService(db_path)
        alert = svc.create_alert(user_id=1, target_currency="JPY", target_rate=4.8)
        svc.deactivate_alert(alert["alert_id"])

        alerts = svc.get_alerts(user_id=1, active_only=True)
        ids = [a["alert_id"] for a in alerts]
        assert alert["alert_id"] not in ids

    def test_invalid_alert_id(self, db_path):
        svc = RateAlertService(db_path)
        with pytest.raises(ValueError):
            svc.deactivate_alert(alert_id=0)


class TestGetTriggeredAlerts:
    def test_get_triggered_empty(self, db_path):
        svc = RateAlertService(db_path)
        triggered = svc.get_triggered_alerts(user_id=1)
        assert isinstance(triggered, list)

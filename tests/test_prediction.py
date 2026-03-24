"""
test_prediction.py - 支出預測與智慧提醒模組測試
"""

import pytest
from src.prediction import SpendingPredictor


class TestPredictBudgetExceedDay:
    def test_returns_dict_structure(self, db_path):
        predictor = SpendingPredictor(db_path)
        result = predictor.predict_budget_exceed_day(trip_id=1)
        assert isinstance(result, dict)
        assert "will_exceed" in result

    def test_invalid_trip_id(self, db_path):
        predictor = SpendingPredictor(db_path)
        with pytest.raises(ValueError):
            predictor.predict_budget_exceed_day(trip_id=0)

    def test_nonexistent_trip(self, db_path):
        predictor = SpendingPredictor(db_path)
        result = predictor.predict_budget_exceed_day(trip_id=9999)
        # 找不到旅行時回傳含 error 的 dict
        assert isinstance(result, dict)


class TestPredictDailySpending:
    def test_returns_dict(self, db_path):
        predictor = SpendingPredictor(db_path)
        result = predictor.predict_daily_spending(trip_id=1)
        assert isinstance(result, dict)
        assert "historical" in result
        assert "predicted_next" in result
        assert "trend" in result

    def test_trend_is_valid_value(self, db_path):
        predictor = SpendingPredictor(db_path)
        result = predictor.predict_daily_spending(trip_id=1)
        assert result["trend"] in ("up", "down", "stable")

    def test_no_data_returns_empty(self, db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO trips (user_id, trip_name, destination, currency_code, start_date, end_date) VALUES (1, '空旅行', '測試', 'JPY', '2025-01-01', '2025-01-05')")
        conn.commit()
        conn.close()

        predictor = SpendingPredictor(db_path)
        # 取得新建旅行的 trip_id
        import sqlite3 as sq
        conn2 = sq.connect(db_path)
        row = conn2.execute("SELECT trip_id FROM trips WHERE trip_name='空旅行'").fetchone()
        conn2.close()
        new_trip_id = row[0]

        result = predictor.predict_daily_spending(trip_id=new_trip_id)
        assert result["historical"] == []

    def test_invalid_trip_id(self, db_path):
        predictor = SpendingPredictor(db_path)
        with pytest.raises(ValueError):
            predictor.predict_daily_spending(trip_id=-1)


class TestCheckOverspend:
    def test_returns_list(self, db_path):
        predictor = SpendingPredictor(db_path)
        result = predictor.check_overspend(trip_id=1, user_id=1)
        assert isinstance(result, list)

    def test_invalid_ids(self, db_path):
        predictor = SpendingPredictor(db_path)
        with pytest.raises(ValueError):
            predictor.check_overspend(trip_id=0, user_id=1)
        with pytest.raises(ValueError):
            predictor.check_overspend(trip_id=1, user_id=0)


class TestGenerateAllAlerts:
    def test_returns_list(self, db_path):
        predictor = SpendingPredictor(db_path)
        result = predictor.generate_all_alerts(trip_id=1, user_id=1)
        assert isinstance(result, list)

    def test_alerts_have_required_fields(self, db_path):
        predictor = SpendingPredictor(db_path)
        alerts = predictor.generate_all_alerts(trip_id=1, user_id=1)
        for alert in alerts:
            assert "title" in alert
            assert "severity" in alert
            assert "message" in alert

    def test_invalid_ids(self, db_path):
        predictor = SpendingPredictor(db_path)
        with pytest.raises(ValueError):
            predictor.generate_all_alerts(trip_id=0, user_id=1)


class TestGetAlerts:
    def test_returns_list(self, db_path):
        predictor = SpendingPredictor(db_path)
        # 先產生提醒
        predictor.generate_all_alerts(trip_id=1, user_id=1)
        result = predictor.get_alerts(trip_id=1, user_id=1)
        assert isinstance(result, list)

    def test_unread_only_filter(self, db_path):
        predictor = SpendingPredictor(db_path)
        predictor.generate_all_alerts(trip_id=1, user_id=1)
        unread = predictor.get_alerts(trip_id=1, user_id=1, unread_only=True)
        all_alerts = predictor.get_alerts(trip_id=1, user_id=1)
        assert len(unread) <= len(all_alerts)


class TestMarkRead:
    def test_marks_as_read(self, db_path):
        predictor = SpendingPredictor(db_path)
        alerts = predictor.generate_all_alerts(trip_id=1, user_id=1)
        if alerts and "alert_id" in alerts[0]:
            alert_id = alerts[0]["alert_id"]
            predictor.mark_read(alert_id)
            remaining_unread = predictor.get_alerts(trip_id=1, user_id=1, unread_only=True)
            ids = [a["alert_id"] for a in remaining_unread]
            assert alert_id not in ids

    def test_invalid_alert_id(self, db_path):
        predictor = SpendingPredictor(db_path)
        with pytest.raises(ValueError):
            predictor.mark_read(alert_id=0)

"""
test_risk_dashboard.py - 風險評估儀表板模組測試
"""

import pytest
from src.risk_dashboard import RiskDashboard


class TestAssessFxRisk:
    def test_returns_structure(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_fx_risk(trip_id=1)
        assert isinstance(result, dict)
        assert "risk_score" in result
        assert "level" in result
        assert "message" in result

    def test_risk_score_in_range(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_fx_risk(trip_id=1)
        assert 0.0 <= result["risk_score"] <= 100.0

    def test_level_is_valid(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_fx_risk(trip_id=1)
        assert result["level"] in ("低", "中等", "高")

    def test_invalid_trip_id(self, db_path):
        rd = RiskDashboard(db_path)
        with pytest.raises(ValueError):
            rd.assess_fx_risk(trip_id=0)


class TestAssessBudgetRisk:
    def test_returns_structure(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_budget_risk(trip_id=1)
        assert isinstance(result, dict)
        assert "risk_score" in result
        assert "level" in result

    def test_risk_score_in_range(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_budget_risk(trip_id=1)
        assert 0.0 <= result["risk_score"] <= 100.0


class TestAssessAnomalyRisk:
    def test_returns_structure(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_anomaly_risk(trip_id=1)
        assert isinstance(result, dict)
        assert "risk_score" in result
        assert "anomaly_rate" in result

    def test_risk_score_in_range(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_anomaly_risk(trip_id=1)
        assert 0.0 <= result["risk_score"] <= 100.0

    def test_invalid_trip_id(self, db_path):
        rd = RiskDashboard(db_path)
        with pytest.raises(ValueError):
            rd.assess_anomaly_risk(trip_id=-1)


class TestAssessOverall:
    def test_returns_all_dimensions(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_overall(user_id=1, trip_id=1)
        assert "overall_risk" in result
        assert "health_index" in result
        assert "fx" in result
        assert "budget" in result
        assert "anomaly" in result
        assert "credit" in result
        assert "recommendations" in result

    def test_overall_risk_in_range(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_overall(user_id=1, trip_id=1)
        assert 0.0 <= result["overall_risk"] <= 100.0

    def test_health_index_is_valid(self, db_path):
        rd = RiskDashboard(db_path)
        result = rd.assess_overall(user_id=1, trip_id=1)
        assert result["health_index"] in ("A", "B", "C", "D", "F")

    def test_invalid_user_id(self, db_path):
        rd = RiskDashboard(db_path)
        with pytest.raises(ValueError):
            rd.assess_overall(user_id=0, trip_id=1)

    def test_invalid_trip_id(self, db_path):
        rd = RiskDashboard(db_path)
        with pytest.raises(ValueError):
            rd.assess_overall(user_id=1, trip_id=-1)

    def test_saves_to_db(self, db_path):
        import sqlite3
        rd = RiskDashboard(db_path)
        rd.assess_overall(user_id=1, trip_id=1)
        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM risk_assessments WHERE user_id=1"
        ).fetchone()[0]
        conn.close()
        assert count >= 1


class TestGenerateRecommendations:
    def test_returns_list(self, db_path):
        rd = RiskDashboard(db_path)
        assessment = {
            "budget": {"risk_score": 80},
            "anomaly": {"risk_score": 70},
            "fx": {"risk_score": 65},
            "credit": {"risk_score": 50},
        }
        recs = rd.generate_recommendations(assessment)
        assert isinstance(recs, list)
        assert len(recs) >= 1

    def test_low_risk_returns_positive_message(self, db_path):
        rd = RiskDashboard(db_path)
        assessment = {
            "budget": {"risk_score": 10},
            "anomaly": {"risk_score": 5},
            "fx": {"risk_score": 15},
            "credit": {"risk_score": 10},
        }
        recs = rd.generate_recommendations(assessment)
        assert len(recs) >= 1


class TestGetRiskHistory:
    def test_history_returns_list(self, db_path):
        rd = RiskDashboard(db_path)
        rd.assess_overall(user_id=1, trip_id=1)
        history = rd.get_risk_history(user_id=1)
        assert isinstance(history, list)
        assert len(history) >= 1

    def test_invalid_user_id(self, db_path):
        rd = RiskDashboard(db_path)
        with pytest.raises(ValueError):
            rd.get_risk_history(user_id=0)

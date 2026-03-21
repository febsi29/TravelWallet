"""test_budget.py - BudgetManager 單元測試"""

import pytest
from src.budget import BudgetManager


class TestGetBurndown:
    def test_returns_correct_structure(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.get_burndown(1)
        assert "trip" in result
        assert "burndown" in result
        assert "num_members" in result
        assert "daily_planned" in result

    def test_burndown_days_count(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.get_burndown(1)
        # 旅行 2025-03-01 ~ 2025-03-05 = 5 天
        assert len(result["burndown"]) == 5

    def test_burndown_day_fields(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.get_burndown(1)
        for entry in result["burndown"]:
            assert "day"               in entry
            assert "date"              in entry
            assert "planned_remaining" in entry
            assert "actual_remaining"  in entry
            assert "daily_spent"       in entry
            assert "cumulative_spent"  in entry
            assert "on_track"          in entry

    def test_cumulative_is_monotone(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.get_burndown(1)
        cumulative = [b["cumulative_spent"] for b in result["burndown"]]
        assert cumulative == sorted(cumulative)

    def test_invalid_trip_raises(self, db_path):
        bm = BudgetManager(db_path)
        with pytest.raises(ValueError):
            bm.get_burndown(9999)

    def test_negative_trip_id_raises(self, db_path):
        bm = BudgetManager(db_path)
        with pytest.raises(ValueError):
            bm.get_burndown(-1)


class TestPredictRemaining:
    def test_returns_correct_structure(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.predict_remaining(1)
        assert "predicted_total"    in result
        assert "actual_spent"       in result
        assert "predicted_remaining" in result
        assert "will_exceed"        in result
        assert "daily_rate"         in result
        assert "prediction_line"    in result

    def test_prediction_line_length(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.predict_remaining(1)
        assert len(result["prediction_line"]) == 5  # 5 天

    def test_predict_at_day_3(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.predict_remaining(1, current_day=3)
        assert result["current_day"] == 3
        assert result["days_remaining"] == 2

    def test_invalid_current_day_raises(self, db_path):
        bm = BudgetManager(db_path)
        with pytest.raises(ValueError):
            bm.predict_remaining(1, current_day=0)

    def test_invalid_type_current_day_raises(self, db_path):
        bm = BudgetManager(db_path)
        with pytest.raises(ValueError):
            bm.predict_remaining(1, current_day="abc")

    def test_predicted_total_is_positive(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.predict_remaining(1)
        assert result["predicted_total"] >= 0


class TestSuggestDailyLimit:
    def test_mid_trip_returns_limit(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.suggest_daily_limit(1, current_day=2)
        assert result["status"] in ("on_track", "over_budget")
        assert "suggested_daily_limit" in result
        assert "remaining_budget"      in result

    def test_completed_trip_status(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.suggest_daily_limit(1, current_day=5)
        assert result["status"] == "trip_completed"

    def test_suggested_limit_non_negative(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.suggest_daily_limit(1, current_day=3)
        assert result.get("suggested_daily_limit", 0) >= 0

    def test_invalid_current_day_raises(self, db_path):
        bm = BudgetManager(db_path)
        with pytest.raises(ValueError):
            bm.suggest_daily_limit(1, current_day=-1)


class TestAssessHealth:
    def test_returns_score_and_status(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.assess_health(1)
        assert "score"       in result
        assert "status"      in result
        assert "usage_ratio" in result

    def test_score_in_valid_range(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.assess_health(1)
        assert 0 <= result["score"] <= 100

    def test_on_track_days_valid(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.assess_health(1)
        assert 0 <= result["on_track_days"] <= result["total_days"]

    def test_usage_ratio_positive(self, db_path):
        bm = BudgetManager(db_path)
        result = bm.assess_health(1)
        assert result["usage_ratio"] >= 0

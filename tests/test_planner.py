"""test_planner.py - TripPlanner 單元測試"""

import pytest
from src.planner import TripPlanner, DESTINATION_FACTORS


class TestSuggestBudget:
    def test_returns_correct_structure(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("日本", 5, num_travelers=2)
        assert "destination"     in plan
        assert "days"            in plan
        assert "num_travelers"   in plan
        assert "tiers"           in plan
        assert "category_ratios" in plan
        assert "data_source"     in plan

    def test_three_tiers_returned(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("日本", 5)
        assert set(plan["tiers"].keys()) == {"budget", "standard", "premium"}

    def test_tier_hierarchy(self, db_path):
        """豪華版 > 標準版 > 節省版"""
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("日本", 5)
        assert plan["tiers"]["premium"]["total_per_person"] > plan["tiers"]["standard"]["total_per_person"]
        assert plan["tiers"]["standard"]["total_per_person"] > plan["tiers"]["budget"]["total_per_person"]

    def test_group_total_is_per_person_times_travelers(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("泰國", 7, num_travelers=4)
        for tier in plan["tiers"].values():
            assert tier["total_group"] == tier["total_per_person"] * 4

    def test_category_breakdown_sums_approximately_to_total(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("韓國", 5)
        std = plan["tiers"]["standard"]
        breakdown_sum = sum(std["breakdown"].values())
        assert abs(breakdown_sum - std["total_per_person"]) / std["total_per_person"] < 0.05

    def test_unknown_destination_uses_default_factor(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("月球", 3)
        assert plan["destination_factor"] == 1.0
        assert plan["currency_code"] == "USD"

    def test_destination_factor_applied(self, db_path):
        planner = TripPlanner(db_path)
        plan_japan = planner.suggest_budget("日本", 5)   # factor=1.15
        plan_thai  = planner.suggest_budget("泰國", 5)   # factor=0.70
        assert plan_japan["tiers"]["standard"]["total_per_person"] > \
               plan_thai["tiers"]["standard"]["total_per_person"]

    def test_invalid_destination_raises(self, db_path):
        planner = TripPlanner(db_path)
        with pytest.raises(ValueError):
            planner.suggest_budget("", 5)

    def test_invalid_days_raises(self, db_path):
        planner = TripPlanner(db_path)
        with pytest.raises(ValueError):
            planner.suggest_budget("日本", 0)

    def test_invalid_travelers_raises(self, db_path):
        planner = TripPlanner(db_path)
        with pytest.raises(ValueError):
            planner.suggest_budget("日本", 5, num_travelers=-1)


class TestCompareDestinations:
    def test_returns_all_destinations(self, db_path):
        planner = TripPlanner(db_path)
        comparisons = planner.compare_destinations(days=5)
        assert len(comparisons) == len(DESTINATION_FACTORS)

    def test_sorted_by_cost_ascending(self, db_path):
        planner = TripPlanner(db_path)
        comparisons = planner.compare_destinations(days=5)
        costs = [c["total_per_person"] for c in comparisons]
        assert costs == sorted(costs)

    def test_each_entry_has_required_keys(self, db_path):
        planner = TripPlanner(db_path)
        for c in planner.compare_destinations(days=5):
            assert "destination"      in c
            assert "total_per_person" in c
            assert "factor"           in c

    def test_invalid_days_raises(self, db_path):
        planner = TripPlanner(db_path)
        with pytest.raises(ValueError):
            planner.compare_destinations(days=-1)


class TestGetAvgDailySpending:
    def test_returns_positive_value(self, db_path):
        planner = TripPlanner(db_path)
        avg = planner._get_avg_daily_spending()
        assert avg > 0

    def test_uses_latest_year(self, db_path):
        """種子資料有 2022 和 2023，應用 2023 的資料（60481 / 7.84 ≈ 7714）"""
        planner = TripPlanner(db_path)
        avg = planner._get_avg_daily_spending()
        assert 7000 < avg < 9000


class TestSavePlan:
    def test_save_plan_returns_plan_id(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("日本", 5, num_travelers=2)
        plan_id = planner.save_plan(user_id=1, plan=plan, user_budget=80000)
        assert isinstance(plan_id, int)
        assert plan_id > 0

    def test_save_plan_invalid_user_raises(self, db_path):
        planner = TripPlanner(db_path)
        plan = planner.suggest_budget("日本", 5)
        with pytest.raises(ValueError):
            planner.save_plan(user_id=-1, plan=plan)

"""
test_community.py - 社群排行榜模組測試
"""

import pytest
from src.community import CommunityService


class TestShareTripData:
    def test_share_creates_record(self, db_path):
        svc = CommunityService(db_path)
        result = svc.share_trip_data(user_id=1, trip_id=1)
        assert "destination" in result
        assert "per_person_daily" in result
        assert result["per_person_daily"] >= 0

    def test_share_idempotent(self, db_path):
        svc = CommunityService(db_path)
        svc.share_trip_data(user_id=1, trip_id=1)
        svc.share_trip_data(user_id=1, trip_id=1)  # INSERT OR REPLACE
        # 不應報錯，且資料應覆蓋

    def test_invalid_user_id(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.share_trip_data(user_id=0, trip_id=1)

    def test_invalid_trip_id(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.share_trip_data(user_id=1, trip_id=-1)

    def test_nonexistent_trip(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.share_trip_data(user_id=1, trip_id=9999)


class TestGetLeaderboard:
    def test_frugal_returns_list(self, db_path):
        svc = CommunityService(db_path)
        svc.share_trip_data(user_id=1, trip_id=1)
        result = svc.get_leaderboard(metric="frugal")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_spender_returns_list(self, db_path):
        svc = CommunityService(db_path)
        svc.share_trip_data(user_id=1, trip_id=1)
        result = svc.get_leaderboard(metric="spender")
        assert isinstance(result, list)

    def test_invalid_metric(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.get_leaderboard(metric="unknown")

    def test_frugal_sorted_ascending(self, db_path):
        svc = CommunityService(db_path)
        # 新增多筆不同消費
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT OR REPLACE INTO community_stats
            (destination, trip_days, num_travelers, total_spent_twd, per_person_daily, user_id, trip_id)
            VALUES ('測試地A', 5, 2, 100000, 10000, 2, 1)
        """)
        conn.execute("""
            INSERT OR REPLACE INTO community_stats
            (destination, trip_days, num_travelers, total_spent_twd, per_person_daily, user_id, trip_id)
            VALUES ('測試地B', 5, 2, 40000, 4000, 3, 1)
        """)
        conn.commit()
        conn.close()

        result = svc.get_leaderboard(metric="frugal")
        if len(result) >= 2:
            assert result[0]["per_person_daily"] <= result[-1]["per_person_daily"]


class TestGetDestinationStats:
    def test_returns_dict(self, db_path):
        svc = CommunityService(db_path)
        svc.share_trip_data(user_id=1, trip_id=1)
        result = svc.get_destination_stats(destination="日本")
        assert isinstance(result, dict)
        assert "destination" in result
        assert "count" in result
        assert "avg_daily" in result

    def test_empty_destination(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.get_destination_stats(destination="")

    def test_unknown_destination_returns_zero(self, db_path):
        svc = CommunityService(db_path)
        result = svc.get_destination_stats(destination="月球")
        assert result["count"] == 0


class TestGetSimilarTrips:
    def test_returns_dict(self, db_path):
        svc = CommunityService(db_path)
        svc.share_trip_data(user_id=1, trip_id=1)
        result = svc.get_similar_trips(destination="日本", days=5, num_travelers=3)
        assert isinstance(result, dict)
        assert "similar_count" in result
        assert "avg_daily" in result

    def test_invalid_days(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.get_similar_trips(destination="日本", days=0, num_travelers=2)


class TestGetMyRanking:
    def test_ranking_structure(self, db_path):
        svc = CommunityService(db_path)
        svc.share_trip_data(user_id=1, trip_id=1)
        result = svc.get_my_ranking(user_id=1, trip_id=1)
        assert isinstance(result, dict)
        assert "rank" in result
        assert "percentile" in result
        assert "per_person_daily" in result

    def test_not_shared_returns_none_rank(self, db_path):
        svc = CommunityService(db_path)
        # user 2 沒有分享 trip_id=1
        result = svc.get_my_ranking(user_id=2, trip_id=1)
        assert result["rank"] is None

    def test_invalid_ids(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.get_my_ranking(user_id=0, trip_id=1)


class TestGetDestinationComparison:
    def test_multiple_destinations(self, db_path):
        svc = CommunityService(db_path)
        result = svc.get_destination_comparison(destinations=["日本", "韓國"])
        assert isinstance(result, list)
        assert len(result) == 2

    def test_invalid_empty_list(self, db_path):
        svc = CommunityService(db_path)
        with pytest.raises(ValueError):
            svc.get_destination_comparison(destinations=[])

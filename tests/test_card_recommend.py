"""
test_card_recommend.py - 信用卡推薦模組測試
"""

import pytest
from src.card_recommend import CardRecommendService, seed_cards


class TestSeedCards:
    def test_seed_creates_cards(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        assert len(cards) >= 6

    def test_seed_is_idempotent(self, db_path):
        seed_cards(db_path)
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        # 不應重複建立
        names = [c["card_name"] for c in cards]
        assert len(names) == len(set(names))


class TestGetAllCards:
    def test_empty_when_no_cards(self, db_path):
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        assert isinstance(cards, list)

    def test_returns_cards_after_seed(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        assert len(cards) > 0
        assert "card_name" in cards[0]
        assert "rewards" in cards[0]
        assert isinstance(cards[0]["rewards"], list)


class TestCalculateReward:
    def test_cashback_calculation(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        card_id = cards[0]["card_id"]
        result = svc.calculate_reward(card_id=card_id, amount=10000, category="餐飲", region="日本")
        assert "reward_amount" in result
        assert "net_benefit" in result
        assert "fee_amount" in result
        assert isinstance(result["reward_amount"], float)

    def test_reward_not_negative(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        card_id = cards[0]["card_id"]
        result = svc.calculate_reward(card_id=card_id, amount=1000, category="住宿")
        assert result["reward_amount"] >= 0.0

    def test_invalid_card_id(self, db_path):
        svc = CardRecommendService(db_path)
        with pytest.raises(ValueError):
            svc.calculate_reward(card_id=0, amount=1000, category="餐飲")

    def test_invalid_amount(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        with pytest.raises(ValueError):
            svc.calculate_reward(card_id=cards[0]["card_id"], amount=-100, category="餐飲")

    def test_invalid_category(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        with pytest.raises(ValueError):
            svc.calculate_reward(card_id=cards[0]["card_id"], amount=1000, category="")


class TestRecommendByCategory:
    def test_returns_sorted_list(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        results = svc.recommend_by_category(category="餐飲", amount=5000, region="日本")
        assert isinstance(results, list)
        if len(results) >= 2:
            assert results[0]["net_benefit"] >= results[-1]["net_benefit"]

    def test_invalid_category(self, db_path):
        svc = CardRecommendService(db_path)
        with pytest.raises(ValueError):
            svc.recommend_by_category(category="", amount=5000)

    def test_invalid_amount(self, db_path):
        svc = CardRecommendService(db_path)
        with pytest.raises(ValueError):
            svc.recommend_by_category(category="餐飲", amount=0)


class TestRecommendByTrip:
    def test_returns_list(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        results = svc.recommend_by_trip(trip_id=1)
        assert isinstance(results, list)

    def test_sorted_by_net_benefit(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        results = svc.recommend_by_trip(trip_id=1)
        if len(results) >= 2:
            assert results[0]["net_benefit"] >= results[-1]["net_benefit"]

    def test_invalid_trip_id(self, db_path):
        svc = CardRecommendService(db_path)
        with pytest.raises(ValueError):
            svc.recommend_by_trip(trip_id=0)


class TestCompareCards:
    def test_compare_returns_dict(self, db_path):
        seed_cards(db_path)
        svc = CardRecommendService(db_path)
        cards = svc.get_all_cards()
        if len(cards) >= 2:
            ids = [cards[0]["card_id"], cards[1]["card_id"]]
            result = svc.compare_cards(card_ids=ids, trip_id=1)
            assert "cards" in result
            assert "best_card_id" in result

    def test_empty_card_ids(self, db_path):
        svc = CardRecommendService(db_path)
        with pytest.raises(ValueError):
            svc.compare_cards(card_ids=[], trip_id=1)

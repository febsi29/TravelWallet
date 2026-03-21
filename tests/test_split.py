"""test_split.py - SplitEngine 單元測試"""

import pytest
from src.split import SplitEngine


class TestEqualSplit:
    def test_equal_split_three_users(self, db_path):
        engine = SplitEngine(db_path)
        # txn_id=1: 3000 JPY / 651 TWD，三人均分
        details = engine.add_equal_split(1, [1, 2, 3])
        assert len(details) == 3
        for d in details:
            assert abs(d["share_amount"] - 1000) < 1
            assert abs(d["ratio"] - 0.3333) < 0.001

    def test_equal_split_two_users(self, db_path):
        engine = SplitEngine(db_path)
        details = engine.add_equal_split(1, [1, 2])
        assert len(details) == 2
        for d in details:
            assert abs(d["share_amount"] - 1500) < 1

    def test_equal_split_invalid_txn_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_equal_split(9999, [1, 2])

    def test_equal_split_empty_users_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_equal_split(1, [])

    def test_equal_split_invalid_txn_id_type_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_equal_split("abc", [1, 2])


class TestRatioSplit:
    def test_ratio_split_valid(self, db_path):
        engine = SplitEngine(db_path)
        details = engine.add_ratio_split(2, {1: 0.5, 2: 0.3, 3: 0.2})
        assert len(details) == 3
        amounts = {d["user_id"]: d["share_amount"] for d in details}
        total_txn_amount = 8000  # txn_id=2
        assert abs(amounts[1] - total_txn_amount * 0.5) < 1

    def test_ratio_split_invalid_sum_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_ratio_split(2, {1: 0.5, 2: 0.3})  # 總和 0.8

    def test_ratio_split_empty_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_ratio_split(2, {})


class TestCustomSplit:
    def test_custom_split_valid(self, db_path):
        engine = SplitEngine(db_path)
        # txn_id=4: 5000 JPY，分配給兩人
        details = engine.add_custom_split(4, {1: 3000, 3: 2000})
        assert len(details) == 2
        amounts = {d["user_id"]: d["share_amount"] for d in details}
        assert amounts[1] == 3000
        assert amounts[3] == 2000

    def test_custom_split_wrong_total_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_custom_split(4, {1: 2000, 3: 2000})  # 總和 4000，不等於 5000

    def test_custom_split_empty_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.add_custom_split(4, {})


class TestNetBalances:
    def test_net_balances_returns_all_members(self, db_path):
        engine = SplitEngine(db_path)
        balances = engine.get_net_balances(1)
        assert len(balances) == 3  # 3 個旅行成員

    def test_net_balances_has_required_keys(self, db_path):
        engine = SplitEngine(db_path)
        balances = engine.get_net_balances(1)
        for uid, info in balances.items():
            assert "name" in info
            assert "paid" in info
            assert "owed" in info
            assert "balance" in info

    def test_net_balances_invalid_trip_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.get_net_balances(-1)


class TestSettle:
    def test_settle_trip_returns_list(self, db_path):
        engine = SplitEngine(db_path)
        transfers = engine.settle_trip(1)
        assert isinstance(transfers, list)

    def test_settle_transfer_has_required_keys(self, db_path):
        engine = SplitEngine(db_path)
        # 先建立分帳記錄
        engine.add_equal_split(1, [1, 2, 3])
        engine.add_equal_split(2, [1, 2, 3])
        transfers = engine.settle_trip(1)
        for t in transfers:
            assert "from_user" in t
            assert "to_user"   in t
            assert "amount"    in t

    def test_settle_minimizes_transfers(self, db_path):
        engine = SplitEngine(db_path)
        engine.add_equal_split(1, [1, 2, 3])
        engine.add_equal_split(2, [1, 2, 3])
        transfers = engine.settle_trip(1)
        # 3 人之間最多需要 2 筆轉帳
        assert len(transfers) <= 2

    def test_settle_invalid_trip_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.settle_trip(0)


class TestTripSummary:
    def test_summary_has_required_keys(self, db_path):
        engine = SplitEngine(db_path)
        summary = engine.get_trip_summary(1)
        assert "txn_count" in summary
        assert "total_twd" in summary
        assert "payers"    in summary
        assert "categories" in summary

    def test_summary_txn_count_correct(self, db_path):
        engine = SplitEngine(db_path)
        summary = engine.get_trip_summary(1)
        assert summary["txn_count"] == 7  # 種子資料有 7 筆交易

    def test_summary_invalid_trip_raises(self, db_path):
        engine = SplitEngine(db_path)
        with pytest.raises(ValueError):
            engine.get_trip_summary(-1)

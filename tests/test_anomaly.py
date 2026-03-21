"""test_anomaly.py - AnomalyDetector 單元測試"""

import pytest
from src.anomaly import AnomalyDetector


class TestDetectZscore:
    def test_returns_list(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_zscore(1)
        assert isinstance(results, list)

    def test_result_has_required_keys(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_zscore(1)
        for r in results:
            assert "txn_id"           in r
            assert "zscore"           in r
            assert "is_anomaly_zscore" in r

    def test_detects_large_purchase_as_anomaly(self, db_path):
        """txn_id=6：30000 JPY 的大額購物應被標記

        購物類別只有 2 筆資料（5000 / 30000），2 點時 Z-score 最大值 ≈ 0.71，
        使用 threshold=0.5 來測試偏差偵測能力。
        """
        detector = AnomalyDetector(db_path)
        results = detector.detect_zscore(1, threshold=0.5)
        anomalies = [r for r in results if r["is_anomaly_zscore"]]
        # 30000 JPY 的 Z-score ≈ 0.71，高於門檻 0.5
        assert len(anomalies) >= 1

    def test_sorted_by_absolute_zscore(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_zscore(1)
        zscores = [abs(r["zscore"]) for r in results]
        assert zscores == sorted(zscores, reverse=True)

    def test_invalid_threshold_raises(self, db_path):
        detector = AnomalyDetector(db_path)
        with pytest.raises(ValueError):
            detector.detect_zscore(1, threshold=0)

    def test_invalid_trip_id_raises(self, db_path):
        detector = AnomalyDetector(db_path)
        with pytest.raises(ValueError):
            detector.detect_zscore(-1)


class TestDetectIqr:
    def test_returns_list(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_iqr(1)
        assert isinstance(results, list)

    def test_result_has_required_keys(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_iqr(1)
        for r in results:
            assert "txn_id"        in r
            assert "is_anomaly_iqr" in r
            assert "iqr_bounds"    in r
            assert "iqr_reason"    in r

    def test_iqr_bounds_structure(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_iqr(1)
        if results:
            bounds = results[0]["iqr_bounds"]
            assert "lower" in bounds
            assert "upper" in bounds
            assert "q1"    in bounds
            assert "q3"    in bounds

    def test_invalid_multiplier_raises(self, db_path):
        detector = AnomalyDetector(db_path)
        with pytest.raises(ValueError):
            detector.detect_iqr(1, multiplier=-1)

    def test_detects_outlier(self, db_path):
        """30000 JPY 的交易應超過 IQR 上界"""
        detector = AnomalyDetector(db_path)
        results = detector.detect_iqr(1)
        anomalies = [r for r in results if r["is_anomaly_iqr"]]
        assert len(anomalies) >= 1


class TestDetectAll:
    def test_returns_list(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_all(1)
        assert isinstance(results, list)

    def test_combined_result_has_required_keys(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_all(1)
        for r in results:
            assert "txn_id"            in r
            assert "flags"             in r
            assert "is_anomaly"        in r
            assert "is_anomaly_zscore" in r
            assert "is_anomaly_iqr"    in r

    def test_flags_range(self, db_path):
        """flags 必須在 0~3 之間"""
        detector = AnomalyDetector(db_path)
        results = detector.detect_all(1)
        for r in results:
            assert 0 <= r["flags"] <= 3

    def test_is_anomaly_requires_majority(self, db_path):
        """is_anomaly = True 必須有 flags >= 2"""
        detector = AnomalyDetector(db_path)
        results = detector.detect_all(1)
        for r in results:
            if r["is_anomaly"]:
                assert r["flags"] >= 2

    def test_sorted_by_flags_descending(self, db_path):
        detector = AnomalyDetector(db_path)
        results = detector.detect_all(1)
        flags = [r["flags"] for r in results]
        assert flags == sorted(flags, reverse=True)

    def test_updates_database_flags(self, db_path):
        """detect_all 應更新 transactions 的 is_anomaly 欄位"""
        import sqlite3
        detector = AnomalyDetector(db_path)
        detector.detect_all(1)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE is_anomaly IS NOT NULL")
        count = cursor.fetchone()[0]
        conn.close()
        assert count > 0


class TestGetAnomalySummary:
    def test_returns_correct_structure(self, db_path):
        detector = AnomalyDetector(db_path)
        detector.detect_all(1)
        summary = detector.get_anomaly_summary(1)
        assert "total_transactions" in summary
        assert "anomaly_count"      in summary
        assert "anomaly_rate"       in summary
        assert "anomalies"          in summary

    def test_anomaly_rate_in_valid_range(self, db_path):
        detector = AnomalyDetector(db_path)
        detector.detect_all(1)
        summary = detector.get_anomaly_summary(1)
        assert 0 <= summary["anomaly_rate"] <= 100

    def test_total_matches_txn_count(self, db_path):
        detector = AnomalyDetector(db_path)
        summary = detector.get_anomaly_summary(1)
        assert summary["total_transactions"] == 7  # 種子資料 7 筆

    def test_invalid_trip_raises(self, db_path):
        detector = AnomalyDetector(db_path)
        with pytest.raises(ValueError):
            detector.get_anomaly_summary(0)

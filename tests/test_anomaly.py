import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.anomaly import AnomalyDetector

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'travel_wallet.db')

def test_zscore():
    d = AnomalyDetector(DB)
    r = d.detect_zscore(1)
    assert len(r) == 31
    print(f"PASS: Z-Score on 31 txns")

def test_iqr():
    d = AnomalyDetector(DB)
    r = d.detect_iqr(1)
    assert len(r) == 31
    print("PASS: IQR on 31 txns")

def test_combined():
    d = AnomalyDetector(DB)
    r = d.detect_all(1)
    assert len(r) == 31
    for x in r:
        if x["is_anomaly"]:
            assert x["flags"] >= 2
    print("PASS: combined majority vote")

if __name__ == "__main__":
    test_zscore()
    test_iqr()
    test_combined()
    print("All anomaly tests passed!")

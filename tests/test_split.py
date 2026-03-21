import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.split import SplitEngine

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'travel_wallet.db')

def test_net_balances():
    e = SplitEngine(DB)
    b = e.get_net_balances(1)
    assert len(b) == 4
    assert abs(sum(i["balance"] for i in b.values())) < 1
    print("PASS: net balances sum to zero")

def test_settle():
    e = SplitEngine(DB)
    t = e.settle_trip(1)
    assert 0 < len(t) <= 3
    for x in t:
        assert x["amount"] > 0
        assert x["from_user"] != x["to_user"]
    print(f"PASS: {len(t)} transfers")

def test_summary():
    e = SplitEngine(DB)
    s = e.get_trip_summary(1)
    assert s["txn_count"] == 31
    assert s["total_amount"] > 0
    print(f"PASS: {s['txn_count']} txns")

if __name__ == "__main__":
    test_net_balances()
    test_settle()
    test_summary()
    print("All split tests passed!")

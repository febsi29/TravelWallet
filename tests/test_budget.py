import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.budget import BudgetManager

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'travel_wallet.db')

def test_burndown():
    bm = BudgetManager(DB)
    bd = bm.get_burndown(1)
    assert len(bd["burndown"]) == 5
    print("PASS: 5 days burndown")

def test_prediction():
    bm = BudgetManager(DB)
    p = bm.predict_remaining(1, current_day=3)
    assert p["predicted_total"] > 0
    assert p["daily_rate"] > 0
    print(f"PASS: predicted NT${p['predicted_total']:,}")

def test_health():
    bm = BudgetManager(DB)
    h = bm.assess_health(1)
    assert 0 <= h["score"] <= 100
    print(f"PASS: score {h['score']}/100")

if __name__ == "__main__":
    test_burndown()
    test_prediction()
    test_health()
    print("All budget tests passed!")

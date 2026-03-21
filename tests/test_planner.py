import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.planner import TripPlanner, DESTINATION_FACTORS

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'travel_wallet.db')

def test_suggest():
    p = TripPlanner(DB)
    plan = p.suggest_budget("", 5, 4)
    s = plan["tiers"]["standard"]
    assert s["total_per_person"] > 0
    assert s["total_group"] == s["total_per_person"] * 4
    print(f"PASS: Japan NT${s['total_per_person']:,}/person")

def test_tier_order():
    p = TripPlanner(DB)
    plan = p.suggest_budget("", 5, 1)
    b = plan["tiers"]["budget"]["total_per_person"]
    s = plan["tiers"]["standard"]["total_per_person"]
    m = plan["tiers"]["premium"]["total_per_person"]
    assert b < s < m
    print("PASS: budget < standard < premium")

def test_all_dests():
    p = TripPlanner(DB)
    for d in DESTINATION_FACTORS:
        plan = p.suggest_budget(d, 3, 1)
        assert plan["tiers"]["standard"]["total_per_person"] > 0
    print(f"PASS: all {len(DESTINATION_FACTORS)} destinations")

if __name__ == "__main__":
    test_suggest()
    test_tier_order()
    test_all_dests()
    print("All planner tests passed!")

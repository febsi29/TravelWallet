import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.currency import CurrencyManager, FALLBACK_RATES

def test_fallback():
    for code in ["JPY","USD","KRW","EUR"]:
        assert FALLBACK_RATES[code] > 0
    print("PASS: fallback rates valid")

def test_convert():
    cm = CurrencyManager()
    r = cm.convert(10000, "JPY", "TWD")
    assert r["amount"] > 0
    print(f"PASS: 10000 JPY = NT${r['amount']:,.0f}")

def test_same():
    cm = CurrencyManager()
    r = cm.convert(1000, "TWD", "TWD")
    assert r["amount"] == 1000
    print("PASS: same currency")

if __name__ == "__main__":
    test_fallback()
    test_convert()
    test_same()
    print("All currency tests passed!")

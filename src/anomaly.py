"""
anomaly.py - Anomaly Detection Module

Features:
- Z-Score statistical detection (per category)
- IQR (Interquartile Range) detection
- Isolation Forest (unsupervised ML)
- Multi-dimensional analysis (amount, time, category)
- Anomaly scoring and labeling

Usage:
  from src.anomaly import AnomalyDetector
  detector = AnomalyDetector(db_path)
  results = detector.detect_all(trip_id=1)
"""

import sqlite3
import os
import math
from collections import defaultdict
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")


class AnomalyDetector:

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn, conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_transactions(self, trip_id: int) -> list:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT txn_id, amount, amount_twd, currency_code, category,
                       txn_datetime, location, payment_method, description
                FROM transactions
                WHERE trip_id = ?
                ORDER BY txn_datetime
            """, (trip_id,))
            columns = ["txn_id", "amount", "amount_twd", "currency_code", "category",
                       "txn_datetime", "location", "payment_method", "description"]
            return [dict(zip(columns, r)) for r in cursor.fetchall()]

    # ============================================================
    #  Method 1: Z-Score (per category)
    # ============================================================

    def detect_zscore(self, trip_id: int, threshold: float = 2.0) -> list:
        """
        Z-Score detection: flag transactions that deviate more than
        'threshold' standard deviations from their category mean.

        Z = (x - mean) / std

        If |Z| > threshold, it's anomalous.
        """
        if threshold <= 0:
            raise ValueError(f"threshold  0: {threshold}")

        txns = self._get_transactions(trip_id)
        if not txns:
            return []

        by_category = defaultdict(list)
        for t in txns:
            by_category[t["category"]].append(t)

        results = []
        for category, cat_txns in by_category.items():
            amounts = [t["amount_twd"] for t in cat_txns]
            n = len(amounts)

            if n < 2:
                for t in cat_txns:
                    t["zscore"] = 0
                    t["is_anomaly_zscore"] = False
                    t["zscore_reason"] = "insufficient data"
                    results.append(t)
                continue

            mean = sum(amounts) / n
            variance = sum((x - mean) ** 2 for x in amounts) / (n - 1)
            std = math.sqrt(variance) if variance > 0 else 1

            for t in cat_txns:
                z = (t["amount_twd"] - mean) / std if std > 0 else 0
                t["zscore"] = round(z, 2)
                t["is_anomaly_zscore"] = abs(z) > threshold
                t["category_mean"] = round(mean)
                t["category_std"] = round(std)

                if t["is_anomaly_zscore"]:
                    direction = "above" if z > 0 else "below"
                    t["zscore_reason"] = (
                        f"{category} avg NT${mean:,.0f}, this NT${t['amount_twd']:,.0f}, "
                        f"Z={z:+.2f} ({direction} {threshold} std)"
                    )
                else:
                    t["zscore_reason"] = "normal"

                results.append(t)

        results.sort(key=lambda x: abs(x["zscore"]), reverse=True)
        return results

    # ============================================================
    #  Method 2: IQR (Interquartile Range)
    # ============================================================

    def detect_iqr(self, trip_id: int, multiplier: float = 1.5) -> list:
        """
        IQR detection: flag transactions outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]

        IQR = Q3 - Q1
        Lower bound = Q1 - multiplier * IQR
        Upper bound = Q3 + multiplier * IQR
        """
        if multiplier <= 0:
            raise ValueError(f"multiplier  0: {multiplier}")

        txns = self._get_transactions(trip_id)
        if not txns:
            return []

        amounts = sorted([t["amount_twd"] for t in txns])
        n = len(amounts)

        q1 = amounts[n // 4]
        q3 = amounts[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        for t in txns:
            amt = t["amount_twd"]
            t["is_anomaly_iqr"] = amt < lower or amt > upper
            t["iqr_bounds"] = {"lower": round(lower), "upper": round(upper), "q1": q1, "q3": q3, "iqr": iqr}

            if amt > upper:
                t["iqr_reason"] = f"NT${amt:,.0f} exceeds upper bound NT${upper:,.0f}"
            elif amt < lower:
                t["iqr_reason"] = f"NT${amt:,.0f} below lower bound NT${lower:,.0f}"
            else:
                t["iqr_reason"] = "normal"

        txns.sort(key=lambda x: x["amount_twd"], reverse=True)
        return txns

    # ============================================================
    #  Method 3: Isolation Forest (ML)
    # ============================================================

    def detect_isolation_forest(self, trip_id: int, contamination: float = 0.1) -> list:
        """
        Isolation Forest: unsupervised ML anomaly detection.

        Features used:
        - amount_twd (spending amount)
        - hour_of_day (time of transaction)
        - category_encoded (spending category)

        contamination: expected proportion of anomalies (default 10%)
        """
        if not 0 < contamination < 0.5:
            raise ValueError(f"contamination  (0, 0.5) : {contamination}")

        txns = self._get_transactions(trip_id)
        if not txns:
            return []

        try:
            from sklearn.ensemble import IsolationForest
            import numpy as np
        except ImportError:
            print("scikit-learn not installed, skipping Isolation Forest")
            for t in txns:
                t["is_anomaly_if"] = False
                t["if_score"] = 0
                t["if_reason"] = "scikit-learn not available"
            return txns

        categories = list(set(t["category"] for t in txns))
        cat_map = {c: i for i, c in enumerate(categories)}

        features = []
        for t in txns:
            hour = int(t["txn_datetime"].split(" ")[1].split(":")[0]) if " " in t["txn_datetime"] else 12
            features.append([
                t["amount_twd"],
                hour,
                cat_map[t["category"]],
            ])

        X = np.array(features)

        for col in range(X.shape[1]):
            col_std = X[:, col].std()
            if col_std > 0:
                X[:, col] = (X[:, col] - X[:, col].mean()) / col_std

        model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        labels = model.fit_predict(X)
        scores = model.decision_function(X)

        for i, t in enumerate(txns):
            t["is_anomaly_if"] = int(labels[i]) == -1
            t["if_score"] = round(float(scores[i]), 4)

            if t["is_anomaly_if"]:
                t["if_reason"] = f"anomaly score={t['if_score']:.4f} (negative = more anomalous)"
            else:
                t["if_reason"] = "normal"

        txns.sort(key=lambda x: x["if_score"])
        return txns

    # ============================================================
    #  Combined Detection
    # ============================================================

    def detect_all(
        self,
        trip_id: int,
        zscore_threshold: float = 2.0,
        iqr_multiplier: float = 1.5,
        if_contamination: float = 0.1,
    ) -> list:
        """
        Run all three detection methods and combine results.

        A transaction is flagged as anomalous if at least 2 out of 3 methods agree.
        """
        zscore_results = {t["txn_id"]: t for t in self.detect_zscore(trip_id, zscore_threshold)}
        iqr_results = {t["txn_id"]: t for t in self.detect_iqr(trip_id, iqr_multiplier)}
        if_results = {t["txn_id"]: t for t in self.detect_isolation_forest(trip_id, if_contamination)}

        combined = []
        all_ids = set(zscore_results.keys()) | set(iqr_results.keys()) | set(if_results.keys())

        for txn_id in all_ids:
            z = zscore_results.get(txn_id, {})
            iq = iqr_results.get(txn_id, {})
            iso = if_results.get(txn_id, {})

            base = z or iq or iso

            flags = sum([
                z.get("is_anomaly_zscore", False),
                iq.get("is_anomaly_iqr", False),
                iso.get("is_anomaly_if", False),
            ])

            entry = {
                "txn_id": txn_id,
                "amount_twd": base.get("amount_twd", 0),
                "category": base.get("category", ""),
                "description": base.get("description", ""),
                "txn_datetime": base.get("txn_datetime", ""),
                "location": base.get("location", ""),
                "zscore": z.get("zscore", 0),
                "is_anomaly_zscore": z.get("is_anomaly_zscore", False),
                "is_anomaly_iqr": iq.get("is_anomaly_iqr", False),
                "is_anomaly_if": iso.get("is_anomaly_if", False),
                "if_score": iso.get("if_score", 0),
                "flags": flags,
                "is_anomaly": flags >= 2,
            }

            combined.append(entry)

        combined.sort(key=lambda x: x["flags"], reverse=True)
        self._update_anomaly_flags(combined)
        return combined

    def _update_anomaly_flags(self, results: list) -> None:
        with self._db() as (conn, cursor):
            for r in results:
                cursor.execute("""
                    UPDATE transactions
                    SET is_anomaly = ?, anomaly_score = ?
                    WHERE txn_id = ?
                """, (1 if r["is_anomaly"] else 0, r["if_score"], r["txn_id"]))

    # ============================================================
    #  Summary
    # ============================================================

    def get_anomaly_summary(self, trip_id: int) -> dict:
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id : {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT COUNT(*) FROM transactions
                WHERE trip_id = ? AND is_anomaly = 1
            """, (trip_id,))
            anomaly_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM transactions WHERE trip_id = ?", (trip_id,))
            total_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT txn_id, amount_twd, category, description, location, anomaly_score
                FROM transactions
                WHERE trip_id = ? AND is_anomaly = 1
                ORDER BY amount_twd DESC
            """, (trip_id,))
            anomalies = [
                {"txn_id": r[0], "amount_twd": r[1], "category": r[2],
                 "description": r[3], "location": r[4], "score": r[5]}
                for r in cursor.fetchall()
            ]

        return {
            "total_transactions": total_count,
            "anomaly_count": anomaly_count,
            "anomaly_rate": round(anomaly_count / total_count * 100, 1) if total_count > 0 else 0,
            "anomalies": anomalies,
        }


if __name__ == "__main__":
    print("TravelWallet - Anomaly Detection Test")
    print("=" * 60)

    detector = AnomalyDetector()
    trip_id = 1

    print("\n[Method 1] Z-Score Detection (threshold=2.0)")
    print("-" * 60)
    zscore = detector.detect_zscore(trip_id)
    flagged_z = [t for t in zscore if t["is_anomaly_zscore"]]
    print(f"  Flagged: {len(flagged_z)} / {len(zscore)} transactions")
    for t in flagged_z:
        print(f"    txn#{t['txn_id']} {t['category']} NT${t['amount_twd']:,} Z={t['zscore']:+.2f}")

    print(f"\n[Method 2] IQR Detection (multiplier=1.5)")
    print("-" * 60)
    iqr = detector.detect_iqr(trip_id)
    flagged_iq = [t for t in iqr if t["is_anomaly_iqr"]]
    print(f"  Flagged: {len(flagged_iq)} / {len(iqr)} transactions")

    print(f"\n[Combined] Majority Vote (2/3 methods agree)")
    print("=" * 60)
    combined = detector.detect_all(trip_id)
    anomalies = [c for c in combined if c["is_anomaly"]]
    print(f"  Final anomalies: {len(anomalies)} / {len(combined)} transactions")

    print("\nDone!")

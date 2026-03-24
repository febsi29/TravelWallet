"""
risk_dashboard.py - 風險評估儀表板模組

功能：
- 匯率風險評估（歷史波動率分析）
- 預算風險評估（整合 BudgetManager）
- 異常消費風險評估（整合 AnomalyDetector）
- 信用風險評估（整合 CreditScoreEngine）
- 綜合風險指數計算（加權平均）
- 改善建議產生

使用方式：
  from src.risk_dashboard import RiskDashboard
  rd = RiskDashboard(db_path)
  result = rd.assess_overall(user_id=1, trip_id=1)
"""

import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# 各維度風險的加權比例（總和 = 1.0）
RISK_WEIGHTS = {
    "fx":      0.25,
    "budget":  0.30,
    "anomaly": 0.25,
    "credit":  0.20,
}


def _risk_level(score: float) -> str:
    """將風險分數（0-100）轉換為風險等級"""
    if score <= 30:
        return "低"
    elif score <= 60:
        return "中等"
    else:
        return "高"


class RiskDashboard:
    """旅遊財務風險評估儀表板"""

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

    def _get_trip_currency(self, trip_id: int) -> str:
        with self._db() as (conn, cursor):
            cursor.execute("SELECT currency_code FROM trips WHERE trip_id = ?", (trip_id,))
            row = cursor.fetchone()
        return row[0] if row else "JPY"

    # ============================================================
    #  四維度風險評估
    # ============================================================

    def assess_fx_risk(self, trip_id: int) -> dict:
        """
        評估匯率風險

        以歷史匯率波動率計算：
        - volatility = std_dev / mean（變異係數）
        - risk_score = min(100, volatility * 1000)

        參數：
            trip_id: 旅行 ID

        回傳：
            dict: {risk_score, level, message, volatility}
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        currency = self._get_trip_currency(trip_id)

        if currency == "TWD":
            return {
                "risk_score": 0.0,
                "level": "低",
                "message": "台幣旅行無匯率風險",
                "volatility": 0.0,
                "currency": currency,
            }

        try:
            from src.fx_strategy import FxStrategy
            fx = FxStrategy(self.db_path)
            history = fx.get_history(currency, 30)
        except Exception:
            history = []

        if len(history) < 3:
            return {
                "risk_score": 50.0,
                "level": "中等",
                "message": "無足夠歷史匯率資料，採用預設中等風險",
                "volatility": 0.0,
                "currency": currency,
            }

        rates = [h["rate"] for h in history]
        mean = sum(rates) / len(rates)
        variance = sum((r - mean) ** 2 for r in rates) / len(rates)
        std_dev = variance ** 0.5
        volatility = std_dev / mean if mean > 0 else 0

        risk_score = min(100.0, round(volatility * 1000, 2))

        # 若當前匯率偏離均值 > 5%，額外加分
        current_rate = rates[-1]
        deviation = abs(current_rate - mean) / mean if mean > 0 else 0
        if deviation > 0.05:
            risk_score = min(100.0, risk_score + 20)

        return {
            "risk_score": risk_score,
            "level": _risk_level(risk_score),
            "message": f"{currency} 近 30 日匯率波動率 {volatility*100:.2f}%",
            "volatility": round(volatility * 100, 2),
            "currency": currency,
        }

    def assess_budget_risk(self, trip_id: int) -> dict:
        """
        評估預算風險

        使用 BudgetManager.assess_health() 的健康分數：
        risk_score = 100 - health_score

        參數：
            trip_id: 旅行 ID

        回傳：
            dict: {risk_score, level, message, usage_ratio}
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        try:
            from src.budget import BudgetManager
            bm = BudgetManager(self.db_path)
            health = bm.assess_health(trip_id)
        except Exception:
            return {"risk_score": 50.0, "level": "中等", "message": "無法評估預算健康", "usage_ratio": 0}

        health_score = health.get("score", 50)
        usage_ratio = health.get("usage_ratio", 0)
        risk_score = max(0.0, float(100 - health_score))

        return {
            "risk_score": risk_score,
            "level": _risk_level(risk_score),
            "message": f"預算使用率 {usage_ratio:.1f}%，健康分 {health_score}/100",
            "usage_ratio": usage_ratio,
        }

    def assess_anomaly_risk(self, trip_id: int) -> dict:
        """
        評估異常消費風險

        anomaly_rate = 異常交易筆數 / 總交易筆數
        risk_score = min(100, anomaly_rate * 300)

        參數：
            trip_id: 旅行 ID

        回傳：
            dict: {risk_score, level, message, anomaly_rate}
        """
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(is_anomaly), 0)
                FROM transactions WHERE trip_id = ?
            """, (trip_id,))
            total, anomaly_count = cursor.fetchone()

        if total == 0:
            return {
                "risk_score": 0.0,
                "level": "低",
                "message": "尚無交易紀錄",
                "anomaly_rate": 0.0,
            }

        anomaly_rate = anomaly_count / total
        risk_score = min(100.0, round(anomaly_rate * 300, 2))

        return {
            "risk_score": risk_score,
            "level": _risk_level(risk_score),
            "message": f"共 {total} 筆交易，{int(anomaly_count)} 筆異常（{anomaly_rate*100:.1f}%）",
            "anomaly_rate": round(anomaly_rate * 100, 2),
        }

    def assess_credit_risk(self, user_id: int, trip_id: int) -> dict:
        """
        評估信用風險

        使用 CreditScoreEngine.evaluate()：
        risk_score = 100 - credit_score

        參數：
            user_id: 使用者 ID
            trip_id: 旅行 ID

        回傳：
            dict: {risk_score, level, credit_score, grade}
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        try:
            from src.credit_score import CreditScoreEngine
            engine = CreditScoreEngine(self.db_path)
            result = engine.evaluate(user_id, trip_id)
        except Exception:
            return {
                "risk_score": 50.0,
                "level": "中等",
                "credit_score": 50,
                "grade": "C",
            }

        credit_score = result.get("overall_score", 50)
        risk_score = max(0.0, float(100 - credit_score))
        grade = result.get("grade", "C")

        return {
            "risk_score": risk_score,
            "level": _risk_level(risk_score),
            "credit_score": credit_score,
            "grade": grade,
            "message": f"財務健康評分 {credit_score}/100（{grade} 級）",
        }

    # ============================================================
    #  綜合風險評估
    # ============================================================

    def assess_overall(self, user_id: int, trip_id: int) -> dict:
        """
        執行綜合風險評估（四維度加權平均）

        權重：匯率 25%、預算 30%、異常 25%、信用 20%

        參數：
            user_id: 使用者 ID
            trip_id: 旅行 ID

        回傳：
            dict: {overall_risk, health_index, fx, budget, anomaly, credit, recommendations}
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(trip_id, int) or trip_id <= 0:
            raise ValueError(f"trip_id 必須為正整數，收到: {trip_id!r}")

        fx_result      = self.assess_fx_risk(trip_id)
        budget_result  = self.assess_budget_risk(trip_id)
        anomaly_result = self.assess_anomaly_risk(trip_id)
        credit_result  = self.assess_credit_risk(user_id, trip_id)

        overall_risk = round(
            fx_result["risk_score"]      * RISK_WEIGHTS["fx"]      +
            budget_result["risk_score"]  * RISK_WEIGHTS["budget"]  +
            anomaly_result["risk_score"] * RISK_WEIGHTS["anomaly"] +
            credit_result["risk_score"]  * RISK_WEIGHTS["credit"],
            2,
        )

        if overall_risk <= 30:
            health_index = "A"
        elif overall_risk <= 50:
            health_index = "B"
        elif overall_risk <= 70:
            health_index = "C"
        elif overall_risk <= 85:
            health_index = "D"
        else:
            health_index = "F"

        assessment = {
            "overall_risk": overall_risk,
            "health_index": health_index,
            "fx":      fx_result,
            "budget":  budget_result,
            "anomaly": anomaly_result,
            "credit":  credit_result,
        }

        recommendations = self.generate_recommendations(assessment)
        assessment["recommendations"] = recommendations

        # 儲存評估結果
        with self._db() as (conn, cursor):
            cursor.execute("""
                INSERT INTO risk_assessments
                (user_id, trip_id, overall_risk, fx_risk, budget_risk,
                 anomaly_risk, credit_risk, health_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, trip_id, overall_risk,
                fx_result["risk_score"],
                budget_result["risk_score"],
                anomaly_result["risk_score"],
                credit_result["risk_score"],
                health_index,
            ))

        return assessment

    def generate_recommendations(self, assessment: dict) -> list:
        """
        根據各維度風險產生改善建議

        參數：
            assessment: assess_overall() 回傳的評估結果

        回傳：
            list[str]: 改善建議文字列表
        """
        recs = []

        budget_risk  = assessment.get("budget",  {}).get("risk_score", 0)
        anomaly_risk = assessment.get("anomaly", {}).get("risk_score", 0)
        fx_risk      = assessment.get("fx",      {}).get("risk_score", 0)
        credit_risk  = assessment.get("credit",  {}).get("risk_score", 0)

        if budget_risk > 70:
            recs.append("預算嚴重超支：建議每日消費控制在預算的 80% 以內，並使用「支出預測」功能追蹤消費軌跡")
        elif budget_risk > 40:
            recs.append("預算偏高：建議減少非必要的購物支出，重新規劃剩餘旅程的每日預算")

        if anomaly_risk > 60:
            recs.append("異常消費偏多：請至「異常偵測」頁面確認可疑交易，並檢查信用卡是否有未授權消費")
        elif anomaly_risk > 30:
            recs.append("存在部分異常消費：建議定期檢視交易明細，確認所有消費均為本人操作")

        if fx_risk > 60:
            recs.append("匯率波動劇烈：建議分批換匯以降低風險，並使用「匯率到價提醒」鎖定目標匯率")
        elif fx_risk > 30:
            recs.append("匯率有一定波動：可使用「換匯策略」功能選擇較佳換匯時機")

        if credit_risk > 60:
            recs.append("財務健康評分偏低：建議加快分帳結算速度，並維持消費類別的均衡分佈")
        elif credit_risk > 30:
            recs.append("財務健康仍有改善空間：及時結算分帳，保持良好的消費習慣")

        if not recs:
            recs.append("財務狀況良好，繼續維持現有消費習慣")

        return recs

    # ============================================================
    #  歷史紀錄查詢
    # ============================================================

    def get_risk_history(self, user_id: int, limit: int = 10) -> list:
        """
        查詢風險評估歷史紀錄

        參數：
            user_id: 使用者 ID
            limit: 最多回傳筆數

        回傳：
            list[dict]: 評估紀錄列表
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id 必須為正整數，收到: {user_id!r}")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit 必須為正整數，收到: {limit!r}")

        with self._db() as (conn, cursor):
            cursor.execute("""
                SELECT ra.assessment_id, ra.trip_id, t.trip_name,
                       ra.overall_risk, ra.fx_risk, ra.budget_risk,
                       ra.anomaly_risk, ra.credit_risk, ra.health_index, ra.assessed_at
                FROM risk_assessments ra
                LEFT JOIN trips t ON ra.trip_id = t.trip_id
                WHERE ra.user_id = ?
                ORDER BY ra.assessed_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

        keys = ["assessment_id", "trip_id", "trip_name", "overall_risk",
                "fx_risk", "budget_risk", "anomaly_risk", "credit_risk",
                "health_index", "assessed_at"]
        return [dict(zip(keys, r)) for r in rows]

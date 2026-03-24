"""
ai_agent.py - Anthropic Claude AI Agent 服務層

功能：
1. Claude Vision OCR：比 pytesseract 更準確的收據辨識
2. 智慧財務顧問：對話式旅行消費分析
3. 異常交易說明：LLM 生成自然語言解釋
4. 信用卡推薦對話：多輪對話個人化推薦
5. 預算規劃 Agent：個人化旅行預算生成

API Key 從環境變數 ANTHROPIC_API_KEY 讀取，絕不硬編碼。
無 API Key 時所有方法優雅降級，返回規則型結果。
"""

import os
import re
import json
import base64
import logging
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "travel_wallet.db")

# 模型常數
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


# ============================================================
#  底層 HTTP 客戶端
# ============================================================

class ClaudeClient:
    """
    封裝 Anthropic Messages API 的輕量 HTTP 客戶端。
    使用 requests，不依賴 anthropic SDK。
    """

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.available = bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    def chat(
        self,
        messages: list,
        system: str = "",
        model: str = MODEL_HAIKU,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str | None:
        """
        呼叫 Anthropic Messages API。

        回傳：
            str: 模型回覆文字
            None: API 不可用或呼叫失敗
        """
        if not self.available:
            return None
        try:
            import requests
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                payload["system"] = system

            resp = requests.post(
                ANTHROPIC_API_URL,
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
        except Exception as e:
            logger.error(f"Claude API 呼叫失敗: {e}")
            return None

    def vision_chat(
        self,
        image_b64: str,
        image_media_type: str,
        prompt: str,
        system: str = "",
        model: str = MODEL_HAIKU,
        max_tokens: int = 1024,
    ) -> str | None:
        """
        呼叫 Vision API（帶圖片的 Messages）。

        回傳：
            str: 模型回覆文字
            None: 失敗時
        """
        if not self.available:
            return None
        try:
            import requests
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }]
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                payload["system"] = system

            resp = requests.post(
                ANTHROPIC_API_URL,
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
        except Exception as e:
            logger.error(f"Claude Vision API 呼叫失敗: {e}")
            return None


# ============================================================
#  功能一：收據 Vision OCR 解析器
# ============================================================

class ReceiptVisionParser:
    """
    使用 Claude Vision API 解析收據圖片。
    作為 pytesseract 的主要 OCR 引擎（更準確、支援多語言）。
    """

    _SYSTEM = """你是一個收據資訊提取專家。
從收據圖片中提取以下資訊，只回傳 JSON，不加任何說明文字：
{
  "raw_text": "收據文字原文（盡量完整）",
  "merchant": "商家名稱",
  "amount": 數字或null（只取最終總金額），
  "currency": "ISO幣別代碼或null（¥→JPY、$→USD、NT$→TWD、₩→KRW、฿→THB）",
  "date": "YYYY-MM-DD格式或null",
  "category": "餐飲或交通或住宿或購物或娛樂或其他",
  "confidence": 0到1之間的小數
}"""

    def __init__(self, client: ClaudeClient):
        self.client = client

    def parse_image(self, image_path: str) -> dict | None:
        """
        用 Claude Vision 解析收據圖片。

        回傳：
            dict: 包含 raw_text/merchant/amount/currency/date/category/confidence
            None: API 不可用或解析失敗
        """
        if not self.client.available:
            return None
        try:
            b64, media_type = self._read_image_b64(image_path)
            text = self.client.vision_chat(
                image_b64=b64,
                image_media_type=media_type,
                prompt="請提取此收據的所有資訊。",
                system=self._SYSTEM,
            )
            if not text:
                return None
            return self._parse_json_response(text)
        except Exception as e:
            logger.error(f"Vision OCR 失敗: {e}")
            return None

    def _read_image_b64(self, image_path: str) -> tuple:
        ext = os.path.splitext(image_path)[1].lower()
        media_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        media_type = media_map.get(ext, "image/jpeg")
        with open(image_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        return b64, media_type

    def _parse_json_response(self, text: str) -> dict:
        # 找出 JSON block（可能被 markdown code fence 包住）
        json_match = re.search(r"\{[\s\S]+\}", text)
        if not json_match:
            return {}
        data = json.loads(json_match.group())
        # 確保 amount 為 float
        if data.get("amount") is not None:
            try:
                data["amount"] = float(data["amount"])
            except (ValueError, TypeError):
                data["amount"] = None
        return data


# ============================================================
#  功能二：智慧財務顧問
# ============================================================

class FinancialAdvisorAgent:
    """
    對話式旅行財務顧問。
    使用 claude-sonnet-4-6 進行深度分析，維護多輪對話歷史。
    """

    _SYSTEM_TEMPLATE = """你是 TravelWallet 的旅行財務顧問，專門協助台灣旅客分析旅遊消費。

當前旅行資料：
{context}

分析原則：
- 使用繁體中文回覆
- 提供具體數字依據，不做空泛建議
- 與全國平均（每人每日約 NT$7,714）比較
- 指出節省空間和消費風險
- 對話風格：專業但親切
- 不使用 emoji
- 每次回覆不超過 300 字"""

    def __init__(self, client: ClaudeClient, db_path: str):
        self.client = client
        self.db_path = db_path

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

    def build_context(self, trip_id: int) -> str:
        """從資料庫彙整旅行資料，作為 system prompt 的 context。"""
        parts = []
        try:
            with self._db() as (conn, cursor):
                cursor.execute(
                    "SELECT trip_name, destination, start_date, end_date, total_budget, currency_code "
                    "FROM trips WHERE trip_id = ?", (trip_id,)
                )
                row = cursor.fetchone()
                if row:
                    parts.append(
                        f"旅行：{row[0]}，目的地：{row[1]}，"
                        f"日期：{row[2]} ~ {row[3]}，"
                        f"總預算：NT${row[4]:,.0f}，幣別：{row[5]}"
                    )

                cursor.execute(
                    "SELECT category, COUNT(*) as cnt, SUM(amount_twd) as total "
                    "FROM transactions WHERE trip_id = ? GROUP BY category ORDER BY total DESC",
                    (trip_id,)
                )
                cats = cursor.fetchall()
                if cats:
                    total_all = sum(c[2] for c in cats)
                    cat_lines = [
                        f"  {c[0]}: NT${c[2]:,.0f}（{c[2]/total_all*100:.1f}%，{c[1]}筆）"
                        for c in cats
                    ]
                    parts.append("各類別消費：\n" + "\n".join(cat_lines))
                    parts.append(f"總消費：NT${total_all:,.0f}")

                cursor.execute(
                    "SELECT COUNT(*) FROM transactions WHERE trip_id = ? AND is_anomaly = 1",
                    (trip_id,)
                )
                anomaly_count = cursor.fetchone()[0]
                if anomaly_count > 0:
                    parts.append(f"異常交易：{anomaly_count} 筆")
        except Exception as e:
            logger.warning(f"build_context 失敗: {e}")

        return "\n".join(parts) if parts else "（尚無旅行資料）"

    def chat(self, user_message: str, trip_id: int, history: list) -> str:
        """
        財務顧問多輪對話。

        降級：呼叫 _fallback_advice 返回規則型分析。
        """
        context = self.build_context(trip_id)
        system = self._SYSTEM_TEMPLATE.format(context=context)

        messages = []
        for msg in history[-10:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        reply = self.client.chat(
            messages=messages,
            system=system,
            model=MODEL_SONNET,
            max_tokens=512,
            temperature=0.5,
        )
        if reply:
            return reply
        return self._fallback_advice(trip_id, user_message)

    def _fallback_advice(self, trip_id: int, question: str) -> str:
        """無 API 時的規則型財務建議。"""
        try:
            from src.budget import BudgetManager
            from src.analytics import Analytics
            bm = BudgetManager(self.db_path)
            ana = Analytics(self.db_path)
            health = bm.assess_health(trip_id)
            pvn = ana.personal_vs_national(trip_id)
            p = pvn["personal"]
            c = pvn["comparison"]
            return (
                f"**預算健康評估（規則引擎）**\n\n"
                f"- 健康分數：{health['score']}/100（{health['status']}）\n"
                f"- 已使用：NT${health['total_spent']:,}（{health['usage_ratio']}%）\n"
                f"- 剩餘預算：NT${health.get('remaining', 0):,}\n\n"
                f"**與全國平均比較**\n"
                f"- 本次每人消費：NT${p['per_person_total']:,}\n"
                f"- 差距：{c['diff_pct']:+.1f}%（{c['verdict']}）"
            )
        except Exception:
            return "目前無法提供詳細分析，請確認旅行資料是否完整。"


# ============================================================
#  功能三：異常交易 LLM 說明
# ============================================================

class AnomalyExplainer:
    """
    為 AnomalyDetector 偵測到的異常交易生成自然語言說明。
    使用 claude-haiku（速度優先、成本低）。
    """

    _SYSTEM = """你是旅行帳務分析師。根據給定的異常交易資料，
用繁體中文撰寫一段簡潔（50-100字）的說明，解釋：
1. 為什麼這筆交易被判定為異常
2. 可能的原因
3. 建議使用者確認的行動
不使用 emoji，直接輸出說明文字，不加標題或前綴。"""

    def __init__(self, client: ClaudeClient):
        self.client = client

    def explain(self, transaction: dict, stats: dict | None = None) -> str:
        """
        為單筆異常交易生成說明。

        降級：根據 zscore/flags 返回模板文字。
        """
        prompt = self._build_prompt(transaction, stats or {})
        reply = self.client.chat(
            messages=[{"role": "user", "content": prompt}],
            system=self._SYSTEM,
            model=MODEL_HAIKU,
            max_tokens=200,
            temperature=0.4,
        )
        if reply:
            return reply.strip()
        return self._fallback_explain(transaction)

    def explain_batch(self, anomalies: list, max_count: int = 5) -> list:
        """
        批次為多筆異常交易生成說明。
        回傳原始 anomaly dict + "explanation" 欄位。
        """
        flagged = [a for a in anomalies if a.get("is_anomaly")][:max_count]
        result = []
        for item in flagged:
            explanation = self.explain(item)
            result.append({**item, "explanation": explanation})
        return result

    def _build_prompt(self, t: dict, stats: dict) -> str:
        cat_mean = stats.get("category_mean", 0)
        cat_std = stats.get("category_std", 0)
        flags = t.get("flags", 0)
        zscore = t.get("zscore", 0)
        return (
            f"異常交易資料：\n"
            f"- 金額：NT${t.get('amount_twd', 0):,}\n"
            f"- 類別：{t.get('category', '--')}\n"
            f"- 描述：{t.get('description', '--')}\n"
            f"- 時間：{t.get('txn_datetime', '--')}\n"
            f"- Z-Score：{zscore:.2f}（該類別平均：NT${cat_mean:,.0f}，標準差：NT${cat_std:,.0f}）\n"
            f"- 觸發方法數：{flags}/3（Z-Score、IQR、Isolation Forest）\n"
            f"\n請解釋為何此交易被判為異常，並給出建議。"
        )

    def _fallback_explain(self, t: dict) -> str:
        zscore = t.get("zscore", 0)
        flags = t.get("flags", 0)
        amount = t.get("amount_twd", 0)
        category = t.get("category", "此類別")
        if flags >= 3:
            return (
                f"此筆 NT${amount:,} 的{category}消費同時被三種統計方法（Z-Score、IQR、Isolation Forest）"
                f"標記為異常，Z-Score 達 {zscore:.1f}，顯著偏離正常消費水準，建議確認交易真實性。"
            )
        if zscore > 2.0:
            return (
                f"此筆消費 NT${amount:,} 的 Z-Score 為 {zscore:.1f}，"
                f"表示金額遠高於{category}類別的平均水準，可能為特殊消費或輸入錯誤，建議核對。"
            )
        return (
            f"此筆 NT${amount:,} 的{category}消費被部分統計方法標記為異常，"
            f"建議與收據核對確認金額正確。"
        )


# ============================================================
#  功能四：信用卡推薦對話
# ============================================================

class CardAdvisorAgent:
    """
    對話式信用卡推薦 Agent。
    透過多輪對話收集消費習慣，再進行個人化推薦。
    """

    _SYSTEM_TEMPLATE = """你是台灣旅遊信用卡顧問。
透過 3-5 輪對話了解使用者的旅遊消費習慣，然後推薦最適合的信用卡。

可推薦的卡片：
{cards_info}

對話策略：
1. 詢問主要旅遊地區（日本/東南亞/歐美等）
2. 詢問最大消費類別（餐飲/購物/住宿）
3. 詢問旅遊頻率與預算
4. 根據資訊推薦 1-2 張卡片，附具體回饋試算
5. 回答補充問題

規則：
- 繁體中文，每次回覆不超過 200 字
- 推薦時附上具體數字（回饋率、預估回饋金額）
- 不使用 emoji"""

    def __init__(self, client: ClaudeClient, db_path: str):
        self.client = client
        self.db_path = db_path
        self._cards_cache = None

    def get_cards_summary(self) -> str:
        """格式化信用卡資訊供 LLM 使用。"""
        if self._cards_cache:
            return self._cards_cache
        try:
            from src.card_recommend import CardRecommendService, seed_cards
            seed_cards(self.db_path)
            svc = CardRecommendService(self.db_path)
            cards = svc.get_all_cards()
            lines = []
            for c in cards:
                reward_strs = [
                    f"{r['category']}({r['region']}):{r['reward_rate']:.1f}%回饋"
                    for r in c["rewards"]
                ]
                lines.append(
                    f"- {c['card_name']}（{c['issuer']}）"
                    f"海外手續費{c['overseas_fee_pct']:.1f}%"
                    + ("，" + "、".join(reward_strs) if reward_strs else "")
                )
            self._cards_cache = "\n".join(lines)
            return self._cards_cache
        except Exception:
            return "玉山Pi卡(2.8%海外回饋)、中信CUBE卡(餐飲5%)、台新@GoGo卡(3%海外)、國泰KOKO卡(3.3%)、富邦J卡(日本5%)、聯邦賴點卡(購物5%)"

    def chat(self, user_message: str, history: list, spending_profile: dict | None = None) -> str:
        """
        信用卡推薦多輪對話。
        降級：呼叫 CardRecommendService 規則推薦。
        """
        cards_info = self.get_cards_summary()
        system = self._SYSTEM_TEMPLATE.format(cards_info=cards_info)

        if spending_profile:
            system += f"\n\n使用者現有消費檔案：{json.dumps(spending_profile, ensure_ascii=False)}"

        messages = []
        for msg in history[-8:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        reply = self.client.chat(
            messages=messages,
            system=system,
            model=MODEL_HAIKU,
            max_tokens=400,
            temperature=0.6,
        )
        if reply:
            return reply.strip()
        return self._fallback_recommend(spending_profile)

    def _fallback_recommend(self, spending_profile: dict | None) -> str:
        try:
            from src.card_recommend import CardRecommendService, seed_cards
            seed_cards(self.db_path)
            svc = CardRecommendService(self.db_path)
            results = svc.recommend_by_category(category="海外", amount=10000, region="日本")
            if results:
                top = results[:2]
                lines = ["根據一般海外旅遊消費，推薦以下信用卡：\n"]
                for r in top:
                    lines.append(
                        f"**{r['card_name']}**（{r['issuer']}）"
                        f" — NT$10,000 消費可獲回饋 NT${r['reward_amount']:,.0f}"
                    )
                return "\n".join(lines)
        except Exception:
            pass
        return "建議選擇海外回饋率 3% 以上的信用卡，可詢問各銀行旅遊卡方案。"


# ============================================================
#  功能五：預算規劃 Agent
# ============================================================

class BudgetPlannerAgent:
    """
    旅遊前預算規劃 Agent。
    依目的地/天數/人數/旅遊風格生成個人化預算建議。
    使用 claude-sonnet 進行深度推理。
    """

    _SYSTEM_TEMPLATE = """你是旅遊預算規劃專家，專門為台灣旅客規劃出國預算。

基準預算資料（規則引擎計算）：
{base_plan}

{history_context}

根據以上資訊，生成個人化旅行預算建議，包含：
1. 三檔方案（節省/標準/豪華）每日與總預算（以台幣計）
2. 各類別金額分配（住宿/餐飲/交通/購物/娛樂）
3. 針對此目的地的省錢技巧（3-5 條）
4. 風險提醒（匯率波動、旺季漲價等）

格式：繁體中文，結構清晰，數字具體，不使用 emoji，不超過 400 字。"""

    def __init__(self, client: ClaudeClient, db_path: str):
        self.client = client
        self.db_path = db_path

    def plan(
        self,
        destination: str,
        days: int,
        num_travelers: int,
        travel_style: str = "standard",
        special_needs: str = "",
        user_id: int | None = None,
    ) -> dict:
        """
        生成個人化預算規劃。

        回傳：
            dict: {base_plan, ai_analysis, source}
        """
        from src.planner import TripPlanner
        planner = TripPlanner(self.db_path)
        try:
            base_plan = planner.suggest_budget(destination, days, num_travelers)
        except ValueError:
            # 目的地不在資料庫中，使用預設
            base_plan = planner.suggest_budget("日本", days, num_travelers)

        base_text = self._format_base_plan(base_plan, destination, days, num_travelers, travel_style)
        history_context = ""
        if user_id:
            history_context = self._get_history_context(user_id)

        extra = f"特殊需求：{special_needs}" if special_needs else ""
        system = self._SYSTEM_TEMPLATE.format(
            base_plan=base_text,
            history_context=f"使用者歷史消費：\n{history_context}" if history_context else "",
        )
        user_msg = (
            f"請為 {destination} {days} 天 {num_travelers} 人的旅行，"
            f"以「{travel_style}」風格規劃預算。"
            + (f" {extra}" if extra else "")
        )

        ai_analysis = self.client.chat(
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            model=MODEL_SONNET,
            max_tokens=600,
            temperature=0.5,
        )

        return {
            "base_plan": base_plan,
            "ai_analysis": ai_analysis,
            "source": MODEL_SONNET if ai_analysis else "rule_engine",
        }

    def interactive_plan(
        self,
        user_message: str,
        history: list,
        current_params: dict,
    ) -> tuple:
        """
        互動式預算規劃對話。
        回傳 (回覆文字, 更新後的 current_params)
        """
        from src.planner import TripPlanner, DESTINATION_FACTORS
        system = (
            "你是旅遊預算助理。根據對話調整旅行參數（目的地/天數/人數/風格）並重新計算預算。"
            f"目前參數：{json.dumps(current_params, ensure_ascii=False)}\n"
            f"支援目的地：{', '.join(DESTINATION_FACTORS.keys())}\n"
            "繁體中文回覆，不超過 200 字，不使用 emoji。"
        )
        messages = []
        for msg in history[-6:]:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        reply = self.client.chat(
            messages=messages,
            system=system,
            model=MODEL_HAIKU,
            max_tokens=300,
            temperature=0.5,
        )
        if not reply:
            reply = "請告訴我目的地、天數和人數，我幫你重新計算預算。"
        return reply, current_params

    def _format_base_plan(
        self, plan: dict, dest: str, days: int, travelers: int, style: str
    ) -> str:
        tiers = plan.get("tiers", {})
        lines = [f"目的地：{dest}，{days}天，{travelers}人，風格：{style}"]
        for tier_key, label in [("budget", "節省"), ("standard", "標準"), ("premium", "豪華")]:
            t = tiers.get(tier_key, {})
            lines.append(
                f"{label}版：每人每日 NT${t.get('daily_per_person', 0):,}，"
                f"每人總計 NT${t.get('total_per_person', 0):,}"
            )
        std = tiers.get("standard", {})
        breakdown = std.get("breakdown", {})
        if breakdown:
            lines.append("標準版類別分配：" + "、".join(
                f"{k} NT${v:,}" for k, v in breakdown.items()
            ))
        return "\n".join(lines)

    def _get_history_context(self, user_id: int) -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.destination, SUM(tx.amount_twd) as total,
                           COUNT(tx.txn_id) as cnt
                    FROM trips t
                    JOIN transactions tx ON t.trip_id = tx.trip_id
                    WHERE t.user_id = ?
                    GROUP BY t.destination
                    ORDER BY total DESC LIMIT 3
                """, (user_id,))
                rows = cursor.fetchall()
                if rows:
                    return "、".join(
                        f"{r[0]}（NT${r[1]:,.0f}，{r[2]}筆交易）" for r in rows
                    )
        except Exception:
            pass
        return ""


# ============================================================
#  統一對外入口
# ============================================================

class AIAgentService:
    """
    TravelWallet AI 服務的統一入口。
    組合所有子 Agent，供 Streamlit 頁面直接使用。
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DB_PATH
        self._client = ClaudeClient()
        self.vision_parser = ReceiptVisionParser(self._client)
        self.advisor = FinancialAdvisorAgent(self._client, self.db_path)
        self.explainer = AnomalyExplainer(self._client)
        self.card_advisor = CardAdvisorAgent(self._client, self.db_path)
        self.budget_planner = BudgetPlannerAgent(self._client, self.db_path)

    @property
    def is_available(self) -> bool:
        """True 表示 ANTHROPIC_API_KEY 已設定"""
        return self._client.available

    @property
    def model_info(self) -> dict:
        return {
            "haiku": MODEL_HAIKU,
            "sonnet": MODEL_SONNET,
            "available": self.is_available,
        }

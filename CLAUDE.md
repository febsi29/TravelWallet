# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 語言規則

- 總是用繁體中文回覆。

## 常用指令

```bash
# 啟動應用程式（Windows 必須加 PYTHONUTF8=1，否則中文頁面會被隱藏）
PYTHONUTF8=1 streamlit run app/main.py

# 初始化資料庫 schema（首次或 schema 變更後執行）
python -c "
import sqlite3
conn = sqlite3.connect('database/travel_wallet.db')
with open('database/schema.sql', 'r', encoding='utf-8') as f:
    conn.executescript(f.read())
conn.commit(); conn.close()
"

# 生成種子資料（開發用，會清除現有資料）
python -m database.seed_data

# 執行全部測試
python -m pytest tests/ -q

# 執行單一測試檔
python -m pytest tests/test_wallet.py -q

# 執行單一測試函數
python -m pytest tests/test_wallet.py::test_deposit -q
```

## 架構概覽

```
app/
  main.py          # Streamlit 首頁：載入旅行摘要、預算、異常偵測
  pages/           # 各功能頁面（數字前綴決定側邊欄順序）
src/               # 服務層（純 Python，不含 Streamlit）
database/
  schema.sql       # SQLite schema（所有表定義）
  travel_wallet.db # 主資料庫（本地 SQLite）
  seed_data.py     # 開發用種子資料生成腳本
tests/             # pytest 測試（每個 src/ 模組對應一個測試檔）
```

### 分層原則

- **頁面層（app/pages/）** 只負責 UI 與呼叫服務層，不直接寫 SQL
- **服務層（src/）** 封裝所有資料庫存取，使用 `contextmanager` `_db()` 管理連線
- 資料庫連線必須用 `with sqlite3.connect(...) as conn:` 或 `_db()` context manager，禁止在頁面層直接持有連線

### 資料庫存取模式

所有服務類別使用統一的 context manager 模式：

```python
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
```

### SQL 安全規則

- **ORDER BY 必須使用白名單字典**，分別映射欄位名與排序方向，禁止任何字串插值包含使用者輸入
- 所有 WHERE 條件使用參數化查詢（`?` 佔位符）

### 主要服務模組

| 模組 | 功能 |
|------|------|
| `src/currency.py` | 匯率查詢、快取、即時更新 |
| `src/split.py` | 分帳計算、貪心結算演算法 |
| `src/wallet.py` | 多幣別電子錢包、存提款 |
| `src/rate_alert.py` | 匯率到價提醒 |
| `src/prediction.py` | 支出預測（指數平滑） |
| `src/anomaly.py` | 異常交易偵測 |
| `src/risk_dashboard.py` | 財務風險評估（四維度加權） |
| `src/card_recommend.py` | 信用卡推薦 |
| `src/ocr.py` | 收據 OCR（Claude Vision / pytesseract fallback） |
| `src/community.py` | 社群排行榜 |
| `src/payment.py` | 分帳付款連結（LINE Pay / JKO Pay / PayPal） |
| `src/ai_agent.py` | Claude AI Agent（5 個子 Agent + 降級規則型回退） |

### AI Agent 架構

`src/ai_agent.py` 包含 5 個子 Agent 類別，統一由 `AIAgentService` 管理：
- `ReceiptVisionParser` — 收據圖片結構化解析
- `FinancialAdvisorAgent` — 財務建議
- `AnomalyExplainer` — 異常交易解釋
- `CardAdvisorAgent` — 信用卡推薦輔助
- `BudgetPlannerAgent` — 預算規劃

所有 Agent 在 `ANTHROPIC_API_KEY` 未設定時自動降級為規則型回退，不會拋出例外。

### 環境變數

```bash
ANTHROPIC_API_KEY   # Claude API 金鑰（選填，未設定時 AI 功能自動降級）
```

## 質量紅線

### 絕對禁止
- 絕不提交未通過測試的程式碼
- 絕不使用 TODO/佔位符作為最終代碼
- 絕不跳過錯誤處理
- 絕不硬編碼金鑰/憑證
- SQL ORDER BY 子句絕不插值使用者輸入

## Git 規範

### 分支命名
- `feature/功能描述`
- `bugfix/問題描述`
- `hotfix/緊急修復`

### Commit 訊息
```
類型(範圍): 簡短描述
```
類型：`feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`chore`

## 溝通規範
- 使用清晰、專業的語言
- 避免過度解釋
- 需求不明確時主動提問
- 避免社交短語（"您說得對"、"好問題"）

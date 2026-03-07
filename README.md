# TravelWallet

A travel expense tracker with split bill functionality, built for Taiwanese travelers. Combines personal spending data with Taiwan government tourism statistics to provide budget planning, anomaly detection, and consumption analytics.

I built this as a side project while applying for FinTech internships. The goal was to demonstrate skills in database design, data analysis, machine learning, and full-stack development — all within a realistic financial application context.

一個為台灣旅人設計的旅遊記帳工具，結合多人分帳功能。整合個人消費資料與政府觀光統計，提供預算規劃、異常偵測、消費分析等功能。

這是我在準備 FinTech 實習面試時做的 side project，目標是展示資料庫設計、資料分析、機器學習與全端開發的能力，並將這些技能放在一個實際的金融應用場景中。

---

## Installation / 安裝

Clone the repository and install dependencies:

```bash
git clone https://github.com/febsi29/TravelWallet.git
cd TravelWallet
pip install -r requirements.txt
```

Initialize the database and load sample data:

初始化資料庫並載入範例資料：

```bash
python src/data_loader.py
python database/seed_data.py
```

(Optional) Set API keys for live exchange rates and AI assistant:

（選用）設定 API key 以啟用即時匯率和 AI 助手：

```bash
# PowerShell
$env:EXCHANGE_RATE_API_KEY="your_key"
$env:GEMINI_API_KEY="your_key"
```

Free keys available at / 免費申請：
- Exchange rates: https://www.exchangerate-api.com/
- Gemini: https://aistudio.google.com/apikey

The app works without these keys — it falls back to offline exchange rates and a rule-based engine.

沒有 key 也能正常使用，系統會自動切換為離線匯率和規則引擎。

---

## Usage / 使用方法

Start the app / 啟動應用：

```bash
streamlit run app/main.py
```

Open http://localhost:8501 in your browser.

在瀏覽器開啟 http://localhost:8501。

### What you can do / 功能說明

**Record expenses and split bills / 記帳與分帳**

Input a transaction with amount, currency, category, and payer. Choose how to split it: equal, by ratio, or custom amounts. The system tracks who paid what and who owes whom.

輸入消費金額、幣別、類別和付款人，選擇分帳方式（均分、比例、自訂金額）。系統會追蹤誰付了什麼、誰欠誰多少。

```
Input:  Dinner at Shibuya, JPY 24,000, paid by Alice, split equally among 4
Output: Each person owes JPY 6,000. Alice is owed JPY 18,000.

輸入：澀谷晚餐，24,000日圓，小明付的，四人均分
輸出：每人分攤 6,000日圓，小明被欠 18,000日圓
```

**Settle debts with minimal transfers / 最少轉帳次數結算**

At the end of a trip, the greedy netting algorithm calculates the fewest transfers needed to clear all debts.

旅行結束後，貪心演算法（Greedy Netting）算出最少的轉帳次數來清償所有債務。

```
Input:  4 people, 31 transactions over 5 days
Output: 3 transfers to settle everything
        Bob pays Alice: JPY 32,275
        Bob pays Carol: JPY 28,375
        Bob pays Dave:  JPY 9,475

輸入：4人，5天31筆交易
輸出：只需要3筆轉帳就能全部結清
```

**Plan a trip budget / 旅遊前預算規劃**

Enter a destination and number of days. The system uses government statistics on average tourist spending to suggest three budget tiers.

輸入目的地和天數，系統根據政府觀光統計資料建議三檔預算。

```
Input:  Japan, 5 days, 4 people
Output: Budget tier:   NT$31,049/person
        Standard tier: NT$44,355/person
        Premium tier:  NT$66,533/person

輸入：日本，5天，4人
輸出：節省版 NT$31,049/人、標準版 NT$44,355/人、豪華版 NT$66,533/人
```

**Detect anomalous spending / 異常消費偵測**

Three detection methods (Z-Score, IQR, Isolation Forest) run independently. A transaction is flagged only when 2 out of 3 methods agree.

三種偵測方法獨立運行，只有兩種以上方法同時標記時才判定為異常，降低誤報率。

```
Input:  31 transactions from a Tokyo trip
Output: 0 anomalies detected (normal trip)
        Z-Score flagged 1, IQR flagged 0, Isolation Forest flagged 3
        No consensus = no false alarms

輸入：東京旅行的31筆交易
輸出：0筆異常（正常旅行）
      Z-Score標記1筆、IQR標記0筆、Isolation Forest標記3筆
      沒有共識 = 不誤報
```

**Compare your spending to the national average / 個人 vs 全國平均**

Your per-person spending is compared against government data on average Taiwanese tourist expenditure.

將你的每人花費與政府統計的台灣旅客平均消費做比較。

```
Input:  Tokyo trip, 5 days, 4 people
Output: Your per-person total: NT$24,331
        National average:      NT$60,481
        Difference: -59.8% (below average, excludes airfare)

輸入：東京旅行，5天4人
輸出：你的每人花費 NT$24,331 vs 全國平均 NT$60,481，低於平均59.8%（未含機票）
```

**Ask the AI assistant / AI 智慧助手**

Type questions in natural language. The system routes structured queries through a rule engine for speed, and open-ended questions through Gemini.

用自然語言提問。結構化查詢走規則引擎（快又準），開放式問題走 Gemini。

```
Input:  "How much does everyone owe?"
Output: Net balances and settlement plan from the rule engine

輸入：「現在誰欠誰多少？」
輸出：規則引擎直接回傳淨餘額和結算方案

Input:  "Should I exchange money now or wait?"
Output: Gemini generates advice based on current rates

輸入：「現在該換日圓嗎？」
輸出：Gemini 根據目前匯率給出建議
```

### Pages / 頁面

| Page / 頁面 | Description / 說明 |
|-------------|-------------------|
| Dashboard | Trip overview with spending charts / 旅行總覽與消費圖表 |
| Transactions | Transaction list with filters and CSV export / 交易列表，支援篩選與匯出 |
| Split Bill | Net balances and settlement plan / 淨餘額與結算方案 |
| Trip Planner | Budget suggestions for 12 destinations / 12個目的地的預算建議 |
| Exchange | Live rates for 12 currencies with converter / 12種幣別即時匯率與換算 |
| Analytics | Personal vs national comparison / 個人與全國平均對比 |
| Alerts | Anomaly detection with adjustable parameters / 異常偵測，可調參數 |
| AI Assistant | Chat interface with quick actions / 對話式AI助手 |

---

## Technical Details / 技術細節

Built with Python, SQLite, Streamlit, scikit-learn, and Plotly.

使用 Python、SQLite、Streamlit、scikit-learn、Plotly 開發。

The split bill settlement uses a greedy algorithm equivalent to financial netting in institutional clearing. The anomaly detection combines statistical methods (Z-Score, IQR) with unsupervised machine learning (Isolation Forest) using a majority vote to reduce false positives. Budget predictions use linear regression on daily cumulative spending.

分帳結算使用貪心演算法，概念等同於金融機構的淨額清算（netting）。異常偵測結合統計方法（Z-Score、IQR）與無監督式機器學習（Isolation Forest），以多數決降低誤報。預算預測使用線性迴歸分析每日累計消費。

Government data comes from Taiwan's Ministry of Transportation and Communications open data portal (data.gov.tw). The AI assistant uses a dual-engine architecture: a rule-based engine for structured data queries and Google Gemini for natural language understanding, with automatic fallback if the API is unavailable.

政府資料來自交通部觀光署開放資料平台（data.gov.tw）。AI 助手採用雙引擎架構：規則引擎處理結構化查詢，Google Gemini 處理自然語言理解，API 不可用時自動降級為規則引擎。

Full database schema is in `database/schema.sql`. All source modules are in `src/` with standalone test scripts.

完整資料庫結構在 `database/schema.sql`，所有模組在 `src/` 底下，各自有獨立的測試腳本。

---

## License / 授權

For educational and portfolio purposes. Government data used under Taiwan Open Data License.

本專案為教育與作品集用途。政府資料依政府資料開放授權條款使用。

---

Built by **febsi29** — Senior, Foreign Languages and MIS double major.

作者 **febsi29** — 外語系與資管系雙主修，大四。

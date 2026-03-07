# 🧳 TravelWallet — 台灣旅人智慧旅遊錢包

**Smart Travel Wallet for Taiwanese Travelers**

一個結合旅遊記帳、多幣別分帳、數據分析與 AI 助手的 FinTech Side Project，融合台灣政府開放資料，提供消費追蹤、預算預測、異常偵測等功能。

> 🎓 This project was built as a portfolio piece for FinTech internship applications.

---

## ✨ Features

### Core Modules
- **多幣別記帳 + 分帳** — 支援均分、比例、自訂金額分帳，最小化轉帳次數的 Greedy Netting 演算法
- **即時匯率查詢** — 串接 ExchangeRate-API，支援 12 種常見幣別換算
- **旅遊前預算規劃** — 根據政府統計資料，提供三檔預算建議（節省/標準/豪華）
- **個人 vs 全國對比** — 將個人消費與全國平均做比較，含類別佔比分析
- **異常消費偵測** — Z-Score + IQR + Isolation Forest 三重偵測，多數決降低誤報
- **預算預測** — 線性迴歸預測整趟花費，燃盡圖追蹤預算使用狀況
- **AI 智慧助手** — Gemini API + 規則引擎雙軌制，自然語言查詢旅遊財務資訊

### Data Sources
- [歷年國人出國旅遊重要指標統計表](https://data.gov.tw/dataset/8587) — 交通部觀光署
- [ExchangeRate-API](https://www.exchangerate-api.com/) — 即時匯率

---

## 🛠 Tech Stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.10+ |
| Data | pandas, NumPy |
| Database | SQLite |
| Visualization | Plotly, Matplotlib |
| Machine Learning | scikit-learn (Isolation Forest) |
| Frontend | Streamlit |
| AI Agent | Google Gemini API + Rule-based Engine |
| Deployment | Streamlit Cloud |

---

## 📁 Project Structure

```
TravelWallet/
├── app/
│   ├── main.py                  # Dashboard
│   └── pages/
│       ├── 2_Transactions.py    # Transaction list with filters
│       ├── 3_SplitBill.py       # Split bill center
│       ├── 4_TripPlanner.py     # Budget planner
│       ├── 5_Exchange.py        # Currency converter
│       ├── 6_Analytics.py       # Data analytics
│       ├── 7_Alerts.py          # Anomaly detection
│       └── 8_AI_Assistant.py    # AI chatbot
├── src/
│   ├── data_loader.py           # CSV cleaning & DB import
│   ├── currency.py              # Exchange rate module
│   ├── split.py                 # Split bill engine
│   ├── planner.py               # Trip budget planner
│   ├── analytics.py             # Consumption analytics
│   ├── anomaly.py               # Anomaly detection (3 methods)
│   └── budget.py                # Budget prediction
├── database/
│   ├── schema.sql               # Full database schema
│   └── seed_data.py             # Mock data generator
├── data/
│   └── raw/                     # Government open data CSVs
├── notebooks/
│   └── 01_EDA_gov_data.py       # Exploratory data analysis
└── docs/
    └── demo_screenshots/        # Charts & screenshots
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/febsi29/TravelWallet.git
cd TravelWallet
pip install -r requirements.txt
```

### 2. Setup Database

```bash
python src/data_loader.py    # Import government data
python database/seed_data.py # Generate mock data
```

### 3. Set API Keys (Optional)

```bash
# PowerShell
$env:EXCHANGE_RATE_API_KEY="your_key_here"
$env:GEMINI_API_KEY="your_key_here"
```

Get free keys:
- Exchange Rate: https://www.exchangerate-api.com/
- Gemini: https://aistudio.google.com/apikey

### 4. Run

```bash
streamlit run app/main.py
```

Open http://localhost:8501

---

## 📊 Key Algorithms

### Greedy Netting (Split Bill Settlement)

Minimizes the number of transfers needed to settle all debts:

1. Calculate net balance for each person (paid - owed)
2. Sort creditors and debtors by amount
3. Match largest debtor with largest creditor
4. Repeat until all balances are zero

> This is equivalent to **financial netting** used in institutional clearing systems.

### Anomaly Detection (Ensemble Approach)

Three methods with majority vote:

| Method | Type | How it works |
|--------|------|-------------|
| Z-Score | Statistics | Flags transactions > 2 std from category mean |
| IQR | Statistics | Flags transactions outside Q1-1.5*IQR to Q3+1.5*IQR |
| Isolation Forest | ML | Unsupervised detection using amount, time, category |

A transaction is flagged only if **2+ methods agree**, reducing false positives.

> Similar logic to **credit card fraud detection** and **AML transaction monitoring** in banking.

### Budget Prediction

Linear regression on daily cumulative spending to forecast total trip cost.

---

## 🤖 AI Agent Architecture

```
User Input
    │
    ▼
┌─────────────────┐
│  Rule Engine     │ ← Keyword matching for structured queries
│  (Fast, Exact)   │   (exchange rates, balances, budgets)
└────────┬────────┘
         │ No match
         ▼
┌─────────────────┐
│  Gemini API      │ ← Natural language understanding
│  (Smart, Flex)   │   for open-ended questions
└────────┬────────┘
         │ API failure
         ▼
┌─────────────────┐
│  Fallback        │ ← Graceful degradation
│  (Rule Engine)   │
└─────────────────┘
```

---

## 📈 Sample Insights from Government Data

- **Peak year**: 17.1M outbound trips in 2019
- **COVID impact**: 97.9% drop in 2021 (only 360K trips)
- **Recovery**: 2023 reached 69% of pre-COVID levels
- **Spending growth**: Per-person average up 24.1% (2013→2023)
- **Stay duration**: Shortening trend (8.7→7.8 nights), indicating more short trips

---

## 🗓 Development Timeline

| Week | Deliverable |
|------|------------|
| 1 | Database schema, data cleaning, seed data |
| 2 | Government data EDA, exchange rate module |
| 3 | Split bill engine with greedy settlement |
| 4 | Trip planner, consumption analytics |
| 5 | Anomaly detection (3 methods), budget prediction |
| 6-7 | Streamlit frontend (8 pages) + AI Agent |
| 8 | Deployment, README, documentation |

---

## 🔮 Future Work

- Natural language expense logging ("小明付了午餐3000四人分")
- LINE Bot integration for group split bills
- OCR receipt scanning
- Currency exchange timing recommendations
- Statistical validation: exchange rate vs travel intention
- RESTful API for microservice architecture

---

## 📝 License

This project is for educational and portfolio purposes.

Data source: [交通部觀光署](https://www.taiwan.net.tw/) under Government Open Data License.

---

## 👤 Author

**febsi29** — Senior, Double Major in Foreign Languages & MIS

- GitHub: [github.com/febsi29](https://github.com/febsi29)
- Project: [github.com/febsi29/TravelWallet](https://github.com/febsi29/TravelWallet)

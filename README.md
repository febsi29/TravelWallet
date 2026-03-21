# TravelWallet

A travel expense tracker with split bill functionality, built for Taiwanese travelers. Combines personal spending data with Taiwan government tourism statistics to provide budget planning, anomaly detection, and consumption analytics.

I built this as a side project while applying for FinTech internships. The goal was to demonstrate skills in database design, data analysis, machine learning, and full-stack development — all within a realistic financial application context.



 FinTech  side project

---

## Installation / 

Clone the repository and install dependencies:

```bash
git clone https://github.com/febsi29/TravelWallet.git
cd TravelWallet
pip install -r requirements.txt
```

Initialize the database and load sample data:



```bash
python src/data_loader.py
python database/seed_data.py
```

(Optional) Set API keys for live exchange rates and AI assistant:

 API key  AI 

```bash
# PowerShell
$env:EXCHANGE_RATE_API_KEY="your_key"
$env:GEMINI_API_KEY="your_key"
```

Free keys available at / 
- Exchange rates: https://www.exchangerate-api.com/
- Gemini: https://aistudio.google.com/apikey

The app works without these keys — it falls back to offline exchange rates and a rule-based engine.

 key 

---

## Usage / 

Start the app / 

```bash
streamlit run app/main.py
```

Open http://localhost:8501 in your browser.

 http://localhost:8501

### What you can do / 

**Record expenses and split bills / **

Input a transaction with amount, currency, category, and payer. Choose how to split it: equal, by ratio, or custom amounts. The system tracks who paid what and who owes whom.



```
Input:  Dinner at Shibuya, JPY 24,000, paid by Alice, split equally among 4
Output: Each person owes JPY 6,000. Alice is owed JPY 18,000.

24,000
 6,000 18,000
```

**Settle debts with minimal transfers / **

At the end of a trip, the greedy netting algorithm calculates the fewest transfers needed to clear all debts.

Greedy Netting

```
Input:  4 people, 31 transactions over 5 days
Output: 3 transfers to settle everything
        Bob pays Alice: JPY 32,275
        Bob pays Carol: JPY 28,375
        Bob pays Dave:  JPY 9,475

4531
3
```

**Plan a trip budget / **

Enter a destination and number of days. The system uses government statistics on average tourist spending to suggest three budget tiers.



```
Input:  Japan, 5 days, 4 people
Output: Budget tier:   NT$31,049/person
        Standard tier: NT$44,355/person
        Premium tier:  NT$66,533/person

54
 NT$31,049/ NT$44,355/ NT$66,533/
```

**Detect anomalous spending / **

Three detection methods (Z-Score, IQR, Isolation Forest) run independently. A transaction is flagged only when 2 out of 3 methods agree.



```
Input:  31 transactions from a Tokyo trip
Output: 0 anomalies detected (normal trip)
        Z-Score flagged 1, IQR flagged 0, Isolation Forest flagged 3
        No consensus = no false alarms

31
0
      Z-Score1IQR0Isolation Forest3
       = 
```

**Compare your spending to the national average /  vs **

Your per-person spending is compared against government data on average Taiwanese tourist expenditure.



```
Input:  Tokyo trip, 5 days, 4 people
Output: Your per-person total: NT$24,331
        National average:      NT$60,481
        Difference: -59.8% (below average, excludes airfare)

54
 NT$24,331 vs  NT$60,48159.8%
```

**Ask the AI assistant / AI **

Type questions in natural language. The system routes structured queries through a rule engine for speed, and open-ended questions through Gemini.

 Gemini

```
Input:  "How much does everyone owe?"
Output: Net balances and settlement plan from the rule engine




Input:  "Should I exchange money now or wait?"
Output: Gemini generates advice based on current rates


Gemini 
```

### Pages / 

| Page /  | Description /  |
|-------------|-------------------|
| Dashboard | Trip overview with spending charts /  |
| Transactions | Transaction list with filters and CSV export /  |
| Split Bill | Net balances and settlement plan /  |
| Trip Planner | Budget suggestions for 12 destinations / 12 |
| Exchange | Live rates for 12 currencies with converter / 12 |
| Analytics | Personal vs national comparison /  |
| Alerts | Anomaly detection with adjustable parameters /  |
| AI Assistant | Chat interface with quick actions / AI |

---

## Technical Details / 

Built with Python, SQLite, Streamlit, scikit-learn, and Plotly.

 PythonSQLiteStreamlitscikit-learnPlotly 

The split bill settlement uses a greedy algorithm equivalent to financial netting in institutional clearing. The anomaly detection combines statistical methods (Z-Score, IQR) with unsupervised machine learning (Isolation Forest) using a majority vote to reduce false positives. Budget predictions use linear regression on daily cumulative spending.

nettingZ-ScoreIQRIsolation Forest

Government data comes from Taiwan's Ministry of Transportation and Communications open data portal (data.gov.tw). The AI assistant uses a dual-engine architecture: a rule-based engine for structured data queries and Google Gemini for natural language understanding, with automatic fallback if the API is unavailable.

data.gov.twAI Google Gemini API 

Full database schema is in `database/schema.sql`. All source modules are in `src/` with standalone test scripts.

 `database/schema.sql` `src/` 

---

## License / 

For educational and portfolio purposes. Government data used under Taiwan Open Data License.



---

Built by **febsi29** — Senior, Foreign Languages and MIS double major.

 **febsi29** — 

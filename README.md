# ⚡ Trade Signal Engine

Multi-strategy intraday trading signal analyzer for NSE Cash Segment.

**Tech Stack:** Python · Flask · SQLite · HTML/CSS/JS · TradingView Lightweight Charts

---

## Quick Start

```bash
# 1. Install dependencies (Python 3.11+ recommended)
pip install -r requirements.txt

# 2. Start the server
python app.py

# 3. Open in browser
http://localhost:5000
```

The app auto-loads a DEMO session on first launch so you can see everything working immediately.

---

## Project Structure

```
trading-engine/
├── app.py              ← Flask server + API routes
├── database.py         ← SQLite layer (sessions, candles, signals, journal)
├── engine/
│   ├── strategies.py   ← EMA, VWAP, ATR, ORB, RSI calculations
│   └── signals.py      ← Multi-strategy signal generation engine
├── templates/
│   └── index.html      ← Single-page app template
├── static/
│   ├── css/style.css   ← Dark terminal theme
│   └── js/app.js       ← Frontend logic + TradingView charts
├── requirements.txt
└── trading_engine.db   ← Auto-created on first run
```

---

## How to Use with Your Live Feed

### Step 1 — Export your 1-min data as CSV

Format: `datetime,open,high,low,close,volume`

```
datetime,open,high,low,close,volume
09:15,712.50,715.30,710.80,714.20,125000
09:16,714.20,716.00,713.50,715.80,98000
```

**From Zerodha Kite:** Chart (1 min) → Right-click → Download CSV  
**From Upstox Pro:** Chart → Export → Historical 1-min OHLC  
**From Angel One:** SmartCharts → Download Data → 1 Min  
**From TradingView:** Chart → Export chart data → CSV  
**From your feed API:** Format as the above and paste directly

### Step 2 — Load in the app

1. Go to **📥 DATA INPUT** tab
2. Paste cash CSV in the top box
3. Paste futures CSV in the bottom box (optional — for bias)
4. Set stock name, capital, risk/trade in the left panel
5. Click **⚡ LOAD & ANALYZE**

### Step 3 — Read signals

- Go to **🎯 SIGNALS** tab
- Click any signal card to expand full trade details:
  - Entry, SL, T1 / T2 / T3
  - Quantity (auto-calculated from your risk settings)
  - Capital required, Max risk, Potential P&L
  - Indicator values at time of signal
  - Plain-English action instruction

### Step 4 — Log your trades

- Click **📓 Log this trade** from any signal
- Or manually add in the **📓 JOURNAL** tab
- Tracks P&L, win rate, brokerage charges automatically

---

## Strategies

| Strategy        | Logic                                                |
|----------------|------------------------------------------------------|
| **ORB**         | First 15-min high/low breakout with 1.3x volume     |
| **EMA 9/21/50** | Golden cross, death cross, EMA21 bounce             |
| **VWAP**        | Session VWAP reclaim and rejection                  |
| **Volume Surge**| Candles with 2x+ average session volume             |
| **Futures Bias**| Cash vs futures premium/discount confirmation       |

Signals fire when combined strategy score ≥ 2.5. All strategies are toggleable.

---

## API Endpoints

| Method | Path                     | Description                   |
|--------|--------------------------|-------------------------------|
| GET    | `/`                      | Main app UI                   |
| POST   | `/api/upload`            | Upload CSV data, create session |
| POST   | `/api/analyze/<id>`      | Run signal engine on session  |
| GET    | `/api/chart-data/<id>`   | OHLCV + indicators + signals  |
| GET    | `/api/signals/<id>`      | Get signals for session       |
| GET    | `/api/sessions`          | List all sessions             |
| POST   | `/api/journal`           | Log a trade                   |
| GET    | `/api/journal`           | Get journal entries           |
| DELETE | `/api/journal/<id>`      | Delete journal entry          |
| GET    | `/api/stats/<id>`        | Win rate, P&L stats           |

---

## Risk Parameters

The engine uses your capital and risk/trade settings to auto-size every trade:

```
Position Size = Risk Per Trade ÷ SL Distance (in ₹)
SL Distance   = 1.5 × ATR(14), adjusted to ORB level
```

**Default settings** (matches your plan):
- Capital: ₹25,000
- Risk/Trade: ₹500 (2% of capital)
- Max Loss/Day: ₹1,000 (2 losing trades = stop for the day)
- Daily Target: ₹125 (0.5% — modest and achievable)
- Monthly Goal: ₹2,500 (covers subscription cost)

---

## Adding Your Own Strategy

Edit `engine/signals.py` and add scoring logic inside the `generate_signals()` loop:

```python
# Custom: Price makes higher high + higher low (uptrend continuation)
if config.get('my_strategy'):
    if candle['high'] > data[i-1]['high'] and candle['low'] > data[i-1]['low']:
        bs += 1.5
        reasons.append('HH/HL Uptrend')
```

Then add the toggle in `templates/index.html`:

```html
<label class="strat-row" data-key="my_strategy" data-color="#ff6b9d">
  <input type="checkbox" /> My Custom Strategy
</label>
```

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

├── app.py                  ← Flask server + API routes
├── database.py             ← SQLite layer (sessions, candles, signals, journal, backtests)
├── backtest_cli.py         ← Run backtests/optimization from the terminal
├── live_feed.py            ← Fyers websocket → 1-min candles → live signals
├── engine/
│   ├── config.py           ← Central tunable signal/backtest config
│   ├── strategies.py       ← EMA, VWAP, ATR, ORB, RSI calculations
│   ├── signals_v2.py       ← Multi-strategy signal engine (the one used everywhere)
│   ├── advanced.py         ← HTF trend, S/R, patterns, regime, volume delta
│   ├── filters.py          ← Time windows, conviction scoring, position sizing
│   ├── strategies_advanced.py ← F5MC, CVD divergence
│   ├── backtester.py       ← Walk-forward replay + optimizer (train/test split)
│   └── data_align.py       ← Timestamp alignment for cash/futures/index feeds
├── templates/index.html    ← Single-page app template
├── static/                 ← Dark terminal theme + TradingView charts
├── tests/                  ← pytest suite (run: pytest -q)
├── requirements.txt / requirements-dev.txt
└── trading_engine.db       ← Auto-created on first run
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


Plus advanced strategies: **F5MC** (first-5-min momentum) and **CVD divergence**.
All strategies are toggleable. A signal must clear several quality gates before
firing (see *Signal Quality & Tuning* below), not just a single score threshold.

---

## Signal Quality & Tuning

The engine is built to emit **few, high-conviction signals**. Every candidate
must pass, in order: a time-of-day window filter, a minimum directional score,
a "not muddy" ratio, a minimum number of distinct strategy buckets,
higher-timeframe (5m/15m) trend alignment, a conviction grade gate (A/B only by
default), a same-direction cooldown, and a per-day cap.

All knobs live in `engine/config.py` (`DEFAULT_SIGNAL_CONFIG`) and can be
overridden without touching code by adding a `signal_config` block to
`fyers_config.json`, e.g.:

```json
{
  "signal_config": {
    "max_signals_per_day": 4,
    "htf_hard_filter": true,
    "min_time_mult": 0.5,
    "threshold": 3.5,
    "slippage_bps": 3
  }
}
```

Per-request overrides are also accepted via the `signal_config` field in the
analyze/backtest API bodies. Lower the filters (e.g. `htf_hard_filter: false`,
`allow_c_grade: true`) for more signals; raise them for fewer/stronger ones.

---

## Backtesting

Walk-forward replay (no look-ahead): at each candle the engine sees only past
data, and trades are simulated on subsequent candles with configurable slippage
and brokerage. Metrics include win rate, expectancy, profit factor, max
drawdown, **annualized Sharpe**, per-day stats and an equity curve.

```bash
# Backtest an existing session
python backtest_cli.py --session 3

# Download a symbol from Fyers, then backtest it
python backtest_cli.py --symbol NSE:SBIN-EQ --from 2024-01-01 --to 2024-01-31

# Grid-search params and validate out-of-sample (train/test split)
python backtest_cli.py --session 3 --optimize --grid '{"vwap":[true,false],"cvd":[true,false]}'
```

The web UI runs the same backtest automatically after analysis.

---

## API Endpoints

| Method | Path                     | Description                   |
|--------|--------------------------|-------------------------------|
| GET    | `/`                      | Main app UI                   |
| POST   | `/api/upload`            | Upload CSV data, create session |
| POST   | `/api/analyze-v2/<id>`   | Run the signal engine on a session |
| POST   | `/api/backtest/<id>`     | Walk-forward backtest (persists results) |
| GET    | `/api/backtests/<id>`    | List saved backtest runs      |
| POST   | `/api/optimize/<id>`     | Grid search + out-of-sample validation |
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

Edit `engine/signals_v2.py` and add scoring logic inside the `generate_signals_v2()` loop:

```python
# Custom: Price makes higher high + higher low (uptrend continuation)
if config.get('my_strategy'):
    if c['high'] > prev['high'] and c['low'] > prev['low']:
        bull_score += 1.5
        reasons.append('HH/HL Uptrend')
        strategies_hit.append('my_strategy')
```

Then add the toggle in `templates/index.html`:

```html
<label class="strat-row" data-key="my_strategy" data-color="#ff6b9d">
  <input type="checkbox" /> My Custom Strategy
</label>
```

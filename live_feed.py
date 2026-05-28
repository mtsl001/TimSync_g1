"""
live_feed.py — Real-Time Market Data + Signal Engine
======================================================
Connects to Fyers WebSocket, aggregates ticks into
1-min candles, runs V2 signal engine on every new candle,
and alerts you when a trade signal fires.

Usage:
  python live_feed.py               # All watchlist stocks
  python live_feed.py --symbol NSE:SBIN-EQ  # Single stock

How it works:
  1. Loads today's pre-market historical data first (9:00 AM)
  2. Connects to Fyers WebSocket at 9:15 AM
  3. Aggregates ticks → 1-min OHLCV candles as they close
  4. Runs V2 signal engine on every new candle
  5. Prints alerts when Grade A/B signals fire
  6. Web dashboard auto-refreshes via /api/live endpoint
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import threading
from datetime import datetime, date, timedelta
from collections import defaultdict

try:
    from fyers_apiv3.FyersWebsocket import data_ws
except ImportError:
    sys.exit("  ✗ Install: pip install fyers-apiv3")

import database as db
from fyers_client import load_config, FyersClient
from engine.signals_v2 import generate_signals_v2
from engine.strategies import calc_orb

logging.basicConfig(level=logging.WARNING)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE  = os.path.join(SCRIPT_DIR, 'fyers_token.json')

# ── Market hours ──────────────────────────────────────────────────────────────
MARKET_OPEN  = (9, 15)
MARKET_CLOSE = (15, 30)

# ── Config ────────────────────────────────────────────────────────────────────
STRATEGY_CONFIG = {
    'orb': True, 'ema': True, 'vwap': True,
    'volume': True, 'futures': False,
}


# ═══════════════════════════════════════════════════════════
# CANDLE AGGREGATOR
# ═══════════════════════════════════════════════════════════

class CandleAggregator:
    """
    Aggregates real-time ticks into 1-minute OHLCV candles.
    Calls on_candle(symbol, candle) when a minute candle closes.
    """

    def __init__(self, on_candle):
        self.on_candle  = on_candle
        self._buckets   = {}   # symbol → current open bucket
        self._lock      = threading.Lock()

    def _minute_key(self, ts: datetime) -> str:
        return ts.strftime('%Y-%m-%d %H:%M')

    def process_tick(self, symbol: str, ltp: float, volume: int, ts: datetime = None):
        if ts is None:
            ts = datetime.now()

        minute = self._minute_key(ts)

        with self._lock:
            if symbol not in self._buckets:
                self._buckets[symbol] = {'minute': minute, 'open': ltp, 'high': ltp,
                                          'low': ltp, 'close': ltp, 'volume': 0, 'ticks': 0}

            bucket = self._buckets[symbol]

            # New minute — close previous candle
            if bucket['minute'] != minute:
                closed = {
                    'datetime': bucket['minute'],
                    'date':     bucket['minute'][:10],
                    'time':     bucket['minute'][11:],
                    'open':     bucket['open'],
                    'high':     bucket['high'],
                    'low':      bucket['low'],
                    'close':    bucket['close'],
                    'volume':   bucket['volume'],
                }
                # Reset for new minute
                self._buckets[symbol] = {
                    'minute': minute, 'open': ltp, 'high': ltp,
                    'low': ltp, 'close': ltp, 'volume': 0, 'ticks': 0
                }
                # Emit closed candle (outside lock to avoid deadlock)
                threading.Thread(
                    target=self.on_candle,
                    args=(symbol, closed),
                    daemon=True
                ).start()
            else:
                # Update current bucket
                bucket['high']   = max(bucket['high'], ltp)
                bucket['low']    = min(bucket['low'],  ltp)
                bucket['close']  = ltp
                bucket['volume'] += volume
                bucket['ticks']  += 1

    def get_current(self, symbol: str) -> dict | None:
        """Get the currently forming (incomplete) candle."""
        with self._lock:
            b = self._buckets.get(symbol)
            if not b:
                return None
            return {
                'datetime': b['minute'],
                'open': b['open'], 'high': b['high'],
                'low': b['low'], 'close': b['close'],
                'volume': b['volume'],
            }


# ═══════════════════════════════════════════════════════════
# SIGNAL PROCESSOR
# ═══════════════════════════════════════════════════════════

class SignalProcessor:
    """
    Maintains per-symbol candle history and runs V2 signal
    engine whenever a new 1-min candle closes.
    """

    def __init__(self, session_map: dict, capital: float, risk: float):
        self.session_map = session_map   # symbol → session_id
        self.candles     = defaultdict(list)   # symbol → [candle, ...]
        self.capital     = capital
        self.risk        = risk
        self.signal_log  = []   # All signals fired today
        self._lock       = threading.Lock()

    def load_history(self, symbol: str, candles: list[dict]):
        """Pre-load historical candles for a symbol."""
        with self._lock:
            self.candles[symbol] = list(candles)
        print(f"  {symbol.split(':')[1].replace('-EQ',''):<16} {len(candles)} historical candles loaded")

    def on_new_candle(self, symbol: str, candle: dict):
        """Called when a new 1-min candle closes."""
        now = datetime.now()
        h, m = now.hour, now.minute

        # Skip outside market hours
        if not ((9, 15) <= (h, m) <= (15, 30)):
            return

        with self._lock:
            self.candles[symbol].append(candle)
            data = list(self.candles[symbol])

        # Store candle in DB
        session_id = self.session_map.get(symbol)
        if session_id:
            db.store_candles(session_id, [candle], 'cash_live')

        # Need at least 25 candles for signals
        if len(data) < 25:
            return

        # Run V2 signal engine on last 200 candles (enough for context)
        window = data[-200:]
        signals = generate_signals_v2(
            window, None, STRATEGY_CONFIG, self.capital, self.risk
        )

        # Check if newest candle triggered a signal
        if not signals:
            return

        latest = signals[-1]
        if latest['candle_index'] < len(window) - 3:
            return  # Signal is old, not on latest candle

        # New signal — alert!
        self._alert(symbol, latest, candle)

        # Save to DB
        if session_id:
            db.clear_signals(session_id)
            db.store_signals(session_id, signals)

    def _alert(self, symbol: str, sig: dict, candle: dict):
        """Print and store a new signal."""
        name  = symbol.split(':')[1].replace('-EQ', '')
        stype = sig['type']
        grade = sig.get('grade', '?')
        entry = sig['entry']
        sl    = sig['sl']
        t1    = sig['t1']
        qty   = sig['qty']
        score = sig['score']
        reasons = sig.get('reasons', [])

        color = '\033[92m' if stype == 'BUY' else '\033[91m'  # green/red
        reset = '\033[0m'

        print(f"\n  {'═'*55}")
        print(f"  {color}⚡ SIGNAL: {stype} {name}{reset}  [Grade {grade} | Score {score}%]")
        print(f"  {'─'*55}")
        print(f"  Entry ₹{entry}  |  SL ₹{sl}  |  T1 ₹{t1}  |  Qty {qty}")
        print(f"  Time: {candle['datetime']}  |  Regime: {sig.get('regime','?')}  |  HTF: {sig.get('htf_5m','?')}")
        print(f"  Reasons: {', '.join(reasons[:4])}")
        print(f"  {'═'*55}\n")

        self.signal_log.append({
            'time':   candle['datetime'],
            'symbol': name,
            **sig,
        })


# ═══════════════════════════════════════════════════════════
# FYERS WEBSOCKET HANDLER
# ═══════════════════════════════════════════════════════════

class LiveFeed:

    def __init__(self, access_token: str, client_id: str,
                 symbols: list[str], processor: SignalProcessor,
                 aggregator: CandleAggregator):
        self.access_token = f"{client_id}:{access_token}"
        self.symbols      = symbols
        self.processor    = processor
        self.aggregator   = aggregator
        self.fyers        = None
        self.running      = False

    def start(self):
        self.running = True
        self.fyers = data_ws.FyersDataSocket(
            access_token=self.access_token,
            log_path='',
            litemode=True,       # LTP only — faster, lower bandwidth
            write_to_file=False,
            reconnect=True,
            on_connect=self._on_connect,
            on_close=self._on_close,
            on_error=self._on_error,
            on_message=self._on_message,
        )
        print(f"\n  Connecting to Fyers WebSocket...")
        self.fyers.connect()

    def _on_connect(self):
        print(f"  ✓ WebSocket connected — subscribing to {len(self.symbols)} symbols")
        self.fyers.subscribe(symbols=self.symbols, data_type='SymbolUpdate')
        self.fyers.keep_running()

    def _on_message(self, msg):
        """Process incoming tick data."""
        try:
            if not isinstance(msg, dict):
                return
            if msg.get('type') != 'SymbolUpdate':
                return

            symbol = msg.get('symbol', '')
            ltp    = float(msg.get('ltp', 0))
            vol    = int(msg.get('vol_traded_today', 0))

            if not symbol or not ltp:
                return

            self.aggregator.process_tick(symbol, ltp, vol)

        except Exception as e:
            pass   # Silently ignore malformed ticks

    def _on_error(self, msg):
        print(f"  ✗ WebSocket error: {msg}")

    def _on_close(self, msg):
        print(f"  WebSocket closed: {msg}")
        if self.running:
            print("  Reconnecting in 5s...")
            time.sleep(5)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def load_token() -> dict:
    if not os.path.exists(TOKEN_FILE):
        sys.exit("  ✗ No token. Run: python quick_token.py")
    t = json.load(open(TOKEN_FILE))
    if t.get('date') != str(date.today()):
        sys.exit("  ✗ Token expired. Run: python quick_token.py")
    return t


def get_today_sessions(watchlist: list[str]) -> dict:
    """Find today's DB sessions for each symbol."""
    today = str(date.today())
    sessions = db.get_sessions()
    session_map = {}

    for sym in watchlist:
        name = sym.split(':')[1].replace('-EQ', '')
        for s in sessions:
            if s['stock_name'] == name:
                session_map[sym] = s['id']
                break

    return session_map


def load_todays_history(client: FyersClient, symbol: str) -> list[dict]:
    """Fetch today's candles so far (pre-market or partial day)."""
    today = str(date.today())
    candles = client.fetch_history(symbol, '1', today, today)
    return candles


def main():
    parser = argparse.ArgumentParser(description='Fyers Live Feed')
    parser.add_argument('--symbol', type=str, default='', help='Single symbol')
    parser.add_argument('--no-history', action='store_true', help='Skip loading today history')
    args = parser.parse_args()

    print("\n  ⚡ Live Feed — Real-Time Signal Engine")
    print("  ══════════════════════════════════════\n")

    # ── Load credentials ──
    token   = load_token()
    config  = load_config()
    capital = config.get('capital', 25000)
    risk    = config.get('risk_per_trade', 500)

    watchlist = [args.symbol] if args.symbol else config.get('watchlist', [])
    if not watchlist:
        sys.exit("  ✗ No symbols. Run: python set_watchlist.py")

    print(f"  Symbols:  {len(watchlist)} stocks")
    print(f"  Capital:  ₹{capital:,}")
    print(f"  Risk:     ₹{risk:,}/trade")
    print(f"  Strategies: ORB ✓  EMA ✓  VWAP ✓  Volume ✓\n")

    db.init_db()

    # ── Find today's sessions in DB ──
    session_map = get_today_sessions(watchlist)
    print(f"  Found {len(session_map)}/{len(watchlist)} existing sessions in DB")

    # ── Set up aggregator + processor ──
    processor  = SignalProcessor(session_map, capital, risk)
    aggregator = CandleAggregator(processor.on_new_candle)

    # ── Load today's history ──
    if not args.no_history:
        print("\n  Loading today's historical candles...")
        client = FyersClient(config['client_id'], token['access_token'])

        for sym in watchlist:
            # First load historical candles from DB (previous days)
            session_id = session_map.get(sym)
            if session_id:
                hist = db.get_candles(session_id, 'cash_1')
                if hist:
                    processor.load_history(sym, hist)

            # Then fetch today's candles from Fyers
            try:
                today_candles = load_todays_history(client, sym)
                if today_candles:
                    with processor._lock:
                        processor.candles[sym].extend(today_candles)
                    print(f"  + {sym.split(':')[1].replace('-EQ',''):<16} {len(today_candles)} candles today")
            except Exception as e:
                print(f"  ⚠ {sym}: {e}")

    # ── Check market hours ──
    now = datetime.now()
    h, m = now.hour, now.minute

    if (h, m) < MARKET_OPEN:
        wait_mins = (MARKET_OPEN[0] * 60 + MARKET_OPEN[1]) - (h * 60 + m)
        print(f"\n  Market opens at 09:15. Waiting {wait_mins} min...")
        time.sleep(wait_mins * 60)

    elif (h, m) >= MARKET_CLOSE:
        print(f"\n  Market is closed (after 15:30).")
        print(f"  Run this script before or during market hours.")
        print(f"  For historical analysis: use python app.py")
        return

    # ── Start WebSocket ──
    feed = LiveFeed(
        token['access_token'],
        token['client_id'],
        watchlist,
        processor,
        aggregator,
    )

    def on_exit(sig, frame):
        print("\n\n  Stopping live feed...")
        feed.running = False
        print(f"  Signals today: {len(processor.signal_log)}")
        for s in processor.signal_log:
            print(f"    {s['time']} {s['type']} {s['symbol']} ₹{s['entry']} Grade:{s.get('grade','?')}")
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)

    print(f"\n  ✓ Starting live feed at {now.strftime('%H:%M:%S')}")
    print(f"  Watching {len(watchlist)} symbols for Grade A/B signals")
    print(f"  Press Ctrl+C to stop\n")

    feed.start()


if __name__ == '__main__':
    main()
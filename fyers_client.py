"""
fyers_client.py — Fyers API V3 Integration
=============================================
Handles authentication, historical data download with
pagination, multi-stock batch downloading, and
rate-limit compliance.

Fyers History API response format:
  {'s': 'ok', 'candles': [[epoch, open, high, low, close, volume], ...]}

Resolution codes:
  '1'  = 1 minute   (max ~100 days per call)
  '5'  = 5 minutes
  '15' = 15 minutes
  '60' = 1 hour
  'D'  = Daily

Symbol format:
  Cash:    'NSE:SBIN-EQ'
  Futures: 'NSE:SBIN25JUNFUT'
  Index:   'NSE:NIFTY50-INDEX', 'NSE:NIFTYBANK-INDEX'
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

try:
    from fyers_apiv3 import fyersModel
    HAS_FYERS_SDK = True
except ImportError:
    HAS_FYERS_SDK = False

import database as db

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'fyers_config.json')

# Max days per API call by resolution
MAX_DAYS = {
    '1':  30,   # 1-min: Fyers allows ~100 days but 30 is safer per chunk
    '5':  60,
    '15': 90,
    '60': 100,
    'D':  365,
}

# Rate limit: Fyers allows ~10 requests/sec, we'll be conservative
RATE_LIMIT_DELAY = 0.3  # seconds between API calls

# Default stocks in ₹500-1000 range for tracking
DEFAULT_WATCHLIST = [
    'NSE:FEDERALBNK-EQ',
    'NSE:BANDHANBNK-EQ',
    'NSE:IDFCFIRSTB-EQ',
    'NSE:ESCORTS-EQ',
    'NSE:BALKRISIND-EQ',
    'NSE:MPHASIS-EQ',
    'NSE:COFORGE-EQ',
    'NSE:PERSISTENT-EQ',
    'NSE:ALKEM-EQ',
    'NSE:TORNTPHARM-EQ',
    'NSE:CUMMINSIND-EQ',
    'NSE:THERMAX-EQ',
]

INDEX_SYMBOLS = {
    'NIFTY':     'NSE:NIFTY50-INDEX',
    'BANKNIFTY': 'NSE:NIFTYBANK-INDEX',
    'NIFTYIT':   'NSE:NIFTYIT-INDEX',
}


# ═══════════════════════════════════════════════════════════
# CONFIG MANAGEMENT
# ═══════════════════════════════════════════════════════════

def load_config() -> dict:
    """Load saved Fyers config (client_id, access_token, watchlist)."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'client_id': '',
        'access_token': '',
        'watchlist': DEFAULT_WATCHLIST,
        'index_symbol': 'NSE:NIFTY50-INDEX',
        'capital': 25000,
        'risk_per_trade': 500,
    }


def save_config(config: dict):
    """Save Fyers config to disk."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# ═══════════════════════════════════════════════════════════
# FYERS CLIENT
# ═══════════════════════════════════════════════════════════

class FyersClient:
    """Wrapper around Fyers API V3 for historical data."""

    def __init__(self, client_id: str = '', access_token: str = ''):
        self.client_id = client_id
        self.access_token = access_token
        self.fyers = None
        self._last_call = 0

        if client_id and access_token and HAS_FYERS_SDK:
            self._connect()

    def _connect(self):
        """Initialize Fyers SDK model."""
        try:
            self.fyers = fyersModel.FyersModel(
                client_id=self.client_id,
                is_async=False,
                token=self.access_token,
                log_path=''
            )
            logger.info("Fyers SDK connected")
        except Exception as e:
            logger.error(f"Fyers connection failed: {e}")
            self.fyers = None

    def is_connected(self) -> bool:
        return self.fyers is not None

    def test_connection(self) -> dict:
        """Test API connection by fetching profile."""
        if not self.fyers:
            return {'status': 'error', 'message': 'SDK not initialized'}
        try:
            profile = self.fyers.get_profile()
            if profile.get('s') == 'ok':
                return {'status': 'ok', 'profile': profile.get('data', {})}
            return {'status': 'error', 'message': profile.get('message', 'Unknown error')}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self._last_call
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call = time.time()

    # ── History Data ──────────────────────────────────────────

    def fetch_history(
        self,
        symbol: str,
        resolution: str = '1',
        from_date: str = '',
        to_date: str = '',
    ) -> list[dict]:
        """
        Fetch historical OHLCV candles for a single symbol.
        Handles pagination (splits into chunks if date range > max).

        Args:
            symbol:     Fyers symbol e.g. 'NSE:SBIN-EQ'
            resolution: '1', '5', '15', '60', 'D'
            from_date:  'YYYY-MM-DD'
            to_date:    'YYYY-MM-DD'

        Returns:
            List of candle dicts: [{datetime, open, high, low, close, volume}, ...]
        """
        if not self.fyers:
            raise ConnectionError("Fyers SDK not initialized. Set client_id and access_token.")

        if not to_date:
            to_date = datetime.now().strftime('%Y-%m-%d')
        if not from_date:
            days_back = MAX_DAYS.get(resolution, 30)
            from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        start = datetime.strptime(from_date, '%Y-%m-%d')
        end   = datetime.strptime(to_date, '%Y-%m-%d')
        chunk_days = MAX_DAYS.get(resolution, 30)

        all_candles = []
        current_start = start

        while current_start < end:
            current_end = min(current_start + timedelta(days=chunk_days - 1), end)

            self._rate_limit()

            data = {
                'symbol':      symbol,
                'resolution':  resolution,
                'date_format': '1',  # YYYY-MM-DD format
                'range_from':  current_start.strftime('%Y-%m-%d'),
                'range_to':    current_end.strftime('%Y-%m-%d'),
                'cont_flag':   '1',
            }

            logger.info(f"Fetching {symbol} {resolution}m: {data['range_from']} → {data['range_to']}")

            try:
                response = self.fyers.history(data=data)
            except Exception as e:
                logger.error(f"API call failed: {e}")
                current_start = current_end + timedelta(days=1)
                continue

            if response.get('s') != 'ok':
                logger.warning(f"API error: {response.get('message', response.get('s'))}")
                current_start = current_end + timedelta(days=1)
                continue

            raw_candles = response.get('candles', [])
            for c in raw_candles:
                # c = [epoch, open, high, low, close, volume]
                if len(c) < 6:
                    continue
                epoch = c[0]
                dt = datetime.fromtimestamp(epoch)
                all_candles.append({
                    'datetime':  dt.strftime('%Y-%m-%d %H:%M'),
                    'date':      dt.strftime('%Y-%m-%d'),
                    'time':      dt.strftime('%H:%M'),
                    'epoch':     epoch,
                    'open':      round(float(c[1]), 2),
                    'high':      round(float(c[2]), 2),
                    'low':       round(float(c[3]), 2),
                    'close':     round(float(c[4]), 2),
                    'volume':    int(c[5]),
                })

            logger.info(f"  → Got {len(raw_candles)} candles")
            current_start = current_end + timedelta(days=1)

        # Remove duplicates (overlapping chunks)
        seen_epochs = set()
        unique = []
        for c in all_candles:
            if c['epoch'] not in seen_epochs:
                seen_epochs.add(c['epoch'])
                unique.append(c)

        unique.sort(key=lambda x: x['epoch'])
        logger.info(f"Total: {len(unique)} unique candles for {symbol} @ {resolution}m")
        return unique

    # ── Batch Download ────────────────────────────────────────

    def fetch_multi_tf(
        self,
        symbol: str,
        from_1m: str = '',
        to_date: str = '',
        from_15m: str = '',
        from_1h: str = '',
    ) -> dict:
        """
        Fetch all 3 timeframes for a single stock.

        Args:
            symbol:  Fyers symbol
            from_1m: Start date for 1-min data (default: 1 month ago)
            to_date: End date for all (default: today)
            from_15m: Start for 15-min (default: 3 months ago)
            from_1h:  Start for 1-hour (default: 3 months ago)

        Returns:
            {'1m': [...], '15m': [...], '1h': [...]}
        """
        today = datetime.now()
        if not to_date:
            to_date = today.strftime('%Y-%m-%d')
        if not from_1m:
            from_1m = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        if not from_15m:
            from_15m = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        if not from_1h:
            from_1h = (today - timedelta(days=90)).strftime('%Y-%m-%d')

        result = {}

        logger.info(f"=== Downloading {symbol} ===")

        result['1m'] = self.fetch_history(symbol, '1', from_1m, to_date)
        result['15m'] = self.fetch_history(symbol, '15', from_15m, to_date)
        result['1h'] = self.fetch_history(symbol, '60', from_1h, to_date)

        logger.info(f"  1m:  {len(result['1m'])} candles")
        logger.info(f"  15m: {len(result['15m'])} candles")
        logger.info(f"  1h:  {len(result['1h'])} candles")

        return result

    def fetch_watchlist(
        self,
        symbols: list[str],
        from_1m: str = '',
        to_date: str = '',
        from_htf: str = '',
        include_index: bool = True,
        index_symbol: str = 'NSE:NIFTY50-INDEX',
    ) -> dict:
        """
        Batch download all timeframes for the full watchlist + index.

        Returns:
            {
                'NSE:SBIN-EQ': {'1m': [...], '15m': [...], '1h': [...]},
                'NSE:NIFTY50-INDEX': {'1m': [...], '15m': [...], '1h': [...]},
                ...
            }
        """
        results = {}
        all_symbols = list(symbols)

        if include_index and index_symbol not in all_symbols:
            all_symbols.append(index_symbol)

        total = len(all_symbols)
        for i, sym in enumerate(all_symbols):
            logger.info(f"[{i+1}/{total}] {sym}")
            try:
                results[sym] = self.fetch_multi_tf(sym, from_1m, to_date, from_htf, from_htf)
            except Exception as e:
                logger.error(f"  FAILED: {e}")
                results[sym] = {'1m': [], '15m': [], '1h': []}

        return results


# ═══════════════════════════════════════════════════════════
# DATABASE INTEGRATION
# ═══════════════════════════════════════════════════════════

def store_fyers_data(session_id: int, candles: list[dict], segment: str, timeframe: str):
    """
    Store Fyers candles into the database.
    segment:   'cash', 'futures', 'index'
    timeframe: '1', '15', '60'
    """
    db_candles = [{
        'datetime': c['datetime'],
        'open':     c['open'],
        'high':     c['high'],
        'low':      c['low'],
        'close':    c['close'],
        'volume':   c['volume'],
    } for c in candles]

    # Store with type encoded as segment_timeframe (e.g., 'cash_1', 'cash_15', 'index_60')
    db_type = f"{segment}_{timeframe}"
    db.store_candles(session_id, db_candles, db_type)


def download_and_store(
    client: FyersClient,
    symbol: str,
    capital: float = 25000,
    risk: float = 500,
    from_1m: str = '',
    to_date: str = '',
    from_htf: str = '',
    futures_symbol: str = '',
    index_symbol: str = 'NSE:NIFTY50-INDEX',
) -> int:
    """
    Full pipeline: download from Fyers → store in SQLite → return session_id.
    """
    # Clean stock name from symbol
    stock_name = symbol.split(':')[-1].replace('-EQ', '').replace('-INDEX', '')

    # Create session
    session_id = db.create_session(stock_name, capital, risk)

    # Fetch cash data (all timeframes)
    data = client.fetch_multi_tf(symbol, from_1m, to_date, from_htf, from_htf)

    # Store each timeframe
    for tf_label, tf_code in [('1m', '1'), ('15m', '15'), ('1h', '60')]:
        if data.get(tf_label):
            store_fyers_data(session_id, data[tf_label], 'cash', tf_code)
            logger.info(f"  Stored {len(data[tf_label])} {tf_label} candles → session {session_id}")

    # Fetch futures data if symbol provided
    if futures_symbol:
        try:
            fut_data = client.fetch_history(futures_symbol, '1', from_1m, to_date)
            if fut_data:
                store_fyers_data(session_id, fut_data, 'futures', '1')
                logger.info(f"  Stored {len(fut_data)} futures 1m candles")
        except Exception as e:
            logger.warning(f"  Futures fetch failed: {e}")

    # Fetch index data
    if index_symbol:
        try:
            idx_data = client.fetch_multi_tf(index_symbol, from_1m, to_date, from_htf, from_htf)
            for tf_label, tf_code in [('1m', '1'), ('15m', '15'), ('1h', '60')]:
                if idx_data.get(tf_label):
                    store_fyers_data(session_id, idx_data[tf_label], 'index', tf_code)
        except Exception as e:
            logger.warning(f"  Index fetch failed: {e}")

    return session_id


# ═══════════════════════════════════════════════════════════
# HELPER: SPLIT DATA BY TRADING DATES
# ═══════════════════════════════════════════════════════════

def split_by_date(candles: list[dict]) -> dict[str, list[dict]]:
    """
    Split a multi-day candle list into per-day lists.
    Returns: {'2024-01-15': [...candles...], '2024-01-16': [...], ...}
    """
    by_date = {}
    for c in candles:
        d = c.get('date', c.get('datetime', '')[:10])
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(c)
    return by_date


def get_trading_dates(candles: list[dict]) -> list[str]:
    """Get sorted list of unique trading dates."""
    dates = sorted(set(c.get('date', c.get('datetime', '')[:10]) for c in candles))
    return dates

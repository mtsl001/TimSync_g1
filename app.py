"""
Trade Signal Engine — Flask Backend
=====================================
Run:  python app.py
Open: http://localhost:5000
"""

import io
import csv
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template
import database as db
from engine.strategies import compute_all, calc_orb
from engine.signals import generate_signals
from engine.signals_v2 import generate_signals_v2
from engine.backtester import backtest_session
from engine.advanced import find_support_resistance, analyze_opening_gap
from engine.filters import detect_market_regime

app = Flask(__name__)


# ─── Helper ───────────────────────────────────────────────────────────────────

def parse_csv_text(text: str) -> list[dict] | None:
    """Parse CSV text into list of OHLCV dicts. Flexible column names."""
    try:
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            return None
        reader = csv.DictReader(io.StringIO('\n'.join(lines)))
        candles = []
        aliases = {
            'datetime': ['datetime', 'date', 'time', 'timestamp', 'dt'],
            'open':     ['open', 'o'],
            'high':     ['high', 'h'],
            'low':      ['low', 'l'],
            'close':    ['close', 'c', 'ltp'],
            'volume':   ['volume', 'vol', 'v', 'qty'],
        }

        def find_col(row, field):
            for k in row:
                if k.lower().strip() in aliases[field]:
                    return k
            return None

        for row in reader:
            try:
                c = {
                    'datetime': row.get(find_col(row, 'datetime') or '', f"R{len(candles)}"),
                    'open':     float(row[find_col(row, 'open')]),
                    'high':     float(row[find_col(row, 'high')]),
                    'low':      float(row[find_col(row, 'low')]),
                    'close':    float(row[find_col(row, 'close')]),
                    'volume':   int(float(row.get(find_col(row, 'volume') or '', 0) or 0)),
                }
                candles.append(c)
            except Exception:
                continue

        return candles if len(candles) >= 5 else None
    except Exception:
        return None


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    return jsonify(db.get_sessions())


@app.route('/api/upload', methods=['POST'])
def upload():
    data = request.get_json(force=True)
    stock_name   = data.get('stock_name', 'UNKNOWN').upper()
    capital      = float(data.get('capital', 25000))
    risk         = float(data.get('risk', 500))
    cash_csv     = data.get('cash_csv', '')
    futures_csv  = data.get('futures_csv', '')

    cash = parse_csv_text(cash_csv)
    if not cash:
        return jsonify({'error': 'Could not parse cash CSV. Required columns: datetime,open,high,low,close,volume'}), 400

    fut = parse_csv_text(futures_csv) if futures_csv.strip() else None

    session_id = db.create_session(stock_name, capital, risk)
    db.store_candles(session_id, cash, 'cash')
    if fut:
        db.store_candles(session_id, fut, 'futures')

    return jsonify({
        'session_id':    session_id,
        'stock_name':    stock_name,
        'candle_count':  len(cash),
        'has_futures':   fut is not None,
        'futures_count': len(fut) if fut else 0,
    })


@app.route('/api/analyze/<int:session_id>', methods=['POST'])
def analyze(session_id):
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    config = request.get_json(force=True).get('strategies', {
        'orb': True, 'ema': True, 'vwap': True, 'volume': True, 'futures': False,
    })

    cash    = db.get_candles(session_id, 'cash')
    futures = db.get_candles(session_id, 'futures')

    sigs = generate_signals(cash, futures or None, config, session['capital'], session['risk'])

    db.clear_signals(session_id)
    db.store_signals(session_id, sigs)

    return jsonify({'signals': sigs, 'count': len(sigs)})


@app.route('/api/analyze-v2/<int:session_id>', methods=['POST'])
def analyze_v2(session_id):
    """Enhanced V2 analysis with all advanced filters."""
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    body = request.get_json(force=True)
    config = body.get('strategies', {
        'orb': True, 'ema': True, 'vwap': True, 'volume': True, 'futures': False,
    })

    # Try both CSV and Fyers data formats
    cash = db.get_candles(session_id, 'cash') or db.get_candles(session_id, 'cash_1')
    futures = db.get_candles(session_id, 'futures') or db.get_candles(session_id, 'futures_1')
    index_d = db.get_candles(session_id, 'index_1')

    if not cash:
        return jsonify({'error': 'No cash data found for this session'}), 404

    sigs = generate_signals_v2(
        cash, futures or None, config,
        session['capital'], session['risk'], index_d or None
    )

    db.clear_signals(session_id)
    db.store_signals(session_id, sigs)

    # Market context
    regime = detect_market_regime(cash, len(cash) - 1) if cash else {}
    gap    = analyze_opening_gap(cash) if cash else {}

    # Data availability info
    has_15m = bool(db.get_candles(session_id, 'cash_15'))
    has_1h  = bool(db.get_candles(session_id, 'cash_60'))

    return jsonify({
        'signals': sigs,
        'count':   len(sigs),
        'regime':  regime,
        'gap':     gap,
        'data_source': {
            'cash_candles':  len(cash),
            'has_futures':   bool(futures),
            'has_index':     bool(index_d),
            'has_15m':       has_15m,
            'has_1h':        has_1h,
        },
    })


@app.route('/api/backtest/<int:session_id>', methods=['POST'])
def backtest(session_id):
    """Run walk-forward backtest on session data."""
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    body = request.get_json(force=True)
    config = body.get('strategies', {
        'orb': True, 'ema': True, 'vwap': True, 'volume': True, 'futures': False,
    })

    cash    = db.get_candles(session_id, 'cash')
    futures = db.get_candles(session_id, 'futures')

    result = backtest_session(
        cash, futures or None, config,
        session['capital'], session['risk']
    )

    return jsonify(result)


@app.route('/api/sr-levels/<int:session_id>', methods=['GET'])
def sr_levels(session_id):
    """Get support/resistance levels for charting."""
    cash = db.get_candles(session_id, 'cash')
    if not cash:
        return jsonify({'supports': [], 'resistances': []})
    sr = find_support_resistance(cash, len(cash) - 1, 60)
    return jsonify(sr)


@app.route('/api/chart-data/<int:session_id>', methods=['GET'])
def chart_data(session_id):
    # Support both CSV-uploaded ('cash') and Fyers-fetched ('cash_1') data
    cash = db.get_candles(session_id, 'cash')
    if not cash:
        cash = db.get_candles(session_id, 'cash_1')
    if not cash:
        return jsonify({'error': 'No data'}), 404

    indicators = compute_all(cash)
    orb        = calc_orb(cash, 15)
    sigs       = db.get_signals(session_id)

    # Merge indicators into candle list for charting
    merged = []
    for i, c in enumerate(cash):
        merged.append({
            **c,
            'ema9':  indicators['ema9'][i]  if i < len(indicators['ema9'])  else None,
            'ema21': indicators['ema21'][i] if i < len(indicators['ema21']) else None,
            'ema50': indicators['ema50'][i] if i < len(indicators['ema50']) else None,
            'vwap':  indicators['vwap'][i]  if i < len(indicators['vwap'])  else None,
            'atr':   indicators['atr'][i]   if i < len(indicators['atr'])   else None,
        })

    # Check for higher-TF data availability
    has_15m = bool(db.get_candles(session_id, 'cash_15'))
    has_1h  = bool(db.get_candles(session_id, 'cash_60'))
    has_idx = bool(db.get_candles(session_id, 'index_1'))

    session = db.get_session(session_id)
    return jsonify({
        'candles':    merged,
        'orb':        orb,
        'signals':    sigs,
        'session':    session,
        'data_info':  {
            'has_15m':  has_15m,
            'has_1h':   has_1h,
            'has_index': has_idx,
            'source':   'fyers' if has_15m else 'csv',
        },
    })


@app.route('/api/signals/<int:session_id>', methods=['GET'])
def get_signals(session_id):
    return jsonify(db.get_signals(session_id))


@app.route('/api/journal', methods=['GET'])
def get_journal():
    session_id = request.args.get('session_id', type=int)
    return jsonify(db.get_journal(session_id))


@app.route('/api/journal', methods=['POST'])
def add_journal():
    data = request.get_json(force=True)
    entry_id = db.add_journal_entry(data)
    return jsonify({'id': entry_id, 'ok': True})


@app.route('/api/journal/<int:entry_id>', methods=['DELETE'])
def delete_journal(entry_id):
    db.delete_journal_entry(entry_id)
    return jsonify({'ok': True})


@app.route('/api/stats/<int:session_id>', methods=['GET'])
def get_stats(session_id):
    journal = db.get_journal(session_id)
    total  = len(journal)
    wins   = sum(1 for j in journal if j['pnl'] and float(j['pnl']) > 0)
    losses = sum(1 for j in journal if j['pnl'] and float(j['pnl']) < 0)
    total_pnl = sum(float(j['pnl']) for j in journal if j['pnl'])
    win_rate  = round(wins / total * 100, 1) if total > 0 else 0
    return jsonify({
        'total_trades': total,
        'wins':         wins,
        'losses':       losses,
        'win_rate':     win_rate,
        'total_pnl':    round(total_pnl, 2),
    })


@app.route('/api/live/signals', methods=['GET'])
def live_signals():
    """Get latest signals across all sessions — for live monitoring."""
    sessions = db.get_sessions()
    all_signals = []
    for s in sessions[:25]:  # Top 25 sessions
        sigs = db.get_signals(s['id'])
        for sig in sigs[-2:]:  # Latest 2 signals per stock
            sig['stock_name'] = s['stock_name']
            all_signals.append(sig)
    all_signals.sort(key=lambda x: x.get('score', 0), reverse=True)
    return jsonify(all_signals[:20])  # Top 20 by score


@app.route('/api/live/today', methods=['POST'])
def fetch_today():
    """Fetch today's candles from Fyers for a session."""
    from fyers_client import FyersClient, load_config
    data = request.get_json(force=True)
    session_id = data.get('session_id')
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    config = load_config()
    if not config.get('access_token'):
        return jsonify({'error': 'No token'}), 400

    # Build symbol from stock name
    symbol = f"NSE:{session['stock_name']}-EQ"
    today  = datetime.now().strftime('%Y-%m-%d')

    client = FyersClient(config['client_id'], config['access_token'])
    try:
        candles = client.fetch_history(symbol, '1', today, today)
        if candles:
            db.store_candles(session_id, candles, 'cash_live')
        return jsonify({'count': len(candles), 'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fyers/config', methods=['GET'])
def fyers_get_config():
    from fyers_client import load_config
    config = load_config()
    safe = {**config}
    if safe.get('access_token'):
        safe['access_token'] = safe['access_token'][:8] + '...' + safe['access_token'][-4:]
        safe['has_token'] = True
    else:
        safe['has_token'] = False
    return jsonify(safe)


@app.route('/api/fyers/config', methods=['POST'])
def fyers_set_config():
    from fyers_client import save_config, load_config
    data = request.get_json(force=True)
    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({'ok': True})


@app.route('/api/fyers/test', methods=['POST'])
def fyers_test():
    from fyers_client import FyersClient, load_config
    config = load_config()
    data = request.get_json(force=True)
    client_id = data.get('client_id') or config.get('client_id', '')
    token = data.get('access_token') or config.get('access_token', '')
    if not client_id or not token:
        return jsonify({'status': 'error', 'message': 'Missing credentials'})
    client = FyersClient(client_id, token)
    return jsonify(client.test_connection())


@app.route('/api/fyers/download', methods=['POST'])
def fyers_download():
    from fyers_client import FyersClient, load_config, download_and_store
    config = load_config()
    if not config.get('client_id') or not config.get('access_token'):
        return jsonify({'error': 'Fyers not configured'}), 400
    data = request.get_json(force=True)
    symbol = data.get('symbol', '')
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    client = FyersClient(config['client_id'], config['access_token'])
    if not client.is_connected():
        return jsonify({'error': 'SDK not available. pip install fyers-apiv3'}), 400
    try:
        sid = download_and_store(
            client, symbol, config.get('capital', 25000), config.get('risk_per_trade', 500),
            data.get('from_1m', ''), data.get('to_date', ''), data.get('from_htf', ''),
            data.get('futures_symbol', ''),
            data.get('index_symbol', config.get('index_symbol', 'NSE:NIFTY50-INDEX')),
        )
        return jsonify({'session_id': sid, 'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fyers/download-watchlist', methods=['POST'])
def fyers_download_watchlist():
    from fyers_client import FyersClient, load_config, download_and_store
    config = load_config()
    if not config.get('client_id') or not config.get('access_token'):
        return jsonify({'error': 'Not configured'}), 400
    client = FyersClient(config['client_id'], config['access_token'])
    if not client.is_connected():
        return jsonify({'error': 'SDK unavailable'}), 400
    watchlist = config.get('watchlist', [])
    data = request.get_json(force=True)
    results = {}
    for i, sym in enumerate(watchlist):
        try:
            sid = download_and_store(
                client, sym, config.get('capital', 25000), config.get('risk_per_trade', 500),
                data.get('from_1m', ''), data.get('to_date', ''), data.get('from_htf', ''),
                index_symbol=config.get('index_symbol', '') if i == 0 else '',
            )
            results[sym] = {'session_id': sid, 'ok': True}
        except Exception as e:
            results[sym] = {'error': str(e)}
    return jsonify({'results': results})


# ─── Entry ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    db.init_db()
    print("\n  ⚡ Trade Signal Engine")
    print("  ─────────────────────────────")
    print("  Running at: http://localhost:5000\n")
    app.run(debug=True, port=5000)
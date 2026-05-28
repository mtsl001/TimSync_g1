#!/usr/bin/env python3
"""
fetch_data.py — CLI tool to batch download data from Fyers
============================================================

Usage:
  python fetch_data.py --setup           # First time: set API credentials
  python fetch_data.py --download        # Download data for all watchlist stocks
  python fetch_data.py --download --symbol NSE:SBIN-EQ   # Single stock
  python fetch_data.py --status          # Show download status
  python fetch_data.py --watchlist       # Show/edit watchlist

Prerequisites:
  1. pip install fyers-apiv3
  2. Create an app at https://myapi.fyers.in/dashboard/
  3. Generate access_token via Fyers login flow
"""

import argparse
import logging
import json
import sys
from datetime import datetime, timedelta

import database as db
from fyers_client import (
    FyersClient, load_config, save_config,
    download_and_store, DEFAULT_WATCHLIST, INDEX_SYMBOLS,
    split_by_date, get_trading_dates
)

logging.basicConfig(
    level=logging.INFO,
    format='  %(message)s',
)
logger = logging.getLogger(__name__)


BANNER = """
  ⚡ Trade Signal Engine — Data Fetcher
  ═══════════════════════════════════════
"""


def cmd_setup():
    """Interactive setup for Fyers API credentials."""
    print(BANNER)
    print("  STEP 1: Fyers API Credentials")
    print("  ─────────────────────────────────")
    print("  Create an app at: https://myapi.fyers.in/dashboard/")
    print("  Then generate an access token using the OAuth flow.\n")

    config = load_config()

    client_id = input(f"  Client ID [{config.get('client_id', '')}]: ").strip()
    if client_id:
        config['client_id'] = client_id

    access_token = input(f"  Access Token [{'*'*20 if config.get('access_token') else ''}]: ").strip()
    if access_token:
        config['access_token'] = access_token

    if not config.get('client_id') or not config.get('access_token'):
        print("\n  ⚠ Both client_id and access_token are required.")
        return

    # Test connection
    print("\n  Testing connection...")
    try:
        from fyers_apiv3 import fyersModel
    except ImportError:
        print("  ⚠ fyers_apiv3 not installed. Run: pip install fyers-apiv3")
        return

    client = FyersClient(config['client_id'], config['access_token'])
    result = client.test_connection()

    if result['status'] == 'ok':
        name = result.get('profile', {}).get('name', 'User')
        print(f"  ✓ Connected as: {name}")
    else:
        print(f"  ✗ Connection failed: {result['message']}")
        print("  Token may be expired. Generate a new one at Fyers dashboard.")
        return

    # Watchlist
    print("\n  STEP 2: Stock Watchlist")
    print("  ─────────────────────────────────")
    print(f"  Current watchlist ({len(config.get('watchlist', []))} stocks):")
    for s in config.get('watchlist', DEFAULT_WATCHLIST):
        print(f"    {s}")

    edit = input("\n  Edit watchlist? (y/N): ").strip().lower()
    if edit == 'y':
        print("  Enter symbols one per line (empty line to finish):")
        print("  Format: NSE:SYMBOL-EQ (e.g., NSE:SBIN-EQ)")
        symbols = []
        while True:
            sym = input("    > ").strip().upper()
            if not sym:
                break
            if ':' not in sym:
                sym = f"NSE:{sym}-EQ"
            symbols.append(sym)
        if symbols:
            config['watchlist'] = symbols

    # Capital
    capital = input(f"\n  Capital [{config.get('capital', 25000)}]: ").strip()
    if capital:
        config['capital'] = float(capital)

    risk = input(f"  Risk per trade [{config.get('risk_per_trade', 500)}]: ").strip()
    if risk:
        config['risk_per_trade'] = float(risk)

    # Index
    print(f"\n  Index for relative strength: {config.get('index_symbol', 'NSE:NIFTY50-INDEX')}")
    idx = input("  Change? (enter symbol or press Enter to keep): ").strip()
    if idx:
        config['index_symbol'] = idx

    save_config(config)
    print("\n  ✓ Configuration saved to fyers_config.json")
    print("  Run: python fetch_data.py --download")


def cmd_download(symbol: str = None):
    """Download historical data from Fyers."""
    print(BANNER)

    config = load_config()
    if not config.get('client_id') or not config.get('access_token'):
        print("  ⚠ No API credentials. Run: python fetch_data.py --setup")
        return

    db.init_db()

    client = FyersClient(config['client_id'], config['access_token'])
    if not client.is_connected():
        print("  ⚠ Could not connect to Fyers. Check credentials.")
        return

    today = datetime.now()
    to_date  = today.strftime('%Y-%m-%d')
    from_1m  = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    from_htf = (today - timedelta(days=90)).strftime('%Y-%m-%d')

    symbols = [symbol] if symbol else config.get('watchlist', DEFAULT_WATCHLIST)
    index_sym = config.get('index_symbol', 'NSE:NIFTY50-INDEX')
    capital = config.get('capital', 25000)
    risk = config.get('risk_per_trade', 500)

    print(f"  📅 1-min data:  {from_1m} → {to_date} (1 month)")
    print(f"  📅 15m/1h data: {from_htf} → {to_date} (3 months)")
    print(f"  📊 Stocks: {len(symbols)}")
    print(f"  📈 Index: {index_sym}")
    print(f"  💰 Capital: ₹{capital:,.0f} | Risk: ₹{risk:,.0f}/trade")
    print()

    results = {}

    for i, sym in enumerate(symbols):
        print(f"  [{i+1}/{len(symbols)}] Downloading {sym}...")
        try:
            sid = download_and_store(
                client, sym, capital, risk,
                from_1m, to_date, from_htf,
                index_symbol=index_sym if i == 0 else '',  # Index only once
            )
            results[sym] = sid
            print(f"    ✓ Session #{sid} created\n")
        except Exception as e:
            print(f"    ✗ Failed: {e}\n")
            results[sym] = None

    # Summary
    print("  ═══════════════════════════════════════")
    print("  DOWNLOAD COMPLETE")
    print("  ─────────────────────────────────────")
    success = sum(1 for v in results.values() if v)
    print(f"  ✓ {success}/{len(symbols)} stocks downloaded")
    for sym, sid in results.items():
        status = f"Session #{sid}" if sid else "FAILED"
        print(f"    {sym}: {status}")

    print(f"\n  Start the app: python app.py")
    print(f"  Open: http://localhost:5000")
    print(f"  Select sessions from the dropdown to analyze.\n")


def cmd_status():
    """Show current download status."""
    print(BANNER)
    db.init_db()

    sessions = db.get_sessions()
    if not sessions:
        print("  No sessions found. Run: python fetch_data.py --download")
        return

    print(f"  {len(sessions)} sessions in database:\n")
    print(f"  {'ID':>4}  {'Stock':<16} {'Date':<12} {'Candles':>8} {'Signals':>8}")
    print(f"  {'─'*4}  {'─'*16} {'─'*12} {'─'*8} {'─'*8}")

    for s in sessions:
        print(f"  {s['id']:4d}  {s['stock_name']:<16} {s['date']:<12} "
              f"{s['candle_count']:>8} {s['signal_count']:>8}")


def cmd_watchlist():
    """Show current watchlist."""
    print(BANNER)
    config = load_config()
    watchlist = config.get('watchlist', DEFAULT_WATCHLIST)
    print(f"  Current watchlist ({len(watchlist)} stocks):\n")
    for i, s in enumerate(watchlist, 1):
        print(f"  {i:2d}. {s}")
    print(f"\n  Edit with: python fetch_data.py --setup")

def cmd_analyze_all():
    """Run V2 analysis on all real sessions."""
    print(BANNER)
    print("  Running V2 analysis on all sessions...\n")

    db.init_db()
    from engine.signals_v2 import generate_signals_v2

    sessions = db.get_sessions()

    # Remove DEMO / test sessions
    sessions = [
        s for s in sessions
        if str(s.get('stock_name', '')).strip().upper() not in ('DEMO', 'TEST', 'SAMPLE')
    ]

    config = {
        'orb': True,
        'ema': True,
        'vwap': True,
        'volume': True,
        'futures': False,
        'f5mc': True,
        'cvd': True,
    }

    if not sessions:
        print("  No real sessions found.")
        return

    for s in sessions:
        sid = s['id']
        cash = db.get_candles(sid, 'cash')
        if not cash:
            cash = db.get_candles(sid, 'cash_1')

        if not cash:
            print(f"  Session #{sid} ({s['stock_name']}): No data")
            continue

        futures = db.get_candles(sid, 'futures') or db.get_candles(sid, 'futures_1')
        index_d = db.get_candles(sid, 'index_1')

        sigs = generate_signals_v2(
            cash,
            futures or None,
            config,
            s['capital'],
            s['risk'],
            index_d
        )

        # Hard final filter
        sigs = [
            sig for sig in sigs
            if sig.get('grade') == 'A' or (
                sig.get('grade') == 'B' and sig.get('score', 0) >= 75
            )
        ]

        db.clear_signals(sid)
        db.store_signals(sid, sigs)

        buys = sum(1 for sig in sigs if sig['type'] == 'BUY')
        sells = sum(1 for sig in sigs if sig['type'] == 'SELL')
        a_grade = sum(1 for sig in sigs if sig.get('grade') == 'A')
        b_grade = sum(1 for sig in sigs if sig.get('grade') == 'B')

        print(
            f"  Session #{sid} ({s['stock_name']}): "
            f"{len(sigs)} signals ({buys} BUY, {sells} SELL) "
            f"[A:{a_grade} B:{b_grade}]"
        )

    print("\n  ✓ Analysis complete. Open http://localhost:5000 to view.")

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Trade Signal Engine — Fyers Data Fetcher')
    parser.add_argument('--setup',    action='store_true', help='Set up Fyers API credentials')
    parser.add_argument('--download', action='store_true', help='Download data for watchlist')
    parser.add_argument('--symbol',   type=str, default='', help='Download specific symbol')
    parser.add_argument('--status',   action='store_true', help='Show download status')
    parser.add_argument('--watchlist', action='store_true', help='Show watchlist')
    parser.add_argument('--analyze',  action='store_true', help='Run V2 analysis on all sessions')

    args = parser.parse_args()

    if args.setup:
        cmd_setup()
    elif args.download:
        cmd_download(args.symbol if args.symbol else None)
    elif args.status:
        cmd_status()
    elif args.watchlist:
        cmd_watchlist()
    elif args.analyze:
        cmd_analyze_all()
    else:
        parser.print_help()
        print("\n  Quick start:")
        print("    python fetch_data.py --setup       # Configure API credentials")
        print("    python fetch_data.py --download    # Download all watchlist data")
        print("    python fetch_data.py --analyze     # Run V2 signal analysis")
        print("    python app.py                      # Start web UI")
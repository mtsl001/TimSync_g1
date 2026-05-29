"""
backtest_cli.py — run backtests from the terminal (no web UI needed).

Examples:
    # Backtest an existing session
    python backtest_cli.py --session 3

    # Download a symbol from Fyers, then backtest it
    python backtest_cli.py --symbol NSE:SBIN-EQ --from 2024-01-01 --to 2024-01-31

    # Grid-search params with an out-of-sample (train/test) split
    python backtest_cli.py --session 3 --optimize \
        --grid '{"vwap":[true,false],"cvd":[true,false]}'
"""
import argparse
import json
import sys

import database as db
from engine.backtester import backtest_session_replay, optimize_with_holdout

DEFAULT_STRATEGIES = {
    'orb': True, 'ema': True, 'vwap': True, 'volume': True, 'futures': False,
    'f5mc': True, 'cvd': True,
}


def _load_session_candles(session_id: int):
    cash = db.get_candles(session_id, 'cash') or db.get_candles(session_id, 'cash_1')
    futures = db.get_candles(session_id, 'futures') or db.get_candles(session_id, 'futures_1')
    index_d = db.get_candles(session_id, 'index_1')
    return cash, futures or None, index_d or None


def _print_summary(summary: dict):
    keys = [
        'total_trades', 'win_rate', 'total_pnl', 'return_pct', 'expectancy',
        'profit_factor', 'max_drawdown', 'max_consecutive_losses',
        'sharpe_annualized', 'trading_days', 'avg_trades_per_day',
    ]
    print("\n  ── Backtest Summary ──")
    for k in keys:
        if k in summary:
            print(f"  {k:<24} {summary[k]}")
    if summary.get('best_day'):
        print(f"  best_day                 {summary['best_day']}")
    if summary.get('worst_day'):
        print(f"  worst_day                {summary['worst_day']}")
    gb = summary.get('grade_breakdown') or {}
    if gb:
        print("  grade_breakdown:")
        for g, d in sorted(gb.items()):
            print(f"    {g}: {d}")


def main(argv=None):
    p = argparse.ArgumentParser(description="TimSync backtest CLI")
    p.add_argument('--session', type=int, help='Existing session id to backtest')
    p.add_argument('--symbol', help='Fyers symbol to download then backtest, e.g. NSE:SBIN-EQ')
    p.add_argument('--from', dest='from_date', default='', help='Start date YYYY-MM-DD (with --symbol)')
    p.add_argument('--to', dest='to_date', default='', help='End date YYYY-MM-DD (with --symbol)')
    p.add_argument('--capital', type=float, default=25000)
    p.add_argument('--risk', type=float, default=500)
    p.add_argument('--strategies', default='', help='JSON strategy toggles override')
    p.add_argument('--signal-config', default='', help='JSON signal_config override')
    p.add_argument('--optimize', action='store_true', help='Run train/test grid search')
    p.add_argument('--grid', default='', help='JSON param grid for --optimize')
    p.add_argument('--train-frac', type=float, default=0.7)
    p.add_argument('--json', action='store_true', help='Emit raw JSON instead of a table')
    args = p.parse_args(argv)

    strategies = dict(DEFAULT_STRATEGIES)
    if args.strategies:
        strategies.update(json.loads(args.strategies))
    sig_cfg = json.loads(args.signal_config) if args.signal_config else None

    # Resolve a session id (download first if a symbol was given).
    session_id = args.session
    if args.symbol:
        from fyers_client import FyersClient, load_config, download_and_store
        cfg = load_config()
        client = FyersClient(cfg.get('client_id', ''), cfg.get('access_token', ''))
        session_id = download_and_store(
            client, args.symbol, args.capital, args.risk,
            from_1m=args.from_date, to_date=args.to_date,
        )
        print(f"  Downloaded {args.symbol} → session {session_id}")

    if not session_id:
        p.error("provide --session <id> or --symbol <SYMBOL>")

    cash, futures, index_d = _load_session_candles(session_id)
    if not cash:
        print(f"  No candle data for session {session_id}", file=sys.stderr)
        return 1

    if args.optimize:
        grid = json.loads(args.grid) if args.grid else {
            'vwap': [True, False], 'volume': [True, False],
            'f5mc': [True, False], 'cvd': [True, False],
        }
        result = optimize_with_holdout(
            cash, futures, strategies, grid,
            args.capital, args.risk, index_d, train_frac=args.train_frac,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\n  ── Top configs (in-sample / train) ──")
            for r in result.get('train', [])[:5]:
                print(f"  pnl={r['total_pnl']:<10} wr={r['win_rate']:<6} "
                      f"pf={r['profit_factor']:<6} trades={r['total_trades']:<4} "
                      f"cfg={ {k: v for k, v in r['config'].items() if k in grid} }")
            if result.get('test'):
                print("\n  ── Out-of-sample (held-out test days) ──")
                _print_summary(result['test']['summary'])
            else:
                print("  (not enough trading days for an out-of-sample split)")
        return 0

    result = backtest_session_replay(
        cash, futures, strategies, args.capital, args.risk, index_d, sig_cfg=sig_cfg,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        align = result.get('alignment', {})
        if align.get('warnings'):
            print("  ⚠ alignment:", '; '.join(align['warnings']))
        _print_summary(result['summary'])
        print(f"\n  equity_curve points: {len(result['summary'].get('equity_curve', []))}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
"""Centralized, tunable signal/backtest configuration.

All the knobs that used to live as magic constants scattered across
signals_v2.py, filters.py and backtester.py are collected here. Defaults
preserve the previous behavior EXCEPT for the newly-added safety caps
(per-day signal cap, time-window floor, HTF hard filter), which are the
levers for "fewer, higher-quality signals".

Override precedence (low -> high):
    DEFAULT_SIGNAL_CONFIG  <  "signal_config" block in fyers_config.json  <  per-call overrides
"""
import json
import os

DEFAULT_SIGNAL_CONFIG: dict = {
    # ── confluence / scoring ──────────────────────────────
    "threshold": 3.5,            # min directional score to consider a signal
    "muddy_ratio": 1.5,          # directional/opposite score ratio required (was 1.35)
    "min_strategies": 2,         # distinct strategy buckets required
    "allow_c_grade": False,      # if True, C-grade signals are tradeable (more signals)
    "b_grade_min_score": 68,     # floor for B-grade signals
    # ── de-dup / cadence ──────────────────────────────────
    "dedup_window": 8,           # candles for directional de-dup
    "min_signal_gap": 25,        # min candles between same-direction signals
    "max_signals_per_day": 4,    # hard cap per symbol per day (NEW)
    "per_symbol_cooldown_min": 30,  # live-feed re-alert suppression window (NEW)
    # ── hard filters ──────────────────────────────────────
    "htf_hard_filter": True,     # require higher-timeframe alignment (NEW; was soft)
    "min_time_mult": 0.5,        # drop signals in weak windows e.g. lunch 0.3 (NEW)
    # ── backtest costs ────────────────────────────────────
    "slippage_bps": 3,           # per-side slippage in basis points
    "brokerage_flat": 40.0,      # flat charge per trade
    "variable_pct": 0.0005,      # variable charge as fraction of turnover
}

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fyers_config.json")


def load_signal_config(overrides: dict | None = None) -> dict:
    """Return a fully-populated signal config.

    Reads the optional "signal_config" block from fyers_config.json, layered
    over the defaults, then applies per-call overrides. Unknown keys are
    ignored so a stray field can never silently change behavior.
    """
    cfg = dict(DEFAULT_SIGNAL_CONFIG)
    try:
        with open(_CONFIG_FILE) as f:
            data = json.load(f)
        block = data.get("signal_config") or {}
        cfg.update({k: v for k, v in block.items() if k in DEFAULT_SIGNAL_CONFIG})
    except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
        pass
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if k in DEFAULT_SIGNAL_CONFIG})
    return cfg


def candle_day(candle: dict) -> str:
    """Trading-day key for a candle ('YYYY-MM-DD'), tolerant of CSV inputs."""
    return candle.get("date") or str(candle.get("datetime", ""))[:10]
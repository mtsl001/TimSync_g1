"""
engine/backtester.py — Walk-forward replay backtester
=====================================================
Strict retrospective replay:
- At candle i, the system sees only candles[:i+1]
- No future candle visibility for signal generation
- Trade simulation starts from candle i+1 onward
- Supports parameter sweeps for tuning

This is meant for realistic intraday replay, not full-data batch scoring.
"""

from copy import deepcopy
from itertools import product

from .signals_v2 import generate_signals_v2

from .config import load_signal_config
from .data_align import align_by_timestamp

def _same_day(dt1: str, dt2: str) -> bool:
    if not dt1 or not dt2:
        return True
    return str(dt1)[:10] == str(dt2)[:10]


def _infer_grade(sig: dict) -> str:
    if sig.get("grade"):
        return sig["grade"]
    if isinstance(sig.get("conviction"), dict):
        return sig["conviction"].get("grade", "?")
    return "?"



def _estimate_charges(entry: float, exit_price: float, qty: int,
                      brokerage_flat: float = 40.0, variable_pct: float = 0.0005) -> float:
    turnover = (abs(entry) + abs(exit_price)) * max(qty, 0)
    variable = turnover * variable_pct
    return round(brokerage_flat + variable, 2)



def _apply_slippage(price: float, bps: float, worse_up: bool) -> float:
    """Move a fill price against the trader by `bps` basis points.
    worse_up=True pushes the price higher (bad for a buy fill / good-side exit)."""
    adj = price * (bps / 10000.0)
    return price + adj if worse_up else price - adj


def _simulate_exit(candles: list[dict], sig: dict, conservative: bool = True,
                   slippage_bps: float = 0.0, brokerage_flat: float = 40.0,
                   variable_pct: float = 0.0005) -> dict:
    """
    Simulate trade only using candles AFTER entry signal candle.
    Conservative mode assumes SL gets priority if both SL and target
    are touched in the same candle.
    """
    entry_idx = sig["candle_index"]
    entry = sig["entry"]
    sl = sig["sl"]
    t1 = sig["t1"]
    t2 = sig["t2"]
    qty = int(sig["qty"])
    is_buy = sig["type"] == "BUY"

    exit_price = None
    exit_reason = None
    exit_idx = entry_idx
    hit_t1 = False
    partial_pnl = 0.0

    entry_day = str(sig.get("time", ""))[:10] if sig.get("time") else None

    for j in range(entry_idx + 1, len(candles)):
        c = candles[j]
        c_day = str(c.get("datetime", ""))[:10] if c.get("datetime") else entry_day

        # Force intraday square-off at day change
        if entry_day and c_day and c_day != entry_day:
            prev_close = candles[j - 1]["close"]
            exit_price = prev_close
            exit_reason = "DAY_END_EXIT"
            exit_idx = j - 1
            break

        high_ = c["high"]
        low_ = c["low"]

        if is_buy:
            sl_hit = low_ <= sl
            t1_hit = high_ >= t1
            t2_hit = high_ >= t2
        else:
            sl_hit = high_ >= sl
            t1_hit = low_ <= t1
            t2_hit = low_ <= t2

        if conservative:
            if sl_hit and not hit_t1:
                exit_price = sl
                exit_reason = "SL_HIT"
                exit_idx = j
                break

        if not hit_t1 and t1_hit:
            hit_t1 = True
            partial_pnl = ((t1 - entry) if is_buy else (entry - t1)) * qty * 0.5

        if hit_t1 and t2_hit:
            exit_price = t2
            exit_reason = "T2_HIT"
            exit_idx = j
            break

        if sl_hit and hit_t1:
            exit_price = entry
            exit_reason = "PARTIAL_BE"
            exit_idx = j
            break

        if (not conservative) and sl_hit and not hit_t1:
            exit_price = sl
            exit_reason = "SL_HIT"
            exit_idx = j
            break

    if exit_price is None:
        exit_price = candles[-1]["close"]
        exit_reason = "FINAL_BAR_EXIT"
        exit_idx = len(candles) - 1


    # Slippage: a buy fills a touch higher and exits a touch lower (and vice
    # versa for a short). Applied to realized fills, not the modeled SL/target.
    fill_entry = _apply_slippage(entry, slippage_bps, worse_up=is_buy)
    fill_exit = _apply_slippage(exit_price, slippage_bps, worse_up=not is_buy)

    if is_buy:
        raw_pnl = (fill_exit - fill_entry) * qty
    else:
        raw_pnl = (fill_entry - fill_exit) * qty

    if exit_reason == "PARTIAL_BE":
        raw_pnl = partial_pnl

    charges = _estimate_charges(fill_entry, fill_exit, qty, brokerage_flat, variable_pct)
    net_pnl = round(raw_pnl - charges, 2)

    outcome = "WIN" if net_pnl > 0 else "LOSS" if net_pnl < 0 else "BE"

    return {
        "signal_time": sig.get("time"),
        "type": sig["type"],
        "entry": round(entry, 2),
        "exit": round(exit_price, 2),
        "sl": round(sl, 2),
        "t1": round(t1, 2),
        "t2": round(t2, 2),
        "qty": qty,
        "raw_pnl": round(raw_pnl, 2),
        "charges": round(charges, 2),
        "slippage_bps": slippage_bps,
        "net_pnl": round(net_pnl, 2),
        "exit_reason": exit_reason,
        "outcome": outcome,
        "hold_candles": exit_idx - entry_idx,
        "score": sig.get("score", 0),
        "grade": _infer_grade(sig),
        "reasons": sig.get("reasons", []),
        "candle_index": entry_idx,
    }


def compute_summary(trades: list[dict], capital: float) -> dict:
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "expectancy": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "max_consecutive_losses": 0,
            "return_pct": 0,
            "sharpe_approx": 0,
            "sharpe_annualized": 0,
            "grade_breakdown": {},
            "exit_reasons": {},
            "per_day": {},
            "trading_days": 0,
            "avg_trades_per_day": 0,
            "best_day": None,
            "worst_day": None,
            "equity_curve": [],
        }

    wins = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]

    n = len(trades)
    n_wins = len(wins)
    n_losses = len(losses)

    total_pnl = sum(t["net_pnl"] for t in trades)
    avg_win = sum(t["net_pnl"] for t in wins) / n_wins if n_wins else 0
    avg_loss = sum(abs(t["net_pnl"]) for t in losses) / n_losses if n_losses else 0
    win_rate = round(n_wins / n * 100, 1) if n else 0
    expectancy = round(total_pnl / n, 2) if n else 0

    gross_profit = sum(t["net_pnl"] for t in wins) if wins else 0
    gross_loss = sum(abs(t["net_pnl"]) for t in losses) if losses else 1
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else 99

    running = 0
    peak = 0
    max_dd = 0
    for t in trades:
        running += t["net_pnl"]
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    max_consec = 0
    streak = 0
    for t in trades:
        if t["outcome"] == "LOSS":
            streak += 1
            max_consec = max(max_consec, streak)
        else:
            streak = 0

    pnls = [t["net_pnl"] for t in trades]
    mean_pnl = total_pnl / n if n else 0
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / n if n > 1 else 0
    std_pnl = variance ** 0.5
    sharpe = round(mean_pnl / std_pnl, 2) if std_pnl > 0 else 0

    grade_breakdown = {}
    for t in trades:
        g = t.get("grade", "?")
        grade_breakdown.setdefault(g, {"trades": 0, "wins": 0, "pnl": 0})
        grade_breakdown[g]["trades"] += 1
        if t["outcome"] == "WIN":
            grade_breakdown[g]["wins"] += 1
        grade_breakdown[g]["pnl"] += t["net_pnl"]

    for g, d in grade_breakdown.items():
        d["win_rate"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] else 0
        d["pnl"] = round(d["pnl"], 2)

    exit_reasons = {}
    for t in trades:
        r = t["exit_reason"]
        exit_reasons.setdefault(r, {"count": 0, "pnl": 0})
        exit_reasons[r]["count"] += 1
        exit_reasons[r]["pnl"] += t["net_pnl"]

    for r in exit_reasons.values():
        r["pnl"] = round(r["pnl"], 2)

    # ── Per-day stats + annualized Sharpe (on daily returns) ──
    per_day: dict = {}
    running_eq = 0.0
    equity_curve = []
    for t in trades:
        day = str(t.get("signal_time", ""))[:10] or "?"
        d = per_day.setdefault(day, {"trades": 0, "wins": 0, "pnl": 0.0})
        d["trades"] += 1
        if t["outcome"] == "WIN":
            d["wins"] += 1
        d["pnl"] += t["net_pnl"]
        running_eq += t["net_pnl"]
        equity_curve.append(round(running_eq, 2))
    for day, d in per_day.items():
        d["pnl"] = round(d["pnl"], 2)
        d["win_rate"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] else 0

    trading_days = len(per_day)
    daily_pnls = [d["pnl"] for d in per_day.values()]
    if capital and len(daily_pnls) > 1:
        daily_rets = [p / capital for p in daily_pnls]
        mean_r = sum(daily_rets) / len(daily_rets)
        var_r = sum((r - mean_r) ** 2 for r in daily_rets) / (len(daily_rets) - 1)
        std_r = var_r ** 0.5
        sharpe_annualized = round((mean_r / std_r) * (252 ** 0.5), 2) if std_r > 0 else 0
    else:
        sharpe_annualized = 0

    best_day = max(per_day.items(), key=lambda kv: kv[1]["pnl"], default=(None, None))
    worst_day = min(per_day.items(), key=lambda kv: kv[1]["pnl"], default=(None, None))


    return {
        "total_trades": n,
        "wins": n_wins,
        "losses": n_losses,
        "breakeven": n - n_wins - n_losses,
        "win_rate": win_rate,
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 2),
        "max_consecutive_losses": max_consec,
        "return_pct": round(total_pnl / capital * 100, 2) if capital else 0,
        "sharpe_approx": sharpe,
        "sharpe_annualized": sharpe_annualized,
        "grade_breakdown": grade_breakdown,
        "exit_reasons": exit_reasons,
        "per_day": per_day,
        "trading_days": trading_days,
        "avg_trades_per_day": round(n / trading_days, 2) if trading_days else 0,
        "best_day": {"date": best_day[0], **best_day[1]} if best_day[0] else None,
        "worst_day": {"date": worst_day[0], **worst_day[1]} if worst_day[0] else None,
        "equity_curve": equity_curve,
    }


def backtest_session_replay(
    cash_data: list[dict],
    futures_data: list[dict] | None,
    config: dict,
    capital: float = 25000,
    risk_per_trade: float = 500,
    index_data: list[dict] | None = None,
    min_warmup: int = 25,
    conservative: bool = True,
    one_position_at_a_time: bool = True,
    sig_cfg: dict | None = None,
) -> dict:
    """
    Strict replay:
    - At step i, generate signals only on data[:i+1]
    - If a new signal appears exactly at candle i, enter it
    - Simulate exit using future candles only after i
    """
    if not cash_data or len(cash_data) < min_warmup:
        return {"trades": [], "summary": compute_summary([], capital), "alignment": {}}

    scfg = load_signal_config(sig_cfg)
    slippage_bps = scfg["slippage_bps"]
    brokerage_flat = scfg["brokerage_flat"]
    variable_pct = scfg["variable_pct"]

    # Align auxiliary feeds to the cash timeline so positional pairing is safe.
    cash_data, futures_data, index_data, alignment = align_by_timestamp(
        cash_data, futures_data, index_data
    )

    trades = []
    last_exit_idx = -1
    seen_signatures = set()

    for i in range(min_warmup, len(cash_data)):
        if one_position_at_a_time and i <= last_exit_idx:
            continue

        cash_slice = cash_data[:i + 1]
        fut_slice = futures_data[:i + 1] if futures_data and len(futures_data) >= i + 1 else None
        idx_slice = index_data[:i + 1] if index_data and len(index_data) >= i + 1 else None

        signals = generate_signals_v2(
            cash_slice,
            fut_slice,
            deepcopy(config),
            capital,
            risk_per_trade,
            idx_slice,
            sig_cfg=sig_cfg,
        )

        if not signals:
            continue

        current_bar_signals = [s for s in signals if s.get("candle_index") == i]
        if not current_bar_signals:
            continue

        current_bar_signals.sort(key=lambda s: (s.get("score", 0), s.get("grade", "")), reverse=True)
        sig = current_bar_signals[0]

        signature = (sig.get("candle_index"), sig.get("type"), round(sig.get("entry", 0), 2))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        trade = _simulate_exit(
            cash_data, sig, conservative=conservative,
            slippage_bps=slippage_bps, brokerage_flat=brokerage_flat,
            variable_pct=variable_pct,
        )
        trades.append(trade)
        last_exit_idx = trade["candle_index"] + trade["hold_candles"]

    summary = compute_summary(trades, capital)
    return {"trades": trades, "summary": summary, "alignment": alignment}


def _merge_dict(base: dict, overrides: dict) -> dict:
    x = deepcopy(base)
    x.update(overrides)
    return x


def optimize_parameters(
    cash_data: list[dict],
    futures_data: list[dict] | None,
    base_config: dict,
    param_grid: dict,
    capital: float = 25000,
    risk_per_trade: float = 500,
    index_data: list[dict] | None = None,
    top_n: int = 10,
) -> list[dict]:
    """
    Grid search optimizer using strict replay backtest.
    param_grid example:
    {
        "orb": [True],
        "ema": [True],
        "vwap": [True, False],
        "volume": [True],
        "f5mc": [True, False],
        "cvd": [True, False],
    }
    """
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]

    results = []

    for combo in product(*values):
        overrides = dict(zip(keys, combo))
        cfg = _merge_dict(base_config, overrides)

        bt = backtest_session_replay(
            cash_data=cash_data,
            futures_data=futures_data,
            config=cfg,
            capital=capital,
            risk_per_trade=risk_per_trade,
            index_data=index_data,
        )

        summary = bt["summary"]
        results.append({
            "config": cfg,
            "total_trades": summary["total_trades"],
            "win_rate": summary["win_rate"],
            "total_pnl": summary["total_pnl"],
            "profit_factor": summary["profit_factor"],
            "expectancy": summary["expectancy"],
            "max_drawdown": summary["max_drawdown"],
            "return_pct": summary["return_pct"],
        })

    results.sort(
        key=lambda x: (
            x["total_pnl"],
            x["profit_factor"],
            x["expectancy"],
            -x["max_drawdown"],
        ),
        reverse=True,
    )

    return results[:top_n]


def split_by_date(candles: list[dict], train_frac: float = 0.7) -> tuple[list[dict], list[dict]]:
    """Chronologically split candles into (train, test) on whole trading days,
    so the out-of-sample test set never shares a day with training."""
    days = sorted({str(c.get("date") or str(c.get("datetime", ""))[:10]) for c in candles})
    if len(days) < 2:
        return candles, []
    cut = max(1, int(len(days) * train_frac))
    train_days = set(days[:cut])
    train = [c for c in candles if str(c.get("date") or str(c.get("datetime", ""))[:10]) in train_days]
    test = [c for c in candles if str(c.get("date") or str(c.get("datetime", ""))[:10]) not in train_days]
    return train, test


def optimize_with_holdout(
    cash_data: list[dict],
    futures_data: list[dict] | None,
    base_config: dict,
    param_grid: dict,
    capital: float = 25000,
    risk_per_trade: float = 500,
    index_data: list[dict] | None = None,
    top_n: int = 5,
    train_frac: float = 0.7,
) -> dict:
    """Grid-search on the training days, then validate the winning config on the
    held-out test days. Guards against overfitting to a single in-sample run."""
    cash_train, cash_test = split_by_date(cash_data, train_frac)
    if not cash_test:
        return {"error": "Not enough distinct trading days for a train/test split", "train": [], "test": None}

    def _slice(aux):
        if not aux:
            return None, None
        tr, te = split_by_date(aux, train_frac)
        return tr or None, te or None

    fut_tr, fut_te = _slice(futures_data)
    idx_tr, idx_te = _slice(index_data)

    ranked = optimize_parameters(
        cash_train, fut_tr, base_config, param_grid,
        capital, risk_per_trade, idx_tr, top_n=top_n,
    )
    out = {"train": ranked, "train_days": len(set(str(c.get("date") or str(c.get("datetime", ""))[:10]) for c in cash_train))}

    if ranked:
        best_cfg = ranked[0]["config"]
        oos = backtest_session_replay(
            cash_test, fut_te, best_cfg, capital, risk_per_trade, idx_te,
        )
        out["test"] = {
            "config": best_cfg,
            "summary": oos["summary"],
            "test_days": len(set(str(c.get("date") or str(c.get("datetime", ""))[:10]) for c in cash_test)),
        }
    else:
        out["test"] = None
    return out
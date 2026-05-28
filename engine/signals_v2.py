"""
engine/signals_v2.py — Enhanced Signal Engine V2
================================================
Improved version with:
1. Same-direction cooldown
2. Stronger confluence requirements
3. Better quality gating
4. Direction-aware deduplication
5. Fewer low-quality repeat signals
"""

from .strategies import calc_ema, calc_vwap, calc_atr, calc_orb
from .advanced import (
    get_higher_tf_trend,
    detect_patterns,
    find_support_resistance,
    price_near_sr_level,
    calc_volume_delta,
    analyze_opening_gap,
    calc_momentum_quality,
    calc_relative_strength,
)
from .filters import (
    get_time_multiplier,
    detect_market_regime,
    calc_conviction_score,
    calc_position_size,
)
from .strategies_advanced import (
    calc_f5mc,
    check_f5mc_entry,
    detect_cvd_divergence,
)

THRESHOLD = 3.5
DEDUP_WINDOW = 8
MIN_SIGNAL_GAP = 25            # min candles between same-direction signals
MIN_STRATEGIES_FOR_SIGNAL = 2  # require at least 2 strategy buckets
ALLOW_C_GRADE = False          # set True if you want more signals


def _safe_len_match(a, b) -> bool:
    return bool(a) and bool(b) and len(a) == len(b)


def _avg_volume(data: list[dict], upto: int, lookback: int = 60) -> float:
    start = max(0, upto - lookback + 1)
    subset = data[start:upto + 1]
    if not subset:
        return 1.0
    avg = sum(d.get("volume", 0) for d in subset) / len(subset)
    return max(avg, 1.0)


def _grade_tradeable(grade: str) -> bool:
    if ALLOW_C_GRADE:
        return grade in ("A", "B", "C")
    return grade in ("A", "B")


def _has_recent_signal(signals: list[dict], candle_index: int, signal_type: str, gap: int = MIN_SIGNAL_GAP) -> bool:
    for s in reversed(signals):
        if s["type"] != signal_type:
            continue
        if candle_index - s["candle_index"] < gap:
            return True
        break
    return False


def _dedup_signals_directional(raw: list[dict], window: int = DEDUP_WINDOW) -> list[dict]:
    """
    Deduplicate separately by direction.
    Keep the highest-score signal inside each local cluster.
    """
    raw_sorted = sorted(raw, key=lambda x: (-x["score"], x["candle_index"]))
    used = set()
    final = []

    for s in raw_sorted:
        idx = s["candle_index"]
        side = s["type"]

        conflict = False
        for other_idx, other_side in used:
            if other_side == side and abs(other_idx - idx) <= window:
                conflict = True
                break

        if conflict:
            continue

        final.append(s)
        used.add((idx, side))

    final.sort(key=lambda x: x["candle_index"])
    return final


def generate_signals_v2(
    cash_data: list[dict],
    futures_data: list[dict] | None,
    config: dict,
    capital: float = 25000,
    risk_per_trade: float = 500,
    index_data: list[dict] | None = None,
) -> list[dict]:
    """
    Generate enhanced signals with stronger anti-noise filters.
    """
    if not cash_data or len(cash_data) < 25:
        return []

    ema9 = calc_ema(cash_data, 9)
    ema21 = calc_ema(cash_data, 21)
    ema50 = calc_ema(cash_data, 50)
    vwap = calc_vwap(cash_data)
    atr = calc_atr(cash_data, 14)
    orb = calc_orb(cash_data, 15) if config.get("orb", True) else None
    gap = analyze_opening_gap(cash_data)

    fut_prem = None
    if _safe_len_match(futures_data, cash_data):
        fut_prem = [
            round(futures_data[i].get("close", 0) - cash_data[i]["close"], 2)
            for i in range(len(cash_data))
        ]

    raw: list[dict] = []
    accepted: list[dict] = []

    f5mc = calc_f5mc(cash_data, index_data)

    for i in range(20, len(cash_data)):
        c = cash_data[i]
        prev = cash_data[i - 1]

        time_mult, time_label = get_time_multiplier(c.get("datetime", ""))
        if time_mult <= 0.0:
            continue

        avg_vol = _avg_volume(cash_data, i, 60)

        bull_score = 0.0
        bear_score = 0.0
        reasons: list[str] = []
        strategies_hit: list[str] = []

        # ── ORB ─────────────────────────────────────────────
        if config.get("orb", True) and orb:
            if i == orb["end_index"] + 1:
                vol_ok = c.get("volume", 0) > avg_vol * 1.3
                if c["close"] > orb["high"] and vol_ok:
                    bull_score += 3.5
                    reasons.append("ORB Breakout ▲")
                    strategies_hit.append("orb")
                elif c["close"] < orb["low"] and vol_ok:
                    bear_score += 3.5
                    reasons.append("ORB Breakdown ▼")
                    strategies_hit.append("orb")

            if i > orb["end_index"] + 3:
                if prev["close"] < orb["high"] and c["close"] > orb["high"]:
                    bull_score += 1.5
                    reasons.append("ORB High Reclaim")
                    strategies_hit.append("orb")
                if prev["close"] > orb["low"] and c["close"] < orb["low"]:
                    bear_score += 1.5
                    reasons.append("ORB Low Lost")
                    strategies_hit.append("orb")

        # ── EMA ─────────────────────────────────────────────
        if config.get("ema", True):
            if ema9[i - 1] <= ema21[i - 1] and ema9[i] > ema21[i]:
                bull_score += 2.5
                reasons.append("EMA 9×21 Golden Cross")
                strategies_hit.append("ema")
            elif ema9[i - 1] >= ema21[i - 1] and ema9[i] < ema21[i]:
                bear_score += 2.5
                reasons.append("EMA 9×21 Death Cross")
                strategies_hit.append("ema")

            in_uptrend = ema9[i] > ema50[i]
            in_downtrend = ema9[i] < ema50[i]

            if in_uptrend and c["low"] <= ema21[i] <= c["close"] and prev["close"] > ema21[i - 1]:
                bull_score += 1.0
                reasons.append("EMA21 Bounce")
                strategies_hit.append("ema")

            if in_downtrend and c["high"] >= ema21[i] >= c["close"] and prev["close"] < ema21[i - 1]:
                bear_score += 1.0
                reasons.append("EMA21 Reject")
                strategies_hit.append("ema")

            if prev["close"] <= ema50[i - 1] and c["close"] > ema50[i]:
                bull_score += 1.0
                reasons.append("EMA50 Break ↑")
                strategies_hit.append("ema")
            elif prev["close"] >= ema50[i - 1] and c["close"] < ema50[i]:
                bear_score += 1.0
                reasons.append("EMA50 Break ↓")
                strategies_hit.append("ema")

        # ── VWAP ────────────────────────────────────────────
        if config.get("vwap", True):
            if prev["close"] < vwap[i - 1] and c["close"] > vwap[i]:
                bull_score += 2.0
                reasons.append("VWAP Reclaim ↑")
                strategies_hit.append("vwap")
            elif prev["close"] > vwap[i - 1] and c["close"] < vwap[i]:
                bear_score += 2.0
                reasons.append("VWAP Break ↓")
                strategies_hit.append("vwap")

            vwap_dist_pct = abs(c["close"] - vwap[i]) / vwap[i] * 100 if vwap[i] else 0
            if vwap_dist_pct < 0.05:
                if ema9[i] > ema21[i]:
                    bull_score += 0.5
                    reasons.append("VWAP Test Bull Bias")
                    strategies_hit.append("vwap")
                elif ema9[i] < ema21[i]:
                    bear_score += 0.5
                    reasons.append("VWAP Test Bear Bias")
                    strategies_hit.append("vwap")

        # ── Volume ──────────────────────────────────────────
        if config.get("volume", True) and avg_vol > 0:
            vol_r = c.get("volume", 0) / avg_vol
            if vol_r > 2.0:
                if c["close"] > c["open"]:
                    bull_score += 1.5
                    reasons.append(f"Vol {vol_r:.1f}x Bullish")
                    strategies_hit.append("volume")
                else:
                    bear_score += 1.5
                    reasons.append(f"Vol {vol_r:.1f}x Bearish")
                    strategies_hit.append("volume")
            elif vol_r > 1.5:
                if c["close"] > c["open"]:
                    bull_score += 0.5
                    reasons.append(f"Vol {vol_r:.1f}x Mild Bull")
                    strategies_hit.append("volume")
                else:
                    bear_score += 0.5
                    reasons.append(f"Vol {vol_r:.1f}x Mild Bear")
                    strategies_hit.append("volume")

        # ── Futures bias ────────────────────────────────────
        if config.get("futures", False) and fut_prem:
            p = fut_prem[i]
            if p > 5:
                bull_score += 1.0
                reasons.append(f"Futures +{p:.1f}")
                strategies_hit.append("futures")
            elif p < -2:
                bear_score += 1.0
                reasons.append(f"Futures {p:.1f}")
                strategies_hit.append("futures")

        # ── F5MC ────────────────────────────────────────────
        if config.get("f5mc", True) and f5mc and f5mc.get("valid") and 5 <= i <= 40:
            f5_signal = check_f5mc_entry(cash_data[i], f5mc, cash_data[:i])
            if f5_signal:
                boost = f5_signal.get("score_boost", 0) / 10
                if f5_signal["direction"] == "BULL":
                    bull_score += 3.0 + boost
                    reasons.append(f5_signal["reason"])
                    strategies_hit.append("f5mc")
                else:
                    bear_score += 3.0 + boost
                    reasons.append(f5_signal["reason"])
                    strategies_hit.append("f5mc")

        # ── CVD divergence ─────────────────────────────────
        if config.get("cvd", True) and i >= 20:
            cvd_sig = detect_cvd_divergence(cash_data, i, lookback=20)
            if cvd_sig:
                boost = cvd_sig.get("score_boost", 10) / 10
                if cvd_sig["direction"] == "BULL":
                    bull_score += 2.0 + boost
                    reasons.append(cvd_sig["reason"])
                    strategies_hit.append("cvd")
                else:
                    bear_score += 2.0 + boost
                    reasons.append(cvd_sig["reason"])
                    strategies_hit.append("cvd")

        if not reasons:
            continue

        if bull_score < THRESHOLD and bear_score < THRESHOLD:
            continue

        is_bull = bull_score >= bear_score
        side = "BUY" if is_bull else "SELL"
        directional_score = max(bull_score, bear_score)
        opposite_score = min(bull_score, bear_score)

        # Reject muddy candles where both sides are close
        if opposite_score > 0 and directional_score / max(opposite_score, 0.1) < 1.35:
            continue

        # Require at least 2 strategy buckets for a valid signal
        unique_strategies = sorted(set(strategies_hit))
        if len(unique_strategies) < MIN_STRATEGIES_FOR_SIGNAL:
            continue

        entry = c["close"]
        cur_atr = atr[i]

        # ── Advanced filters ───────────────────────────────
        htf_5m = get_higher_tf_trend(cash_data, i, 5)
        htf_15m = get_higher_tf_trend(cash_data, i, 15)

        htf_aligned = False
        if is_bull and htf_5m == "BULLISH":
            htf_aligned = True
            reasons.append(f"HTF 5m: {htf_5m}")
        elif (not is_bull) and htf_5m == "BEARISH":
            htf_aligned = True
            reasons.append(f"HTF 5m: {htf_5m}")
        elif htf_5m != "NEUTRAL":
            reasons.append(f"HTF 5m: {htf_5m} ⚠")

        if is_bull and htf_15m == "BULLISH":
            htf_aligned = True
        elif (not is_bull) and htf_15m == "BEARISH":
            htf_aligned = True

        patterns = detect_patterns(cash_data, i)
        pattern_confirmed = False
        for p in patterns:
            if (is_bull and p["bias"] == "BULLISH") or ((not is_bull) and p["bias"] == "BEARISH"):
                pattern_confirmed = True
                reasons.append(f"Pattern: {p['name']}")
                unique_strategies.append("pattern")
                break

        sr_data = find_support_resistance(cash_data, i, 60)
        near_level = price_near_sr_level(entry, sr_data, tolerance_pct=0.3)
        near_sr = False
        if near_level:
            if is_bull and near_level["type"] == "SUPPORT":
                near_sr = True
                reasons.append(f"Near Support {near_level['price']}")
                unique_strategies.append("sr")
            elif (not is_bull) and near_level["type"] == "RESISTANCE":
                near_sr = True
                reasons.append(f"Near Resistance {near_level['price']}")
                unique_strategies.append("sr")

        vol_delta = calc_volume_delta(cash_data, i, 20)
        volume_confirming = False
        if is_bull and vol_delta["ratio"] > 1.3:
            volume_confirming = True
        elif (not is_bull) and vol_delta["ratio"] < 0.7:
            volume_confirming = True

        momentum = calc_momentum_quality(cash_data, i, 10)
        regime = detect_market_regime(cash_data, i, 30)

        rs = 1.0
        if index_data and len(index_data) > i:
            rs = calc_relative_strength(cash_data, index_data, i, 30)
            if is_bull and rs > 1.2:
                reasons.append(f"RS strong {rs}x")
            elif (not is_bull) and rs < 0.8:
                reasons.append(f"RS weak {rs}x")

        base_score = min(100, round(((directional_score - THRESHOLD) / 4.5) * 100))
        conviction = calc_conviction_score(
            base_score=base_score,
            time_mult=time_mult,
            regime=regime["regime"],
            strategies_triggered=sorted(set(unique_strategies)),
            htf_aligned=htf_aligned,
            near_sr=near_sr,
            pattern_confirmed=pattern_confirmed,
            volume_confirming=volume_confirming,
            momentum_quality=momentum["score"],
        )

        if not _grade_tradeable(conviction["grade"]):
            continue

        # Stronger A/B quality gate
        if conviction["grade"] == "B" and conviction["score"] < 68:
            continue

        if conviction["grade"] == "A" and len(set(unique_strategies)) < 2:
            continue

        # Same-direction cooldown
        if _has_recent_signal(accepted, i, side, MIN_SIGNAL_GAP):
            continue

        # Entry / exits
        if is_bull:
            sl = entry - cur_atr * 1.5
            if orb:
                sl = min(sl, orb["low"] - cur_atr * 0.3)
        else:
            sl = entry + cur_atr * 1.5
            if orb:
                sl = max(sl, orb["high"] + cur_atr * 0.3)

        sl = round(sl, 2)
        sl_dist = abs(entry - sl)

        if sl_dist < 0.5:
            continue

        t1 = round(entry + sl_dist * 1.5 if is_bull else entry - sl_dist * 1.5, 2)
        t2 = round(entry + sl_dist * 2.5 if is_bull else entry - sl_dist * 2.5, 2)
        t3 = round(entry + sl_dist * 4.0 if is_bull else entry - sl_dist * 4.0, 2)

        pos = calc_position_size(capital, risk_per_trade, entry, sl, conviction["grade"])
        if pos["qty"] <= 0:
            continue

        signal = {
            "time": c.get("datetime", f"C{i}"),
            "type": side,
            "entry": round(entry, 2),
            "sl": sl,
            "t1": t1,
            "t2": t2,
            "t3": t3,
            "qty": pos["qty"],
            "cap_needed": pos["capital"],
            "risk_amt": pos["risk"],
            "pot_pnl": round(pos["qty"] * abs(t1 - entry), 2),
            "rr": round(abs(t1 - entry) / sl_dist, 1),
            "score": conviction["score"],
            "grade": conviction["grade"],
            "conviction": conviction,
            "reasons": reasons,
            "candle_index": i,
            "vwap": vwap[i],
            "ema9": ema9[i],
            "ema21": ema21[i],
            "atr": round(cur_atr, 2),
            "htf_5m": htf_5m,
            "htf_15m": htf_15m,
            "regime": regime["regime"],
            "regime_conf": regime["confidence"],
            "momentum": momentum["score"],
            "vol_delta": vol_delta["delta"],
            "vol_ratio": vol_delta["ratio"],
            "time_window": time_label,
            "patterns": [p["name"] for p in patterns] if patterns else [],
            "sr_level": near_level["price"] if near_level else None,
            "rs_vs_index": rs,
            "gap": gap,
            "size_pct": pos["size_pct"],
            "strategy_count": len(set(unique_strategies)),
            "base_directional_score": round(directional_score, 2),
        }

        raw.append(signal)
        accepted.append(signal)

    final = _dedup_signals_directional(raw, window=DEDUP_WINDOW)
    return final
"""
engine/filters.py — Signal Quality Filters
=============================================
These filters REJECT low-probability setups before they
become signals. Each filter adds genuine edge.
"""


# ═══════════════════════════════════════════════════════════
# 1. TIME-OF-DAY FILTER
# ═══════════════════════════════════════════════════════════
# Impact: HIGH — Certain times have dramatically different
# win rates. Avoid lunch hour (1:00-2:30) and the last
# 15 minutes (fakeouts).

TIME_WINDOWS = {
    # (hour, minute) ranges → weight multiplier
    # First 15 min: NO trades (opening chaos)
    'opening_chaos':  {'start': (9, 15), 'end': (9, 30), 'multiplier': 0.0, 'label': 'Opening 15min – SKIP'},
    # ORB breakout window: BEST signals
    'orb_window':     {'start': (9, 30), 'end': (10, 15), 'multiplier': 1.3, 'label': 'ORB Window – PRIME'},
    # Morning momentum: great
    'morning_prime':  {'start': (10, 15), 'end': (11, 30), 'multiplier': 1.2, 'label': 'Morning Momentum'},
    # Pre-lunch: decent
    'pre_lunch':      {'start': (11, 30), 'end': (13, 0),  'multiplier': 1.0, 'label': 'Pre-Lunch'},
    # Lunch hour: AVOID (choppy, low volume, stop-hunts)
    'lunch_dead':     {'start': (13, 0),  'end': (14, 15), 'multiplier': 0.3, 'label': 'Lunch Hour – AVOID'},
    # Afternoon recovery: moderate
    'afternoon':      {'start': (14, 15), 'end': (15, 0),  'multiplier': 1.0, 'label': 'Afternoon'},
    # Power close: good for continuation, risky for reversals
    'power_close':    {'start': (15, 0),  'end': (15, 15), 'multiplier': 0.7, 'label': 'Power Close'},
    # Last 15 min: NO new trades
    'closing':        {'start': (15, 15), 'end': (15, 30), 'multiplier': 0.0, 'label': 'Closing – SKIP'},
}


def get_time_multiplier(candle_time: str) -> tuple[float, str]:
    """
    Get score multiplier based on time of day.
    candle_time: 'HH:MM' format
    Returns (multiplier, label)
    """
    try:
        parts = candle_time.strip().split(':')
        h, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 1.0, 'Unknown'

    current = h * 60 + m
    for window in TIME_WINDOWS.values():
        sh, sm = window['start']
        eh, em = window['end']
        start_min = sh * 60 + sm
        end_min   = eh * 60 + em
        if start_min <= current < end_min:
            return window['multiplier'], window['label']

    return 1.0, 'Outside hours'


# ═══════════════════════════════════════════════════════════
# 2. MARKET REGIME DETECTION
# ═══════════════════════════════════════════════════════════
# Impact: HIGH — Different strategies work in different
# regimes. ORB works in trending, mean-reversion in ranging.

def detect_market_regime(candles: list[dict], up_to_index: int, lookback: int = 30) -> dict:
    """
    Classify market regime using ATR ratio and directional movement.

    Returns: { regime, confidence, adr }
    regime: 'TRENDING', 'RANGING', 'VOLATILE', 'QUIET'
    """
    start = max(0, up_to_index - lookback)
    subset = candles[start:up_to_index + 1]
    if len(subset) < 10:
        return {'regime': 'NEUTRAL', 'confidence': 0, 'adr': 0}

    # Average candle range
    ranges = [c['high'] - c['low'] for c in subset]
    avg_range = sum(ranges) / len(ranges)

    # Directional movement (how far price moved vs total range covered)
    total_range = sum(ranges)
    net_move = abs(subset[-1]['close'] - subset[0]['open'])
    efficiency = net_move / total_range if total_range > 0 else 0

    # Recent volatility vs early volatility
    first_half = ranges[:len(ranges)//2]
    second_half = ranges[len(ranges)//2:]
    vol_change = (sum(second_half)/len(second_half)) / (sum(first_half)/len(first_half)) if sum(first_half) > 0 else 1

    # Classify
    if efficiency > 0.35 and avg_range > 0:
        regime = 'TRENDING'
        confidence = min(100, round(efficiency * 200))
    elif efficiency < 0.15 and vol_change < 0.8:
        regime = 'QUIET'
        confidence = min(100, round((1 - efficiency) * 100))
    elif vol_change > 1.5:
        regime = 'VOLATILE'
        confidence = min(100, round(vol_change * 50))
    else:
        regime = 'RANGING'
        confidence = min(100, round((1 - efficiency) * 80))

    return {
        'regime':     regime,
        'confidence': confidence,
        'efficiency': round(efficiency, 3),
        'vol_change': round(vol_change, 2),
        'adr':        round(avg_range, 2),
    }


def regime_strategy_compatibility(regime: str, strategy: str) -> float:
    """
    Returns a compatibility score (0.0 - 1.5) for a strategy in a regime.
    """
    matrix = {
        #                  ORB    EMA    VWAP   VOLUME  FUTURES  PATTERN  SR
        'TRENDING':  {'orb': 1.5, 'ema': 1.3, 'vwap': 1.0, 'volume': 1.2, 'futures': 1.1, 'pattern': 1.0, 'sr': 0.8},
        'RANGING':   {'orb': 0.5, 'ema': 0.7, 'vwap': 1.4, 'volume': 0.8, 'futures': 0.9, 'pattern': 1.3, 'sr': 1.5},
        'VOLATILE':  {'orb': 1.2, 'ema': 0.6, 'vwap': 0.7, 'volume': 1.4, 'futures': 1.0, 'pattern': 0.8, 'sr': 1.0},
        'QUIET':     {'orb': 0.3, 'ema': 0.8, 'vwap': 1.2, 'volume': 0.5, 'futures': 0.8, 'pattern': 1.0, 'sr': 1.3},
        'NEUTRAL':   {'orb': 1.0, 'ema': 1.0, 'vwap': 1.0, 'volume': 1.0, 'futures': 1.0, 'pattern': 1.0, 'sr': 1.0},
    }
    return matrix.get(regime, matrix['NEUTRAL']).get(strategy, 1.0)


# ═══════════════════════════════════════════════════════════
# 3. CONVICTION SCORING (Composite Quality)
# ═══════════════════════════════════════════════════════════

def calc_conviction_score(
    base_score: float,
    time_mult: float,
    regime: str,
    strategies_triggered: list[str],
    htf_aligned: bool,
    near_sr: bool,
    pattern_confirmed: bool,
    volume_confirming: bool,
    momentum_quality: int,
) -> dict:
    """
    Calculate a comprehensive conviction score incorporating
    all filters. This is the FINAL quality gate.

    Returns: { score (0-100), grade (A-F), tradeable (bool), factors }
    """
    score = base_score

    # ── Time filter ──
    score *= time_mult

    # ── Higher timeframe alignment ── (+15 to -10)
    if htf_aligned:
        score += 15
    else:
        score -= 10

    # ── S/R confluence ── (+10)
    if near_sr:
        score += 10

    # ── Pattern confirmation ── (+8)
    if pattern_confirmed:
        score += 8

    # ── Volume confirmation ── (+5)
    if volume_confirming:
        score += 5

    # ── Regime compatibility ──
    avg_compat = 1.0
    if strategies_triggered:
        avg_compat = sum(
            regime_strategy_compatibility(regime, s) for s in strategies_triggered
        ) / len(strategies_triggered)
    score *= avg_compat

    # ── Momentum quality ── (+/- up to 10)
    score += (momentum_quality - 50) * 0.2

    # ── Multi-strategy confluence bonus ──
    n = len(strategies_triggered)
    if n >= 3:
        score += 10
    elif n >= 2:
        score += 5

    score = max(0, min(100, round(score)))

    # Grade
    if score >= 80:   grade = 'A'
    elif score >= 65:  grade = 'B'
    elif score >= 50:  grade = 'C'
    elif score >= 35:  grade = 'D'
    else:              grade = 'F'

    tradeable = grade in ('A', 'B', 'C')

    factors = []
    if htf_aligned:        factors.append('✓ HTF aligned')
    else:                  factors.append('✗ HTF misaligned')
    if near_sr:            factors.append('✓ Near S/R level')
    if pattern_confirmed:  factors.append(f'✓ Candle pattern')
    if volume_confirming:  factors.append('✓ Volume confirmed')
    if avg_compat > 1.1:   factors.append(f'✓ Regime fit ({regime})')
    elif avg_compat < 0.8: factors.append(f'✗ Regime mismatch ({regime})')
    if time_mult >= 1.2:   factors.append('✓ Prime time window')
    elif time_mult < 0.5:  factors.append('✗ Bad time window')
    if n >= 3:             factors.append(f'✓ {n}-strategy confluence')

    return {
        'score':     score,
        'grade':     grade,
        'tradeable': tradeable,
        'factors':   factors,
    }


# ═══════════════════════════════════════════════════════════
# 4. TRADE MANAGEMENT RULES
# ═══════════════════════════════════════════════════════════

def calc_position_size(capital: float, risk_per_trade: float,
                       entry: float, sl: float, conviction_grade: str) -> dict:
    """
    Dynamic position sizing based on conviction.
    A-grade gets full size, lower grades get reduced.
    """
    sl_dist = abs(entry - sl)
    if sl_dist < 0.5:
        return {'qty': 0, 'capital': 0, 'risk': 0, 'size_pct': 0}

    # Grade-based sizing
    size_mult = {'A': 1.0, 'B': 0.75, 'C': 0.5, 'D': 0.25, 'F': 0.0}
    mult = size_mult.get(conviction_grade, 0.5)

    effective_risk = risk_per_trade * mult
    qty = max(0, int(effective_risk / sl_dist))
    cap_needed = qty * entry
    actual_risk = qty * sl_dist

    # Cap check
    if cap_needed > capital:
        qty = int(capital / entry)
        cap_needed = qty * entry
        actual_risk = qty * sl_dist

    return {
        'qty':      qty,
        'capital':  round(cap_needed, 2),
        'risk':     round(actual_risk, 2),
        'size_pct': round(cap_needed / capital * 100, 1) if capital > 0 else 0,
        'grade_mult': mult,
    }


def calc_trailing_sl(entry: float, current_price: float, initial_sl: float,
                     atr: float, signal_type: str = 'BUY') -> float:
    """
    Calculate a trailing stop-loss that:
    1. Starts at initial SL
    2. Moves to breakeven once 1R profit is hit
    3. Trails at 1.5 ATR behind price after 2R
    """
    sl_dist = abs(entry - initial_sl)
    profit = (current_price - entry) if signal_type == 'BUY' else (entry - current_price)

    # Not yet profitable → keep initial SL
    if profit <= 0:
        return initial_sl

    r_multiple = profit / sl_dist if sl_dist > 0 else 0

    if r_multiple >= 2.0:
        # Trail at 1.5 ATR
        if signal_type == 'BUY':
            return round(max(entry, current_price - atr * 1.5), 2)
        else:
            return round(min(entry, current_price + atr * 1.5), 2)
    elif r_multiple >= 1.0:
        # Move to breakeven
        return entry

    return initial_sl

"""
engine/advanced.py — Advanced Technical Analysis
==================================================
Multi-timeframe resampling, candlestick patterns,
support/resistance detection, volume profile, and
gap analysis.
"""

import math
from typing import Optional


# ═══════════════════════════════════════════════════════════
# 1. MULTI-TIMEFRAME RESAMPLING
# ═══════════════════════════════════════════════════════════
# Impact: HIGH — Only taking 1-min signals aligned with
# 5-min/15-min trend boosts win rate by ~10-15%.

def resample_candles(candles_1m: list[dict], minutes: int = 5) -> list[dict]:
    """Resample 1-minute candles to N-minute candles."""
    if not candles_1m:
        return []
    resampled = []
    bucket = []
    for i, c in enumerate(candles_1m):
        bucket.append(c)
        if len(bucket) >= minutes:
            resampled.append({
                'datetime': bucket[0].get('datetime', ''),
                'open':     bucket[0]['open'],
                'high':     max(b['high'] for b in bucket),
                'low':      min(b['low']  for b in bucket),
                'close':    bucket[-1]['close'],
                'volume':   sum(b.get('volume', 0) for b in bucket),
            })
            bucket = []
    # Remaining partial bucket
    if bucket:
        resampled.append({
            'datetime': bucket[0].get('datetime', ''),
            'open':     bucket[0]['open'],
            'high':     max(b['high'] for b in bucket),
            'low':      min(b['low']  for b in bucket),
            'close':    bucket[-1]['close'],
            'volume':   sum(b.get('volume', 0) for b in bucket),
        })
    return resampled


def get_higher_tf_trend(candles_1m: list[dict], up_to_index: int, tf_minutes: int = 5) -> str:
    """
    Get trend direction on a higher timeframe at a given 1-min index.
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    # Only use candles up to the given index (no look-ahead)
    subset = candles_1m[:up_to_index + 1]
    if len(subset) < tf_minutes * 3:
        return 'NEUTRAL'

    resampled = resample_candles(subset, tf_minutes)
    if len(resampled) < 3:
        return 'NEUTRAL'

    # Simple trend: last 3 higher-TF candles making higher lows/lower highs
    last3 = resampled[-3:]
    higher_lows  = last3[1]['low'] > last3[0]['low'] and last3[2]['low'] > last3[1]['low']
    lower_highs  = last3[1]['high'] < last3[0]['high'] and last3[2]['high'] < last3[1]['high']
    higher_close = last3[2]['close'] > last3[0]['close']

    # Also check EMA alignment on higher TF
    closes = [r['close'] for r in resampled]
    ema5  = _simple_ema(closes, 5)
    ema13 = _simple_ema(closes, 13)

    ema_bull = ema5 > ema13
    ema_bear = ema5 < ema13

    if (higher_lows or higher_close) and ema_bull:
        return 'BULLISH'
    elif (lower_highs or not higher_close) and ema_bear:
        return 'BEARISH'
    return 'NEUTRAL'


def _simple_ema(values: list[float], period: int) -> float:
    """Return the last EMA value for a series."""
    if not values:
        return 0
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


# ═══════════════════════════════════════════════════════════
# 2. CANDLESTICK PATTERN RECOGNITION
# ═══════════════════════════════════════════════════════════
# Impact: MEDIUM — Confirms entries at key levels.

def detect_patterns(candles: list[dict], index: int) -> list[dict]:
    """
    Detect candlestick patterns at the given index.
    Returns list of pattern dicts: { name, bias, strength }
    """
    if index < 2 or index >= len(candles):
        return []

    c    = candles[index]
    prev = candles[index - 1]
    pp   = candles[index - 2]
    patterns = []

    body      = abs(c['close'] - c['open'])
    range_    = c['high'] - c['low']
    is_green  = c['close'] > c['open']
    upper_wick = c['high'] - max(c['close'], c['open'])
    lower_wick = min(c['close'], c['open']) - c['low']

    prev_body = abs(prev['close'] - prev['open'])
    prev_green = prev['close'] > prev['open']

    # ── Bullish Engulfing ──
    if (is_green and not prev_green and
        c['open'] <= prev['close'] and c['close'] >= prev['open'] and
        body > prev_body * 1.1):
        patterns.append({'name': 'Bullish Engulfing', 'bias': 'BULLISH', 'strength': 2.0})

    # ── Bearish Engulfing ──
    if (not is_green and prev_green and
        c['open'] >= prev['close'] and c['close'] <= prev['open'] and
        body > prev_body * 1.1):
        patterns.append({'name': 'Bearish Engulfing', 'bias': 'BEARISH', 'strength': 2.0})

    # ── Hammer (bullish reversal) ──
    if (range_ > 0 and lower_wick >= body * 2 and
        upper_wick <= body * 0.3 and
        not prev_green):
        patterns.append({'name': 'Hammer', 'bias': 'BULLISH', 'strength': 1.5})

    # ── Shooting Star (bearish reversal) ──
    if (range_ > 0 and upper_wick >= body * 2 and
        lower_wick <= body * 0.3 and
        prev_green):
        patterns.append({'name': 'Shooting Star', 'bias': 'BEARISH', 'strength': 1.5})

    # ── Doji (indecision — needs context) ──
    if range_ > 0 and body / range_ < 0.1:
        patterns.append({'name': 'Doji', 'bias': 'NEUTRAL', 'strength': 0.5})

    # ── Morning Star (3-candle bullish reversal) ──
    pp_bear = pp['close'] < pp['open']
    pp_body = abs(pp['close'] - pp['open'])
    prev_small = prev_body < pp_body * 0.3
    if pp_bear and prev_small and is_green and c['close'] > (pp['open'] + pp['close']) / 2:
        patterns.append({'name': 'Morning Star', 'bias': 'BULLISH', 'strength': 2.5})

    # ── Evening Star (3-candle bearish reversal) ──
    pp_bull = pp['close'] > pp['open']
    if pp_bull and prev_small and not is_green and c['close'] < (pp['open'] + pp['close']) / 2:
        patterns.append({'name': 'Evening Star', 'bias': 'BEARISH', 'strength': 2.5})

    # ── Three White Soldiers ──
    if (index >= 3 and
        all(candles[index-j]['close'] > candles[index-j]['open'] for j in range(3)) and
        candles[index]['close'] > candles[index-1]['close'] > candles[index-2]['close']):
        patterns.append({'name': 'Three White Soldiers', 'bias': 'BULLISH', 'strength': 2.0})

    # ── Three Black Crows ──
    if (index >= 3 and
        all(candles[index-j]['close'] < candles[index-j]['open'] for j in range(3)) and
        candles[index]['close'] < candles[index-1]['close'] < candles[index-2]['close']):
        patterns.append({'name': 'Three Black Crows', 'bias': 'BEARISH', 'strength': 2.0})

    return patterns


# ═══════════════════════════════════════════════════════════
# 3. SUPPORT / RESISTANCE DETECTION
# ═══════════════════════════════════════════════════════════
# Impact: HIGH — Trading at confluence S/R zones gives
# much better entries than raw indicator signals.

def find_support_resistance(candles: list[dict], up_to_index: int, lookback: int = 60) -> dict:
    """
    Find key S/R levels from pivot points, round numbers,
    and price clustering. Returns { supports: [...], resistances: [...] }
    """
    start = max(0, up_to_index - lookback)
    subset = candles[start:up_to_index + 1]
    if len(subset) < 10:
        return {'supports': [], 'resistances': []}

    current_price = subset[-1]['close']
    levels = []

    # ── Method 1: Swing points ──
    for i in range(2, len(subset) - 2):
        # Swing high
        if (subset[i]['high'] >= subset[i-1]['high'] and
            subset[i]['high'] >= subset[i-2]['high'] and
            subset[i]['high'] >= subset[i+1]['high'] and
            subset[i]['high'] >= subset[i+2]['high']):
            levels.append(('swing_high', subset[i]['high']))

        # Swing low
        if (subset[i]['low'] <= subset[i-1]['low'] and
            subset[i]['low'] <= subset[i-2]['low'] and
            subset[i]['low'] <= subset[i+1]['low'] and
            subset[i]['low'] <= subset[i+2]['low']):
            levels.append(('swing_low', subset[i]['low']))

    # ── Method 2: Previous day High/Low (using first and last candle) ──
    day_high = max(c['high'] for c in subset)
    day_low  = min(c['low']  for c in subset)
    levels.append(('day_high', day_high))
    levels.append(('day_low',  day_low))

    # ── Method 3: Pivot Points (Classic) ──
    if len(subset) > 30:
        first_half = subset[:len(subset)//2]
        ph = max(c['high']  for c in first_half)
        pl = min(c['low']   for c in first_half)
        pc = first_half[-1]['close']
        pivot = (ph + pl + pc) / 3
        r1 = 2 * pivot - pl
        s1 = 2 * pivot - ph
        r2 = pivot + (ph - pl)
        s2 = pivot - (ph - pl)
        for tag, val in [('pivot', pivot), ('R1', r1), ('S1', s1), ('R2', r2), ('S2', s2)]:
            levels.append((tag, round(val, 2)))

    # ── Method 4: Round numbers ──
    base = int(current_price / 10) * 10
    for offset in [-20, -10, 0, 10, 20]:
        levels.append(('round', base + offset))
    base50 = int(current_price / 50) * 50
    for offset in [-50, 0, 50]:
        levels.append(('round50', base50 + offset))

    # ── Cluster nearby levels ──
    price_range = max(c['high'] for c in subset) - min(c['low'] for c in subset)
    tolerance = price_range * 0.005  # 0.5% of range

    all_prices = sorted(set(round(l[1], 2) for l in levels))
    clustered = []
    used = set()

    for p in all_prices:
        if p in used:
            continue
        cluster = [lp for lp in all_prices if abs(lp - p) <= tolerance and lp not in used]
        avg = sum(cluster) / len(cluster)
        strength = len(cluster)  # More methods agreeing = stronger level
        clustered.append({'price': round(avg, 2), 'strength': strength})
        for cp in cluster:
            used.add(cp)

    supports    = sorted([l for l in clustered if l['price'] < current_price],
                         key=lambda x: -x['price'])[:5]
    resistances = sorted([l for l in clustered if l['price'] > current_price],
                         key=lambda x: x['price'])[:5]

    return {'supports': supports, 'resistances': resistances}


def price_near_sr_level(price: float, sr_data: dict, tolerance_pct: float = 0.2) -> Optional[dict]:
    """
    Check if price is near a support or resistance level.
    Returns the nearest level dict or None.
    """
    tol = price * tolerance_pct / 100
    nearest = None
    min_dist = float('inf')

    for s in sr_data.get('supports', []):
        dist = abs(price - s['price'])
        if dist < tol and dist < min_dist:
            min_dist = dist
            nearest = {**s, 'type': 'SUPPORT'}

    for r in sr_data.get('resistances', []):
        dist = abs(price - r['price'])
        if dist < tol and dist < min_dist:
            min_dist = dist
            nearest = {**r, 'type': 'RESISTANCE'}

    return nearest


# ═══════════════════════════════════════════════════════════
# 4. VOLUME PROFILE / DELTA ANALYSIS
# ═══════════════════════════════════════════════════════════
# Impact: MEDIUM-HIGH — Volume delta approximation tells
# you if buyers or sellers are in control.

def calc_volume_delta(candles: list[dict], index: int, lookback: int = 20) -> dict:
    """
    Approximate volume delta from OHLC data.
    - Green candle: most volume attributed to buyers
    - Red candle: most volume attributed to sellers
    - Close position within range determines split ratio

    Returns: { delta, cum_delta, buy_vol, sell_vol, ratio }
    """
    start = max(0, index - lookback + 1)
    subset = candles[start:index + 1]

    cum_buy = 0
    cum_sell = 0

    for c in subset:
        vol = c.get('volume', 0)
        range_ = c['high'] - c['low']
        if range_ <= 0:
            buy_pct = 0.5
        else:
            # Close position within range — closer to high = more buying
            buy_pct = (c['close'] - c['low']) / range_
        buy_vol  = vol * buy_pct
        sell_vol = vol * (1 - buy_pct)
        cum_buy  += buy_vol
        cum_sell += sell_vol

    # Current candle only
    c = candles[index]
    vol = c.get('volume', 0)
    range_ = c['high'] - c['low']
    buy_pct = (c['close'] - c['low']) / range_ if range_ > 0 else 0.5
    candle_delta = vol * buy_pct - vol * (1 - buy_pct)

    total = cum_buy + cum_sell
    return {
        'delta':     round(candle_delta),
        'cum_delta': round(cum_buy - cum_sell),
        'buy_vol':   round(cum_buy),
        'sell_vol':  round(cum_sell),
        'ratio':     round(cum_buy / cum_sell, 2) if cum_sell > 0 else 99.0,
    }


# ═══════════════════════════════════════════════════════════
# 5. GAP ANALYSIS
# ═══════════════════════════════════════════════════════════
# Impact: MEDIUM — Opening gap type determines first-hour bias.

def analyze_opening_gap(candles: list[dict]) -> dict:
    """
    Analyze the opening gap (first candle vs previous close estimate).
    Since we only have intraday data, we compare open of first candle
    to the midpoint of first candle's range (or user can provide prev close).

    Returns: { gap_pct, gap_type, bias }
    gap_type: 'GAP_UP', 'GAP_DOWN', 'FLAT'
    """
    if len(candles) < 15:
        return {'gap_pct': 0, 'gap_type': 'FLAT', 'bias': 'NEUTRAL'}

    first = candles[0]
    # Check if first candle shows a gap pattern
    # Compare first candle open vs its own range
    range_ = first['high'] - first['low']

    # Better: use the first 5-min close vs the 15-min midpoint
    first_5  = candles[:5]
    first_15 = candles[:15]

    open_price = first['open']
    mid_15 = (max(c['high'] for c in first_15) + min(c['low'] for c in first_15)) / 2

    # If first 5 candles trend strongly in one direction, it's a gap drive
    first_5_chg = (first_5[-1]['close'] - first_5[0]['open']) / first_5[0]['open'] * 100
    first_5_vol = sum(c.get('volume', 0) for c in first_5)
    next_5_vol  = sum(c.get('volume', 0) for c in candles[5:10]) if len(candles) > 10 else first_5_vol

    if abs(first_5_chg) > 0.5 and first_5_vol > next_5_vol * 0.8:
        gap_type = 'GAP_UP' if first_5_chg > 0 else 'GAP_DOWN'
        bias = 'BULLISH' if first_5_chg > 0 else 'BEARISH'
    else:
        gap_type = 'FLAT'
        bias = 'NEUTRAL'

    return {
        'gap_pct':  round(first_5_chg, 2),
        'gap_type': gap_type,
        'bias':     bias,
    }


# ═══════════════════════════════════════════════════════════
# 6. RELATIVE STRENGTH (Stock vs Index)
# ═══════════════════════════════════════════════════════════

def calc_relative_strength(stock_candles: list[dict], index_candles: list[dict],
                           up_to_index: int, lookback: int = 30) -> float:
    """
    Calculate relative strength of stock vs index (e.g., Nifty).
    RS > 1 means stock is outperforming the index.
    """
    start = max(0, up_to_index - lookback)

    if (not stock_candles or not index_candles or
        len(stock_candles) <= up_to_index or len(index_candles) <= up_to_index or
        up_to_index < start + 5):
        return 1.0

    stock_chg = (stock_candles[up_to_index]['close'] - stock_candles[start]['close']) / stock_candles[start]['close']
    index_chg = (index_candles[up_to_index]['close'] - index_candles[start]['close']) / index_candles[start]['close']

    if index_chg == 0:
        return 1.0

    return round(stock_chg / index_chg, 2) if index_chg != 0 else 1.0


# ═══════════════════════════════════════════════════════════
# 7. MOMENTUM QUALITY SCORE
# ═══════════════════════════════════════════════════════════

def calc_momentum_quality(candles: list[dict], index: int, lookback: int = 10) -> dict:
    """
    Assess the quality of recent momentum.
    Clean trends (consistent direction, increasing volume) score higher
    than choppy moves.

    Returns: { score (0-100), direction, consecutive, vol_trend }
    """
    if index < lookback:
        return {'score': 50, 'direction': 'NEUTRAL', 'consecutive': 0, 'vol_trend': 'FLAT'}

    subset = candles[index - lookback:index + 1]

    # Count consecutive candles in same direction
    consecutive = 0
    direction = 'UP' if subset[-1]['close'] > subset[-1]['open'] else 'DOWN'
    for i in range(len(subset) - 1, -1, -1):
        is_up = subset[i]['close'] > subset[i]['open']
        if (direction == 'UP' and is_up) or (direction == 'DOWN' and not is_up):
            consecutive += 1
        else:
            break

    # Body-to-range ratio (clean candles have large bodies)
    body_ratios = []
    for c in subset:
        r = c['high'] - c['low']
        body_ratios.append(abs(c['close'] - c['open']) / r if r > 0 else 0)
    avg_body_ratio = sum(body_ratios) / len(body_ratios)

    # Volume trend
    first_half_vol = sum(c.get('volume', 0) for c in subset[:len(subset)//2])
    second_half_vol = sum(c.get('volume', 0) for c in subset[len(subset)//2:])
    vol_trend = 'INCREASING' if second_half_vol > first_half_vol * 1.2 else (
        'DECREASING' if second_half_vol < first_half_vol * 0.8 else 'FLAT'
    )

    # Overall score
    score = 50
    score += consecutive * 5                              # Up to +50 for 10 consecutive
    score += (avg_body_ratio - 0.5) * 40                   # Clean candles
    if vol_trend == 'INCREASING': score += 10
    if vol_trend == 'DECREASING': score -= 10
    score = max(0, min(100, round(score)))

    return {
        'score':       score,
        'direction':   direction,
        'consecutive': consecutive,
        'vol_trend':   vol_trend,
    }

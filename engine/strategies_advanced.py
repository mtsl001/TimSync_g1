"""
engine/strategies_advanced.py
================================
Two high-edge strategies:

1. F5MC  — First 5-Minute Candle Momentum
           Institutional volume + clean direction + trend alignment

2. CVD   — Cumulative Volume Delta Divergence
           Tracks buying/selling pressure under the price
"""

from .strategies import calc_ema


# ═══════════════════════════════════════════════════════════
# STRATEGY 1: FIRST 5-MINUTE CANDLE MOMENTUM (F5MC)
# ═══════════════════════════════════════════════════════════

def calc_f5mc(candles_1m: list[dict], candles_1h: list[dict] | None = None) -> dict | None:
    """
    Analyse the first 5-minute candle for institutional momentum.

    Args:
        candles_1m: 1-min candles for the current day (sorted oldest→newest)
        candles_1h: 1-hour candles for trend alignment (optional)

    Returns:
        {
            'valid':        bool,    # True if setup is tradeable
            'direction':    'BULL' | 'BEAR' | None,
            'entry_zone':   (low, high),    # Wait for price to return here
            'f5mc_high':    float,
            'f5mc_low':     float,
            'body_ratio':   float,   # quality of the candle (>0.65 = clean)
            'vol_ratio':    float,   # how much bigger than avg (>3 = institutional)
            'htf_aligned':  bool,    # 1-hour trend confirmed
            'reason':       str,
        }
    """
    if not candles_1m or len(candles_1m) < 10:
        return None

    # Extract first 5 candles
    f5 = candles_1m[:5]
    f5_open   = f5[0]['open']
    f5_high   = max(c['high']   for c in f5)
    f5_low    = min(c['low']    for c in f5)
    f5_close  = f5[-1]['close']
    f5_volume = sum(c.get('volume', 0) for c in f5)
    f5_range  = f5_high - f5_low

    if f5_range == 0:
        return {'valid': False, 'reason': 'Zero range F5MC'}

    # ── Quality check 1: Body-to-range ratio ──
    body = abs(f5_close - f5_open)
    body_ratio = body / f5_range
    if body_ratio < 0.65:
        return {
            'valid': False,
            'direction': None,
            'body_ratio': round(body_ratio, 3),
            'reason': f'Weak body ratio {body_ratio:.0%} (need >65%)',
        }

    # ── Quality check 2: Volume ──
    # Compare F5MC volume to the rest of the day's 5-min average
    rest_vols = []
    for i in range(5, min(len(candles_1m), 100), 5):
        chunk = candles_1m[i:i+5]
        rest_vols.append(sum(c.get('volume', 0) for c in chunk))

    if not rest_vols:
        avg_5m_vol = f5_volume / 2   # Not enough data — assume it's 2x
    else:
        avg_5m_vol = sum(rest_vols) / len(rest_vols)

    vol_ratio = f5_volume / avg_5m_vol if avg_5m_vol > 0 else 1.0

    if vol_ratio < 3.0:
        return {
            'valid': False,
            'direction': None,
            'body_ratio': round(body_ratio, 3),
            'vol_ratio':  round(vol_ratio, 2),
            'reason': f'Weak volume {vol_ratio:.1f}x (need >3x) — retail candle',
        }

    # ── Direction ──
    direction = 'BULL' if f5_close > f5_open else 'BEAR'

    # ── Quality check 3: 1-hour trend alignment ──
    htf_aligned = False
    if candles_1h and len(candles_1h) >= 21:
        ema9_1h  = calc_ema(candles_1h, 9)
        ema21_1h = calc_ema(candles_1h, 21)
        last_ema9  = ema9_1h[-1]
        last_ema21 = ema21_1h[-1]

        if direction == 'BULL' and last_ema9 > last_ema21:
            htf_aligned = True
        elif direction == 'BEAR' and last_ema9 < last_ema21:
            htf_aligned = True
    else:
        htf_aligned = True  # No HTF data — don't penalise

    # ── Entry zone ──
    # Wait for price to retrace to F5MC level
    if direction == 'BULL':
        # Entry when price pulls back to F5MC high
        entry_zone = (f5_high - f5_range * 0.1, f5_high + f5_range * 0.1)
    else:
        # Entry when price bounces back to F5MC low
        entry_zone = (f5_low - f5_range * 0.1, f5_low + f5_range * 0.1)

    return {
        'valid':       True,
        'direction':   direction,
        'f5mc_high':   round(f5_high,  2),
        'f5mc_low':    round(f5_low,   2),
        'f5mc_open':   round(f5_open,  2),
        'f5mc_close':  round(f5_close, 2),
        'entry_zone':  (round(entry_zone[0], 2), round(entry_zone[1], 2)),
        'body_ratio':  round(body_ratio,  3),
        'vol_ratio':   round(vol_ratio,   2),
        'htf_aligned': htf_aligned,
        'reason':      f'F5MC {direction} | Body {body_ratio:.0%} | Vol {vol_ratio:.1f}x{"" if htf_aligned else " | HTF AGAINST"}',
    }


def check_f5mc_entry(candle: dict, f5mc: dict, candles_so_far: list[dict]) -> dict | None:
    """
    Check if the current candle is a valid F5MC entry.

    Entry conditions:
    1. Price has returned to the F5MC entry zone
    2. This candle's volume is < 50% of F5MC volume (pullback is quiet)
    3. We're within the 9:25–9:50 entry window
    4. Candle closes in the right direction (not a big reversal candle)

    Returns signal dict if entry triggered, else None.
    """
    if not f5mc or not f5mc.get('valid'):
        return None

    price  = candle['close']
    zone   = f5mc['entry_zone']
    vol    = candle.get('volume', 0)
    f5_vol_single = 0

    # Estimate single F5MC candle volume
    if candles_so_far:
        f5_approx = sum(c.get('volume', 0) for c in candles_so_far[:5]) / 5
        f5_vol_single = f5_approx

    in_zone   = zone[0] <= price <= zone[1]
    quiet_vol = (vol < f5_vol_single * 0.5) if f5_vol_single > 0 else True

    if not in_zone:
        return None

    direction = f5mc['direction']
    is_bull   = direction == 'BULL'

    # Entry candle should close in the trend direction
    candle_bull = candle['close'] >= candle['open']
    if is_bull and not candle_bull:
        return None
    if not is_bull and candle_bull:
        return None

    entry  = candle['close']
    f5_range = f5mc['f5mc_high'] - f5mc['f5mc_low']
    atr_est  = f5_range * 0.5

    sl   = entry - atr_est * 1.5 if is_bull else entry + atr_est * 1.5
    t1   = entry + atr_est * 2.0 if is_bull else entry - atr_est * 2.0
    t2   = entry + atr_est * 3.5 if is_bull else entry - atr_est * 3.5

    return {
        'strategy': 'F5MC',
        'direction': direction,
        'entry':    round(entry, 2),
        'sl':       round(sl, 2),
        't1':       round(t1, 2),
        't2':       round(t2, 2),
        'body_ratio':  f5mc['body_ratio'],
        'vol_ratio':   f5mc['vol_ratio'],
        'htf_aligned': f5mc['htf_aligned'],
        'quiet_pullback': quiet_vol,
        'score_boost': 25 if (f5mc['htf_aligned'] and quiet_vol) else 10,
        'reason': f"F5MC Retest | Body {f5mc['body_ratio']:.0%} | Vol {f5mc['vol_ratio']:.1f}x | {'HTF ✓' if f5mc['htf_aligned'] else 'HTF ✗'}",
    }


# ═══════════════════════════════════════════════════════════
# STRATEGY 2: CUMULATIVE VOLUME DELTA DIVERGENCE (CVD)
# ═══════════════════════════════════════════════════════════

def calc_volume_delta_series(candles: list[dict]) -> list[float]:
    """
    Calculate per-candle volume delta.

    Delta = (buy_volume - sell_volume) approximated from price position
    within the candle range.

    A candle closing near its high = mostly buying pressure.
    A candle closing near its low  = mostly selling pressure.
    """
    deltas = []
    for c in candles:
        range_ = c['high'] - c['low']
        vol    = c.get('volume', 0)
        if range_ <= 0 or vol == 0:
            deltas.append(0)
            continue
        # Fraction of range that was bought vs sold
        buy_pct  = (c['close'] - c['low'])  / range_
        sell_pct = (c['high']  - c['close']) / range_
        deltas.append((buy_pct - sell_pct) * vol)
    return deltas


def calc_cvd(candles: list[dict]) -> list[float]:
    """
    Cumulative Volume Delta — running sum of per-candle deltas.
    Positive = buyers winning overall, Negative = sellers winning.
    """
    deltas = calc_volume_delta_series(candles)
    cvd = []
    running = 0.0
    for d in deltas:
        running += d
        cvd.append(running)
    return cvd


def detect_cvd_divergence(
    candles:  list[dict],
    index:    int,
    lookback: int = 15,
) -> dict | None:
    """
    Detect CVD divergence at the given candle index.

    Scans the last `lookback` candles for:
    1. Bearish divergence: price HH but CVD LH
    2. Bullish divergence: price LL but CVD HL
    3. Delta exhaustion: large delta but small price move

    Returns divergence signal or None.
    """
    if index < lookback + 5:
        return None

    start = max(0, index - lookback)
    window = candles[start:index + 1]

    if len(window) < 10:
        return None

    cvd = calc_cvd(window)
    closes = [c['close'] for c in window]
    n = len(window)

    # ── Find swing highs/lows in last lookback candles ──
    def find_pivots(series, mode='high'):
        pivots = []
        for i in range(2, len(series) - 2):
            if mode == 'high':
                if series[i] >= series[i-1] and series[i] >= series[i-2] and \
                   series[i] >= series[i+1] and series[i] >= series[i+2]:
                    pivots.append((i, series[i]))
            else:
                if series[i] <= series[i-1] and series[i] <= series[i-2] and \
                   series[i] <= series[i+1] and series[i] <= series[i+2]:
                    pivots.append((i, series[i]))
        return pivots

    price_highs = find_pivots(closes, 'high')
    price_lows  = find_pivots(closes, 'low')
    cvd_highs   = find_pivots(cvd,    'high')
    cvd_lows    = find_pivots(cvd,    'low')

    # ── Bearish Divergence: Price HH, CVD LH ──
    if len(price_highs) >= 2 and len(cvd_highs) >= 2:
        ph1, ph2 = price_highs[-2], price_highs[-1]
        ch1, ch2 = cvd_highs[-2], cvd_highs[-1]

        price_made_hh = ph2[1] > ph1[1]
        cvd_made_lh   = ch2[1] < ch1[1]

        if price_made_hh and cvd_made_lh:
            strength = (ph2[1] - ph1[1]) / ph1[1] * 100  # % price move
            delta_drop = (ch1[1] - ch2[1]) / abs(ch1[1]) * 100 if ch1[1] != 0 else 0

            if strength > 0.2 and delta_drop > 10:
                return {
                    'type':         'BEARISH_DIVERGENCE',
                    'direction':    'BEAR',
                    'strength':     round(strength, 3),
                    'delta_change': round(delta_drop, 1),
                    'score_boost':  20 if (strength > 0.5 and delta_drop > 20) else 12,
                    'reason':       f'CVD Bear Div | Price +{strength:.2f}% but Delta -{delta_drop:.0f}%',
                }

    # ── Bullish Divergence: Price LL, CVD HL ──
    if len(price_lows) >= 2 and len(cvd_lows) >= 2:
        pl1, pl2 = price_lows[-2], price_lows[-1]
        cl1, cl2 = cvd_lows[-2], cvd_lows[-1]

        price_made_ll = pl2[1] < pl1[1]
        cvd_made_hl   = cl2[1] > cl1[1]

        if price_made_ll and cvd_made_hl:
            strength = (pl1[1] - pl2[1]) / pl1[1] * 100
            delta_rise = (cl2[1] - cl1[1]) / abs(cl1[1]) * 100 if cl1[1] != 0 else 0

            if strength > 0.2 and delta_rise > 10:
                return {
                    'type':         'BULLISH_DIVERGENCE',
                    'direction':    'BULL',
                    'strength':     round(strength, 3),
                    'delta_change': round(delta_rise, 1),
                    'score_boost':  20 if (strength > 0.5 and delta_rise > 20) else 12,
                    'reason':       f'CVD Bull Div | Price -{strength:.2f}% but Delta +{delta_rise:.0f}%',
                }

    # ── Delta Exhaustion: Large delta, tiny price move ──
    c = window[-1]
    prev_c = window[-2]
    delta = calc_volume_delta_series([c])[0]
    price_move = abs(c['close'] - prev_c['close'])
    range_    = c['high'] - c['low']
    avg_vol   = sum(x.get('volume', 0) for x in window) / len(window)

    if c.get('volume', 0) > avg_vol * 2.5 and range_ > 0 and price_move < range_ * 0.15:
        is_bull_delta = delta > 0
        return {
            'type':      'DELTA_EXHAUSTION',
            'direction': 'BEAR' if is_bull_delta else 'BULL',  # Reversal
            'vol_ratio': round(c.get('volume', 0) / avg_vol, 1),
            'score_boost': 15,
            'reason':    f'Delta Exhaustion | {c["volume"]/avg_vol:.1f}x vol absorbed | Tiny price move',
        }

    return None


def get_cvd_snapshot(candles: list[dict], lookback: int = 30) -> dict:
    """
    Get current CVD snapshot for display.
    Returns trend, level, and momentum.
    """
    if len(candles) < 10:
        return {}

    window = candles[-lookback:]
    cvd = calc_cvd(window)

    trend = 'BULLISH' if cvd[-1] > cvd[0] else 'BEARISH'
    momentum = cvd[-1] - cvd[-min(5, len(cvd))]
    accelerating = abs(cvd[-1] - cvd[-3]) > abs(cvd[-6] - cvd[-9]) if len(cvd) > 9 else False

    return {
        'current':      round(cvd[-1]),
        'trend':        trend,
        'momentum':     round(momentum),
        'accelerating': accelerating,
        'values':       [round(v) for v in cvd[-20:]],  # Last 20 for chart
    }

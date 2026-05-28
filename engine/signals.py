"""
engine/signals.py — Multi-strategy signal generator
=====================================================
Strategies:
  1. ORB  — Opening Range Breakout/Breakdown (first 15 min)
  2. EMA  — 9/21/50 crossovers and bounces
  3. VWAP — Session VWAP reclaim/rejection
  4. VOL  — Abnormal volume surge detection
  5. FUT  — Futures premium/discount bias

Each strategy contributes a score. Signal is fired when combined
score >= THRESHOLD. Signals are deduplicated in a 5-candle window.
"""

from .strategies import calc_ema, calc_vwap, calc_atr, calc_orb


THRESHOLD = 2.5   # Minimum combined score to generate a signal
DEDUP_WINDOW = 5  # Candles to look around for deduplication


def _avg_volume(data: list[dict], lookback: int = 60) -> float:
    vols = [d.get('volume') or 0 for d in data[:lookback]]
    return sum(vols) / max(len(vols), 1)


def generate_signals(
    cash_data:    list[dict],
    futures_data: list[dict] | None,
    config:       dict,
    capital:      float = 25000,
    risk_per_trade: float = 500,
) -> list[dict]:

    if not cash_data or len(cash_data) < 25:
        return []

    ema9  = calc_ema(cash_data, 9)
    ema21 = calc_ema(cash_data, 21)
    ema50 = calc_ema(cash_data, 50)
    vwap  = calc_vwap(cash_data)
    atr   = calc_atr(cash_data, 14)
    orb   = calc_orb(cash_data, 15) if config.get('orb') else None
    avg_vol = _avg_volume(cash_data, 60)

    fut_prem = None
    if futures_data and len(futures_data) == len(cash_data):
        fut_prem = [
            round((futures_data[i].get('close', 0) - cash_data[i]['close']), 2)
            for i in range(len(cash_data))
        ]

    raw: list[dict] = []

    for i in range(20, len(cash_data)):
        c    = cash_data[i]
        prev = cash_data[i - 1]
        bs, bers = 0.0, 0.0
        reasons: list[str] = []

        # ── Strategy 1: ORB ────────────────────────────────────────────
        if config.get('orb') and orb:
            # First candle after ORB closes
            if i == orb['end_index'] + 1:
                if c['close'] > orb['high'] and c.get('volume', 0) > avg_vol * 1.3:
                    bs += 3.5
                    reasons.append('ORB Breakout ▲')
                elif c['close'] < orb['low'] and c.get('volume', 0) > avg_vol * 1.3:
                    bers += 3.5
                    reasons.append('ORB Breakdown ▼')

            # ORB high reclaim after pullback
            if i > orb['end_index'] + 3:
                if prev['close'] < orb['high'] and c['close'] > orb['high']:
                    bs += 1.5
                    reasons.append('ORB High Reclaim')
                # ORB low breakdown (continuation)
                if prev['close'] > orb['low'] and c['close'] < orb['low']:
                    bers += 1.5
                    reasons.append('ORB Low Lost')

        # ── Strategy 2: EMA Crossover ──────────────────────────────────
        if config.get('ema'):
            # Golden / Death Cross
            if ema9[i-1] <= ema21[i-1] and ema9[i] > ema21[i]:
                bs += 2.5
                reasons.append('EMA 9×21 Golden Cross')
            elif ema9[i-1] >= ema21[i-1] and ema9[i] < ema21[i]:
                bers += 2.5
                reasons.append('EMA 9×21 Death Cross')

            # Price bounces off EMA21 in uptrend
            in_uptrend = ema9[i] > ema50[i]
            if in_uptrend and c['low'] <= ema21[i] <= c['close'] and prev['close'] > ema21[i-1]:
                bs += 1.0
                reasons.append('EMA21 Bounce (Uptrend)')

            # Price crosses EMA50
            if prev['close'] <= ema50[i-1] and c['close'] > ema50[i]:
                bs += 1.0
                reasons.append('EMA50 Break Up')
            elif prev['close'] >= ema50[i-1] and c['close'] < ema50[i]:
                bers += 1.0
                reasons.append('EMA50 Break Down')

            # EMA9 slope confirmation
            if ema9[i] > ema9[i-1] and ema9[i-1] > ema9[i-2] if i > 1 else False:
                bs += 0.3

        # ── Strategy 3: VWAP ───────────────────────────────────────────
        if config.get('vwap'):
            # VWAP reclaim / breakdown
            if prev['close'] < vwap[i-1] and c['close'] > vwap[i]:
                bs += 2.0
                reasons.append('VWAP Reclaim ↑')
            elif prev['close'] > vwap[i-1] and c['close'] < vwap[i]:
                bers += 2.0
                reasons.append('VWAP Break ↓')

            # Price returning to test VWAP in trend direction
            vwap_dist_pct = abs(c['close'] - vwap[i]) / vwap[i] * 100 if vwap[i] else 0
            if vwap_dist_pct < 0.05 and i > 30:
                if ema9[i] > ema21[i]:
                    bs   += 0.5; reasons.append('VWAP Test (Bullish Bias)')
                else:
                    bers += 0.5; reasons.append('VWAP Test (Bearish Bias)')

        # ── Strategy 4: Volume Surge ───────────────────────────────────
        if config.get('volume') and avg_vol > 0:
            vol_ratio = c.get('volume', 0) / avg_vol
            if vol_ratio > 2.0:
                label = f'Vol Surge {vol_ratio:.1f}x'
                if c['close'] > c['open']:
                    bs   += 1.5; reasons.append(f'⚡ {label} Bullish')
                else:
                    bers += 1.5; reasons.append(f'⚡ {label} Bearish')
            elif vol_ratio > 1.5:
                if c['close'] > c['open']:
                    bs   += 0.5
                else:
                    bers += 0.5

        # ── Strategy 5: Futures Bias ───────────────────────────────────
        if config.get('futures') and fut_prem is not None:
            p = fut_prem[i]
            if p > 5:
                bs   += 1.0; reasons.append(f'Futures Premium +{p:.1f}')
            elif p < -2:
                bers += 1.0; reasons.append(f'Futures Discount {p:.1f}')

        # ── Evaluate ───────────────────────────────────────────────────
        if not reasons:
            continue
        if bs < THRESHOLD and bers < THRESHOLD:
            continue

        is_bull = bs >= bers
        entry   = c['close']
        cur_atr = atr[i]

        # Dynamic SL using ATR
        if is_bull:
            sl = entry - cur_atr * 1.5
            if orb:
                sl = min(sl, orb['low'] - cur_atr * 0.3)
        else:
            sl = entry + cur_atr * 1.5
            if orb:
                sl = max(sl, orb['high'] + cur_atr * 0.3)
        sl = round(sl, 2)

        sl_dist = abs(entry - sl)
        if sl_dist < 0.5:
            continue  # Too tight, skip noise

        # Targets at R multiples
        t1 = round(entry + sl_dist * 1.5 if is_bull else entry - sl_dist * 1.5, 2)
        t2 = round(entry + sl_dist * 2.5 if is_bull else entry - sl_dist * 2.5, 2)
        t3 = round(entry + sl_dist * 4.0 if is_bull else entry - sl_dist * 4.0, 2)

        qty = max(1, int(risk_per_trade / sl_dist))
        cap_needed = round(qty * entry, 2)

        if cap_needed > capital * 1.05:
            continue  # Not enough capital

        score = min(100, round(((max(bs, bers) - THRESHOLD) / 4.5) * 100))

        raw.append({
            'time':         c.get('datetime', f'C{i}'),
            'type':         'BUY' if is_bull else 'SELL',
            'entry':        round(entry, 2),
            'sl':           sl,
            't1':           t1,
            't2':           t2,
            't3':           t3,
            'qty':          qty,
            'cap_needed':   cap_needed,
            'risk_amt':     round(sl_dist * qty, 2),
            'pot_pnl':      round(qty * abs(t1 - entry), 2),
            'rr':           round(abs(t1 - entry) / sl_dist, 1),
            'score':        score,
            'reasons':      reasons,
            'candle_index': i,
            'vwap':         vwap[i],
            'ema9':         ema9[i],
            'ema21':        ema21[i],
            'atr':          round(cur_atr, 2),
        })

    # ── Deduplicate ────────────────────────────────────────────────────────────
    raw.sort(key=lambda x: -x['score'])
    used: set[int] = set()
    final: list[dict] = []

    for s in raw:
        idx = s['candle_index']
        window = range(idx - DEDUP_WINDOW, idx + DEDUP_WINDOW + 1)
        if any(w in used for w in window):
            continue
        final.append(s)
        for w in window:
            used.add(w)

    final.sort(key=lambda x: x['candle_index'])
    return final

"""
engine/strategies.py — Technical indicator calculations
"""


def calc_ema(data: list[dict], period: int) -> list[float]:
    """Exponential Moving Average on close prices."""
    if not data:
        return []
    k = 2 / (period + 1)
    ema = data[0]['close']
    result = [round(ema, 2)]
    for d in data[1:]:
        ema = d['close'] * k + ema * (1 - k)
        result.append(round(ema, 2))
    return result


def calc_sma(data: list[dict], period: int) -> list[float]:
    """Simple Moving Average."""
    closes = [d['close'] for d in data]
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(round(sum(closes[:i+1]) / (i+1), 2))
        else:
            result.append(round(sum(closes[i-period+1:i+1]) / period, 2))
    return result


def calc_vwap(data: list[dict]) -> list[float]:
    """Volume Weighted Average Price (resets each session)."""
    cum_tpv, cum_vol = 0.0, 0.0
    result = []
    for d in data:
        tp = (d['high'] + d['low'] + d['close']) / 3
        vol = d.get('volume') or 1
        cum_tpv += tp * vol
        cum_vol += vol
        result.append(round(cum_tpv / cum_vol, 2))
    return result


def calc_atr(data: list[dict], period: int = 14) -> list[float]:
    """Average True Range."""
    trs = []
    for i, d in enumerate(data):
        if i == 0:
            trs.append(d['high'] - d['low'])
        else:
            prev = data[i - 1]
            tr = max(
                d['high'] - d['low'],
                abs(d['high'] - prev['close']),
                abs(d['low'] - prev['close'])
            )
            trs.append(tr)

    atr = sum(trs[:period]) / max(period, 1)
    result = []
    for i, tr in enumerate(trs):
        if i < period:
            result.append(round(sum(trs[:i+1]) / (i+1), 2))
        else:
            atr = (atr * (period - 1) + tr) / period
            result.append(round(atr, 2))
    return result


def calc_rsi(data: list[dict], period: int = 14) -> list[float]:
    """Relative Strength Index."""
    closes = [d['close'] for d in data]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    result = [50.0]  # Default for first candle
    if len(gains) < period:
        return result * len(data)

    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period):
        result.append(50.0)

    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / avg_l if avg_l != 0 else 100
        result.append(round(100 - 100 / (1 + rs), 2))

    return result[:len(data)]


def calc_bollinger(data: list[dict], period: int = 20, std_dev: float = 2.0) -> dict:
    """Bollinger Bands."""
    closes = [d['close'] for d in data]
    upper, lower, mid = [], [], []
    for i in range(len(closes)):
        start = max(0, i - period + 1)
        window = closes[start:i + 1]
        sma = sum(window) / len(window)
        variance = sum((x - sma) ** 2 for x in window) / len(window)
        std = variance ** 0.5
        mid.append(round(sma, 2))
        upper.append(round(sma + std_dev * std, 2))
        lower.append(round(sma - std_dev * std, 2))
    return {'upper': upper, 'mid': mid, 'lower': lower}


def calc_orb(data: list[dict], minutes: int = 15) -> dict | None:
    """Opening Range (first N candles)."""
    if len(data) < minutes:
        return None
    orb_candles = data[:minutes]
    return {
        'high':      round(max(d['high'] for d in orb_candles), 2),
        'low':       round(min(d['low']  for d in orb_candles), 2),
        'end_index': minutes - 1,
    }


def compute_all(data: list[dict]) -> dict:
    """Compute all indicators for charting."""
    if not data or len(data) < 5:
        return {'ema9': [], 'ema21': [], 'ema50': [], 'vwap': [], 'atr': [], 'rsi': []}
    return {
        'ema9':  calc_ema(data, 9),
        'ema21': calc_ema(data, 21),
        'ema50': calc_ema(data, 50),
        'vwap':  calc_vwap(data),
        'atr':   calc_atr(data, 14),
        'rsi':   calc_rsi(data, 14),
    }

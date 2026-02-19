"""
技术指标（供回测或展示使用）
"""

from typing import List


def obv(closes: List[float], volumes: List[float]) -> List[float]:
    """能量潮 OBV：累计 volume * sign(close - prev_close)"""
    if len(closes) < 2 or len(volumes) < 2 or len(closes) != len(volumes):
        return []
    out = [0.0]
    for i in range(1, len(closes)):
        sign = 1.0 if closes[i] > closes[i - 1] else (-1.0 if closes[i] < closes[i - 1] else 0.0)
        out.append(out[-1] + sign * volumes[i])
    return out


def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """
    平均趋向指数 ADX（period 常用 14）
    返回与 closes 等长的序列，前 period*2 左右为 None 占位或 0，后续为 ADX 值。
    """
    n = len(closes)
    if n < period * 2 or len(highs) != n or len(lows) != n:
        return [0.0] * n

    def _smoothed(series: List[float], period: int) -> List[float]:
        out = [None] * n
        out[period - 1] = sum(series[:period])
        for i in range(period, n):
            out[i] = out[i - 1] - (out[i - 1] / period) + series[i]
        return [x if x is not None else 0.0 for x in out]

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down

    atr = _smoothed(tr, period)
    plus_di = [100.0 * _smoothed(plus_dm, period)[i] / atr[i] if atr[i] > 0 else 0.0 for i in range(n)]
    minus_di = [100.0 * _smoothed(minus_dm, period)[i] / atr[i] if atr[i] > 0 else 0.0 for i in range(n)]

    dx = [0.0] * n
    for i in range(period * 2 - 1, n):
        di_sum = plus_di[i] + minus_di[i]
        di_diff = abs(plus_di[i] - minus_di[i])
        dx[i] = 100.0 * di_diff / di_sum if di_sum > 0 else 0.0

    adx_series = [0.0] * n
    adx_series[period * 2 - 1] = sum(dx[period * 2 - 1 - period + 1:period * 2]) / period
    for i in range(period * 2, n):
        adx_series[i] = (adx_series[i - 1] * (period - 1) + dx[i]) / period
    return adx_series

"""
策略与回测常量，供 strategy_test、screening、prediction 等模块复用，避免循环依赖。
"""

from typing import List, Tuple

# (strategy, short_window, long_window, label)
BACKTEST_STRATEGIES: List[Tuple[str, int, int, str]] = [
    ("ma_cross", 5, 20, "MA(5,20)"),
    ("ma_cross", 10, 30, "MA(10,30)"),
    ("ma_cross", 20, 60, "MA(20,60)"),
    ("macd", 12, 26, "MACD"),
    ("kdj", 9, 3, "KDJ"),
    ("rsi", 14, 0, "RSI(14)"),
    ("bollinger", 0, 20, "BOLL(20)"),
]

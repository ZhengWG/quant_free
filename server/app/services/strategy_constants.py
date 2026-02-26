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
    # 扩充策略（用于全自动交易）
    ("triple_ema", 4, 18, "三重EMA(4,18)"),        # 三重EMA趋势跟踪，A股流行参数
    ("mean_rev_rsi", 14, 20, "RSI+布林回归"),        # RSI+布林双重确认均值回归
    ("composite", 12, 26, "MACD+RSI综合"),           # MACD+RSI+BOLL三指标多数投票
    # 短线策略（提高交易频率）
    ("ma_cross", 3, 8, "MA(3,8)"),                  # 超短期MA，信号更频繁
    ("rsi", 7, 0, "RSI(7)"),                        # 快速RSI，对超买超卖更敏感
    ("bollinger", 0, 10, "BOLL短线(10)"),            # 短周期布林带，频繁均值回归
    ("breakout", 0, 20, "价格突破(20)"),              # 创20日新高买入，回撤7%离场
]

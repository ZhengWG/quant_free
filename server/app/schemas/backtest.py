"""
回测模式
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BacktestParams(BaseModel):
    """回测参数"""
    stock_code: str
    strategy: str = "ma_cross"  # ma_cross, macd, kdj, rsi, bollinger
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    initial_capital: float = 100000.0
    short_window: int = 5  # 短周期
    long_window: int = 20  # 长周期
    # 风控参数（None = 使用引擎默认值）
    stop_loss_pct: Optional[float] = None       # 止损比例，如 0.08 = 8%
    trailing_stop_pct: Optional[float] = None   # 移动止盈回撤，如 0.12 = 12%
    risk_per_trade: Optional[float] = None      # 单笔风险占资金比例，如 0.02 = 2%
    max_position_pct: Optional[float] = None    # 最大仓位占比，如 0.95 = 95%
    trend_ma_len: Optional[int] = None          # 趋势均线天数，如 60
    cooldown_bars: Optional[int] = None         # 止损后冷却天数，如 3


class BacktestTrade(BaseModel):
    """回测中的单笔交易"""
    date: str
    action: str  # BUY / SELL
    price: float
    quantity: int
    profit: Optional[float] = None


class PricePoint(BaseModel):
    """日线价格点"""
    date: str
    close: float

class BacktestResult(BaseModel):
    """回测结果"""
    id: str
    stock_code: str
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_percent: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    trades: List[BacktestTrade] = []
    price_series: List[PricePoint] = []

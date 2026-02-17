"""
回测模式
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BacktestParams(BaseModel):
    """回测参数"""
    stock_code: str
    strategy: str = "ma_cross"  # ma_cross, macd, kdj
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    initial_capital: float = 100000.0
    short_window: int = 5  # 短周期
    long_window: int = 20  # 长周期


class BacktestTrade(BaseModel):
    """回测中的单笔交易"""
    date: str
    action: str  # BUY / SELL
    price: float
    quantity: int
    profit: Optional[float] = None


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

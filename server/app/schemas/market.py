"""
行情数据模式
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Stock(BaseModel):
    """股票数据"""
    code: str
    name: str
    market: str  # A股、港股、美股等
    price: float
    change: float
    change_percent: float
    volume: float
    amount: float
    high: float
    low: float
    open: float
    pre_close: float
    timestamp: datetime
    
    class Config:
        from_attributes = True


class KLineData(BaseModel):
    """K线数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class HistoryData(BaseModel):
    """历史数据"""
    date: str
    price: float
    volume: float
    amount: float


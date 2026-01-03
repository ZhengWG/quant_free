"""
策略模式
"""

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class StrategyParams(BaseModel):
    """策略生成参数"""
    stock_code: str
    risk_level: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = "MEDIUM"
    time_horizon: Optional[str] = "短期"
    custom_prompt: Optional[str] = None


class Strategy(BaseModel):
    """策略"""
    id: str
    stock_code: str
    stock_name: str
    action: Literal["BUY", "SELL", "HOLD"]
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence: float
    reasoning: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    time_horizon: str
    ai_model: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StrategyCreate(BaseModel):
    """创建策略"""
    stock_code: str
    stock_name: str
    action: Literal["BUY", "SELL", "HOLD"]
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence: float
    reasoning: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    time_horizon: str
    ai_model: str


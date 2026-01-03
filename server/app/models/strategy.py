"""
策略模型
"""

from sqlalchemy import Column, String, Float, Text
from app.models.base import BaseModel


class Strategy(BaseModel):
    """策略模型"""
    __tablename__ = "strategies"
    
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))
    action = Column(String(10), nullable=False)  # BUY, SELL, HOLD
    target_price = Column(Float)
    stop_loss = Column(Float)
    confidence = Column(Float)
    reasoning = Column(Text)
    risk_level = Column(String(20))  # LOW, MEDIUM, HIGH
    time_horizon = Column(String(50))
    ai_model = Column(String(50))


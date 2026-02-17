"""
持仓模型
"""

from sqlalchemy import Column, String, Integer, Float
from app.models.base import BaseModel


class Position(BaseModel):
    """持仓模型"""
    __tablename__ = "positions"

    stock_code = Column(String(20), unique=True, nullable=False, index=True)
    stock_name = Column(String(100))
    quantity = Column(Integer, nullable=False, default=0)
    cost_price = Column(Float, nullable=False, default=0.0)

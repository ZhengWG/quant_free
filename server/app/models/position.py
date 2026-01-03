"""
持仓模型
"""

from sqlalchemy import Column, String, Integer, Float
from app.models.base import BaseModel


class Position(BaseModel):
    """持仓模型"""
    __tablename__ = "positions"
    
    stock_code = Column(String(20), primary_key=True)
    stock_name = Column(String(100))
    quantity = Column(Integer, nullable=False)
    cost_price = Column(Float, nullable=False)


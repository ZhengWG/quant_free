"""
股票模型
"""

from sqlalchemy import Column, String, Text
from app.models.base import BaseModel


class Stock(BaseModel):
    """自选股模型"""
    __tablename__ = "stocks"
    
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(100))
    market = Column(String(20))  # A股、港股、美股等
    group_name = Column(String(50))


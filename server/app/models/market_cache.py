"""
行情缓存模型
"""

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class MarketDataCache(Base):
    """行情数据缓存模型"""
    __tablename__ = "market_data_cache"
    
    code = Column(String(20), primary_key=True)
    data = Column(Text, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())


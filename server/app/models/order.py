"""
订单模型
"""

from sqlalchemy import Column, String, Integer, Float, DateTime
from app.models.base import BaseModel


class Order(BaseModel):
    """订单模型"""
    __tablename__ = "orders"

    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))
    type = Column(String(10), nullable=False)  # BUY, SELL
    order_type = Column(String(10), nullable=False)  # MARKET, LIMIT
    price = Column(Float)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)  # PENDING, FILLED, CANCELLED, REJECTED
    filled_quantity = Column(Integer, default=0)
    filled_price = Column(Float, default=0)

    # 费用明细
    stamp_tax = Column(Float, default=0.0)       # 印花税 (卖出0.05%)
    commission = Column(Float, default=0.0)      # 佣金 (0.025%, 最低¥5)
    transfer_fee = Column(Float, default=0.0)    # 过户费 (0.001%)
    total_fee = Column(Float, default=0.0)       # 总费用
    slippage = Column(Float, default=0.0)        # 滑点 (%)

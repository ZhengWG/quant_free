"""
与 QuantFree 约定的请求/响应模型（与 server/app/schemas/trade.py 对齐）
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class OrderCreate(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    type: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"]
    price: Optional[float] = None
    quantity: int


class Order(BaseModel):
    id: str
    stock_code: str
    stock_name: str
    type: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"]
    price: Optional[float] = None
    quantity: int
    status: Literal["PENDING", "FILLED", "CANCELLED", "REJECTED"]
    filled_quantity: int
    filled_price: float
    stamp_tax: float = 0.0
    commission: float = 0.0
    transfer_fee: float = 0.0
    total_fee: float = 0.0
    slippage: float = 0.0
    created_at: datetime
    updated_at: datetime


class Position(BaseModel):
    stock_code: str
    stock_name: str
    quantity: int
    cost_price: float
    current_price: float
    market_value: float
    profit: float
    profit_percent: float
    total_fees: float = 0.0
    realized_profit: float = 0.0


class AccountInfo(BaseModel):
    total_asset: float
    available_cash: float
    market_value: float
    profit: float
    profit_percent: float
    total_fees_paid: float = 0.0

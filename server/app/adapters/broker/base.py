"""
券商适配器抽象基类
实盘模式下 TradeService 通过此接口调用具体券商 API。
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.schemas.trade import Order, OrderCreate, Position, AccountInfo


class BrokerAdapter(ABC):
    """券商 API 适配器抽象类"""

    @abstractmethod
    async def place_order(self, order: OrderCreate) -> Order:
        """提交订单，返回成交结果（含 id、filled_price 等）"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        pass

    @abstractmethod
    async def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """查询订单列表"""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """查询持仓列表"""
        pass

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """查询账户信息"""
        pass

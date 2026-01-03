"""
交易执行服务
"""

import uuid
from typing import List, Optional
from datetime import datetime
from loguru import logger

from app.schemas.trade import Order, OrderCreate, Position, AccountInfo
from app.core.database import AsyncSessionLocal
from app.models.order import Order as OrderModel


class TradeService:
    """交易执行服务"""
    
    async def place_order(self, order: OrderCreate) -> Order:
        """提交订单"""
        try:
            # TODO: 调用券商API执行交易
            order_id = str(uuid.uuid4())
            
            new_order = Order(
                id=order_id,
                stock_code=order.stock_code,
                stock_name=order.stock_name or f"股票{order.stock_code}",
                type=order.type,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status="PENDING",
                filled_quantity=0,
                filled_price=0.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # 保存到数据库
            await self._save_order(new_order)
            
            return new_order
        except Exception as e:
            logger.error(f"Place order error: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        try:
            # TODO: 调用券商API撤销订单
            async with AsyncSessionLocal() as session:
                order = await session.get(OrderModel, order_id)
                if order:
                    order.status = "CANCELLED"
                    order.updated_at = datetime.now()
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            raise
    
    async def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """查询订单"""
        try:
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                stmt = select(OrderModel)
                if status:
                    stmt = stmt.where(OrderModel.status == status)
                result = await session.execute(stmt)
                results = result.scalars().all()
                return [Order.model_validate(r) for r in results]
        except Exception as e:
            logger.error(f"Get orders error: {e}")
            raise
    
    async def get_positions(self) -> List[Position]:
        """查询持仓"""
        try:
            # TODO: 从券商API获取持仓
            return []
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            raise
    
    async def get_account_info(self) -> AccountInfo:
        """查询账户信息"""
        try:
            # TODO: 从券商API获取账户信息
            return AccountInfo(
                total_asset=0.0,
                available_cash=0.0,
                market_value=0.0,
                profit=0.0,
                profit_percent=0.0
            )
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            raise
    
    async def _save_order(self, order: Order):
        """保存订单到数据库"""
        async with AsyncSessionLocal() as session:
            order_model = OrderModel(
                id=order.id,
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                type=order.type,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status=order.status,
                filled_quantity=order.filled_quantity,
                filled_price=order.filled_price
            )
            session.add(order_model)
            await session.commit()


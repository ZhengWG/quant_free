"""
交易执行服务（模拟交易模式）
"""

import uuid
from typing import List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy import select

from app.schemas.trade import Order, OrderCreate, Position, AccountInfo
from app.core.database import AsyncSessionLocal
from app.models.order import Order as OrderModel
from app.models.position import Position as PositionModel


# 模拟账户初始资金
INITIAL_CASH = 1000000.0


class TradeService:
    """交易执行服务（模拟交易）"""

    async def place_order(self, order: OrderCreate) -> Order:
        """提交订单（模拟执行：立即成交）"""
        try:
            order_id = str(uuid.uuid4())
            now = datetime.now()

            # 模拟交易：使用市价或指定的限价直接成交
            fill_price = order.price if order.price else 0.0

            # 如果是市价单且没有价格，暂时以 PENDING 状态保存
            status = "FILLED" if fill_price > 0 else "PENDING"
            filled_qty = order.quantity if status == "FILLED" else 0

            new_order = Order(
                id=order_id,
                stock_code=order.stock_code,
                stock_name=order.stock_name or f"股票{order.stock_code}",
                type=order.type,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status=status,
                filled_quantity=filled_qty,
                filled_price=fill_price,
                created_at=now,
                updated_at=now,
            )

            # 保存订单到数据库
            await self._save_order(new_order)

            # 如果成交，更新持仓
            if status == "FILLED":
                await self._update_position(new_order)

            return new_order
        except Exception as e:
            logger.error(f"Place order error: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        try:
            async with AsyncSessionLocal() as session:
                order = await session.get(OrderModel, order_id)
                if order and order.status == "PENDING":
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
            async with AsyncSessionLocal() as session:
                stmt = select(OrderModel).order_by(OrderModel.created_at.desc())
                if status:
                    stmt = stmt.where(OrderModel.status == status)
                result = await session.execute(stmt)
                results = result.scalars().all()
                return [Order.model_validate(r) for r in results]
        except Exception as e:
            logger.error(f"Get orders error: {e}")
            raise

    async def get_positions(self) -> List[Position]:
        """查询持仓（从数据库计算）"""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(PositionModel).where(PositionModel.quantity > 0)
                result = await session.execute(stmt)
                positions = result.scalars().all()

                result_list = []
                for p in positions:
                    # 使用成本价作为当前价（实际应从行情接口获取）
                    current_price = p.cost_price
                    market_value = current_price * p.quantity
                    cost_total = p.cost_price * p.quantity
                    profit = market_value - cost_total
                    profit_pct = (profit / cost_total * 100) if cost_total > 0 else 0.0

                    result_list.append(Position(
                        stock_code=p.stock_code,
                        stock_name=p.stock_name or f"股票{p.stock_code}",
                        quantity=p.quantity,
                        cost_price=p.cost_price,
                        current_price=current_price,
                        market_value=round(market_value, 2),
                        profit=round(profit, 2),
                        profit_percent=round(profit_pct, 2),
                    ))

                return result_list
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            raise

    async def get_account_info(self) -> AccountInfo:
        """查询账户信息（根据订单和持仓计算）"""
        try:
            positions = await self.get_positions()
            market_value = sum(p.market_value for p in positions)

            # 计算已花费的资金（FILLED 的买单 - FILLED 的卖单）
            async with AsyncSessionLocal() as session:
                stmt = select(OrderModel).where(OrderModel.status == "FILLED")
                result = await session.execute(stmt)
                orders = result.scalars().all()

            spent = 0.0
            for o in orders:
                if o.type == "BUY":
                    spent += (o.filled_price or 0) * (o.filled_quantity or 0)
                elif o.type == "SELL":
                    spent -= (o.filled_price or 0) * (o.filled_quantity or 0)

            available_cash = INITIAL_CASH - spent
            total_asset = available_cash + market_value
            profit = total_asset - INITIAL_CASH
            profit_pct = (profit / INITIAL_CASH * 100) if INITIAL_CASH > 0 else 0.0

            return AccountInfo(
                total_asset=round(total_asset, 2),
                available_cash=round(available_cash, 2),
                market_value=round(market_value, 2),
                profit=round(profit, 2),
                profit_percent=round(profit_pct, 2),
            )
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            raise

    async def _update_position(self, order: Order):
        """根据成交订单更新持仓"""
        async with AsyncSessionLocal() as session:
            stmt = select(PositionModel).where(PositionModel.stock_code == order.stock_code)
            result = await session.execute(stmt)
            position = result.scalar_one_or_none()

            if order.type == "BUY":
                if position:
                    # 加仓：计算新的成本均价
                    total_cost = position.cost_price * position.quantity + order.filled_price * order.filled_quantity
                    position.quantity += order.filled_quantity
                    position.cost_price = total_cost / position.quantity if position.quantity > 0 else 0
                    position.stock_name = order.stock_name
                else:
                    # 新建持仓
                    position = PositionModel(
                        stock_code=order.stock_code,
                        stock_name=order.stock_name,
                        quantity=order.filled_quantity,
                        cost_price=order.filled_price,
                    )
                    session.add(position)
            elif order.type == "SELL":
                if position and position.quantity >= order.filled_quantity:
                    position.quantity -= order.filled_quantity
                else:
                    logger.warning(f"Insufficient position for sell: {order.stock_code}")

            await session.commit()

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
                filled_price=order.filled_price,
            )
            session.add(order_model)
            await session.commit()

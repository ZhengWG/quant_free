"""
交易执行服务（支持模拟 / 实盘切换）
模拟：滑点、手续费、本地库；实盘：通过 BrokerAdapter 调用券商网关，成交结果落库便于导出。
"""

import uuid
import random
from typing import List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy import select

from app.schemas.trade import Order, OrderCreate, Position, AccountInfo
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.order import Order as OrderModel
from app.models.position import Position as PositionModel
from app.services.market_data_service import MarketDataService

# ========== 模拟交易参数 ==========
INITIAL_CASH = 1000000.0        # 初始资金 100万
SLIPPAGE_RATE = 0.001           # 滑点基准 0.1%
SLIPPAGE_RANDOM = 0.0005       # 随机浮动 ±0.05%
COMMISSION_RATE = 0.00025       # 佣金费率 0.025%
COMMISSION_MIN = 5.0            # 最低佣金 ¥5
STAMP_TAX_RATE = 0.0005         # 印花税 0.05% (仅卖出)
TRANSFER_FEE_RATE = 0.00001    # 过户费 0.001%


class TradeService:
    """交易执行服务（模拟 / 实盘）"""

    def __init__(self):
        self.market_service = MarketDataService()
        self._broker = None
        if getattr(settings, "TRADING_MODE", "sim") == "live" and settings.BROKER_API_URL:
            from app.adapters.broker.generic_http import GenericHttpBrokerAdapter
            self._broker = GenericHttpBrokerAdapter(settings.BROKER_API_URL)

    def _is_live(self) -> bool:
        return self._broker is not None

    def _calculate_fees(self, order_type: str, fill_price: float, quantity: int) -> dict:
        """
        计算A股交易费用
        :param order_type: BUY / SELL
        :param fill_price: 成交价
        :param quantity: 成交数量
        :return: {stamp_tax, commission, transfer_fee, total_fee}
        """
        amount = fill_price * quantity

        # 印花税: 仅卖出收取
        stamp_tax = round(amount * STAMP_TAX_RATE, 2) if order_type == "SELL" else 0.0

        # 佣金: 双向收取, 最低¥5
        commission = round(max(amount * COMMISSION_RATE, COMMISSION_MIN), 2)

        # 过户费: 双向收取
        transfer_fee = round(amount * TRANSFER_FEE_RATE, 2)

        total_fee = round(stamp_tax + commission + transfer_fee, 2)

        return {
            "stamp_tax": stamp_tax,
            "commission": commission,
            "transfer_fee": transfer_fee,
            "total_fee": total_fee,
        }

    def _apply_slippage(self, price: float, order_type: str) -> tuple:
        """
        模拟滑点
        :return: (slipped_price, slippage_percent)
        """
        # 随机滑点 = 基准 ± 随机浮动
        slip = SLIPPAGE_RATE + random.uniform(-SLIPPAGE_RANDOM, SLIPPAGE_RANDOM)
        slip = max(slip, 0)  # 不为负

        if order_type == "BUY":
            slipped_price = round(price * (1 + slip), 2)
        else:
            slipped_price = round(price * (1 - slip), 2)

        return slipped_price, round(slip * 100, 4)

    async def _get_market_price(self, stock_code: str) -> Optional[float]:
        """获取实时市场价"""
        try:
            stocks = await self.market_service.get_realtime_data([stock_code])
            if stocks:
                return stocks[0].price
        except Exception as e:
            logger.error(f"Get market price error: {e}")
        return None

    async def place_order(self, order: OrderCreate) -> Order:
        """提交订单（模拟或实盘）"""
        if self._is_live():
            return await self._place_order_live(order)
        return await self._place_order_simulated(order)

    async def _place_order_live(self, order: OrderCreate) -> Order:
        """实盘：调用券商网关，结果落库"""
        result = await self._broker.place_order(order)
        await self._save_order(result)
        logger.info(f"Live order filled: {result.type} {result.stock_code} x{result.quantity} @{result.filled_price}")
        return result

    async def _place_order_simulated(self, order: OrderCreate) -> Order:
        """模拟：滑点、手续费、落库、更新持仓"""
        try:
            order_id = str(uuid.uuid4())
            now = datetime.now()

            if order.order_type == "MARKET":
                market_price = await self._get_market_price(order.stock_code)
                if not market_price:
                    raise ValueError(f"无法获取 {order.stock_code} 实时行情，市价单失败")
                base_price = market_price
            else:
                if not order.price or order.price <= 0:
                    raise ValueError("限价单必须指定价格")
                base_price = order.price

            fill_price, slip_pct = self._apply_slippage(base_price, order.type)
            fees = self._calculate_fees(order.type, fill_price, order.quantity)

            if order.type == "SELL":
                has_position = await self._check_position(order.stock_code, order.quantity)
                if not has_position:
                    raise ValueError(f"持仓不足: {order.stock_code}")

            new_order = Order(
                id=order_id,
                stock_code=order.stock_code,
                stock_name=order.stock_name or f"股票{order.stock_code}",
                type=order.type,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status="FILLED",
                filled_quantity=order.quantity,
                filled_price=fill_price,
                stamp_tax=fees["stamp_tax"],
                commission=fees["commission"],
                transfer_fee=fees["transfer_fee"],
                total_fee=fees["total_fee"],
                slippage=slip_pct,
                created_at=now,
                updated_at=now,
            )

            await self._save_order(new_order)
            await self._update_position(new_order)

            logger.info(
                f"Order filled: {order.type} {order.stock_code} x{order.quantity} "
                f"@{fill_price} (slip:{slip_pct}%) fee:¥{fees['total_fee']}"
            )
            return new_order
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Place order error: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """撤销订单（模拟改状态，实盘调券商）"""
        try:
            if self._is_live():
                return await self._broker.cancel_order(order_id)
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
        """查询持仓（实盘来自券商，模拟用实时行情估值）"""
        try:
            if self._is_live():
                return await self._broker.get_positions()
            async with AsyncSessionLocal() as session:
                stmt = select(PositionModel).where(PositionModel.quantity > 0)
                result = await session.execute(stmt)
                positions = result.scalars().all()

                if not positions:
                    return []

                # 批量获取实时行情
                codes = [p.stock_code for p in positions]
                realtime = {}
                try:
                    stocks = await self.market_service.get_realtime_data(codes)
                    for s in stocks:
                        realtime[s.code] = s.price
                except Exception as e:
                    logger.warning(f"Failed to get realtime prices: {e}")

                result_list = []
                for p in positions:
                    current_price = realtime.get(p.stock_code, p.cost_price)
                    market_value = current_price * p.quantity
                    cost_total = p.cost_price * p.quantity
                    profit = market_value - cost_total
                    profit_pct = (profit / cost_total * 100) if cost_total > 0 else 0.0

                    result_list.append(Position(
                        stock_code=p.stock_code,
                        stock_name=p.stock_name or f"股票{p.stock_code}",
                        quantity=p.quantity,
                        cost_price=round(p.cost_price, 4),
                        current_price=current_price,
                        market_value=round(market_value, 2),
                        profit=round(profit, 2),
                        profit_percent=round(profit_pct, 2),
                        total_fees=round(p.total_fees or 0, 2),
                        realized_profit=round(p.realized_profit or 0, 2),
                    ))

                return result_list
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            raise

    async def get_account_info(self) -> AccountInfo:
        """查询账户信息（实盘来自券商，模拟本地计算）"""
        try:
            if self._is_live():
                return await self._broker.get_account()
            positions = await self.get_positions()
            market_value = sum(p.market_value for p in positions)

            # 计算已花费资金和总手续费
            async with AsyncSessionLocal() as session:
                stmt = select(OrderModel).where(OrderModel.status == "FILLED")
                result = await session.execute(stmt)
                orders = result.scalars().all()

            spent = 0.0
            total_fees = 0.0
            for o in orders:
                fee = o.total_fee or 0
                total_fees += fee
                if o.type == "BUY":
                    spent += (o.filled_price or 0) * (o.filled_quantity or 0) + fee
                elif o.type == "SELL":
                    spent -= (o.filled_price or 0) * (o.filled_quantity or 0) - fee

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
                total_fees_paid=round(total_fees, 2),
            )
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            raise

    async def _check_position(self, stock_code: str, quantity: int) -> bool:
        """检查是否有足够持仓"""
        async with AsyncSessionLocal() as session:
            stmt = select(PositionModel).where(PositionModel.stock_code == stock_code)
            result = await session.execute(stmt)
            position = result.scalar_one_or_none()
            return position is not None and position.quantity >= quantity

    async def _update_position(self, order: Order):
        """根据成交订单更新持仓"""
        async with AsyncSessionLocal() as session:
            stmt = select(PositionModel).where(PositionModel.stock_code == order.stock_code)
            result = await session.execute(stmt)
            position = result.scalar_one_or_none()

            if order.type == "BUY":
                if position:
                    # 加仓: 成本含费用
                    old_total = position.cost_price * position.quantity
                    new_total = order.filled_price * order.filled_quantity + order.total_fee
                    position.quantity += order.filled_quantity
                    position.cost_price = (old_total + new_total) / position.quantity
                    position.stock_name = order.stock_name
                    position.total_fees = (position.total_fees or 0) + order.total_fee
                else:
                    # 新建持仓: 成本价含手续费
                    cost_with_fee = (order.filled_price * order.filled_quantity + order.total_fee) / order.filled_quantity
                    position = PositionModel(
                        stock_code=order.stock_code,
                        stock_name=order.stock_name,
                        quantity=order.filled_quantity,
                        cost_price=cost_with_fee,
                        total_fees=order.total_fee,
                        realized_profit=0.0,
                    )
                    session.add(position)
            elif order.type == "SELL":
                if position:
                    # 计算已实现盈亏
                    sell_revenue = order.filled_price * order.filled_quantity - order.total_fee
                    cost_basis = position.cost_price * order.filled_quantity
                    realized = sell_revenue - cost_basis
                    position.quantity -= order.filled_quantity
                    position.total_fees = (position.total_fees or 0) + order.total_fee
                    position.realized_profit = (position.realized_profit or 0) + realized

            await session.commit()

    async def export_orders(self) -> List[dict]:
        """导出订单为可序列化列表（用于 CSV 等）"""
        orders = await self.get_orders()
        return [
            {
                "id": o.id,
                "stock_code": o.stock_code,
                "stock_name": o.stock_name,
                "type": o.type,
                "order_type": o.order_type,
                "price": o.price,
                "quantity": o.quantity,
                "status": o.status,
                "filled_quantity": o.filled_quantity,
                "filled_price": o.filled_price,
                "stamp_tax": o.stamp_tax,
                "commission": o.commission,
                "transfer_fee": o.transfer_fee,
                "total_fee": o.total_fee,
                "slippage": o.slippage,
                "created_at": o.created_at.isoformat() if o.created_at else "",
                "updated_at": o.updated_at.isoformat() if o.updated_at else "",
            }
            for o in orders
        ]

    async def export_positions(self) -> List[dict]:
        """导出持仓为可序列化列表（用于 CSV 等）"""
        positions = await self.get_positions()
        return [
            {
                "stock_code": p.stock_code,
                "stock_name": p.stock_name,
                "quantity": p.quantity,
                "cost_price": p.cost_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "profit": p.profit,
                "profit_percent": p.profit_percent,
                "total_fees": p.total_fees,
                "realized_profit": p.realized_profit,
            }
            for p in positions
        ]

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
                stamp_tax=order.stamp_tax,
                commission=order.commission,
                transfer_fee=order.transfer_fee,
                total_fee=order.total_fee,
                slippage=order.slippage,
            )
            session.add(order_model)
            await session.commit()

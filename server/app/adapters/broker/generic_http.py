"""
通用 HTTP 券商适配器
通过可配置的 BROKER_API_URL 调用券商网关，请求/响应与 app.schemas.trade 对齐。
若网关返回格式不同，可在此做字段映射。
"""

from datetime import datetime
from typing import List, Optional
import httpx
from loguru import logger

from app.schemas.trade import Order, OrderCreate, Position, AccountInfo
from app.adapters.broker.base import BrokerAdapter
from app.core.config import settings


class GenericHttpBrokerAdapter(BrokerAdapter):
    """通过 HTTP 调用券商网关的通用实现"""

    def __init__(self, base_url: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _order_from_dict(self, d: dict) -> Order:
        """将网关返回的 dict 转为 Order"""
        return Order(
            id=str(d.get("id", "")),
            stock_code=str(d.get("stock_code", "")),
            stock_name=str(d.get("stock_name", "")),
            type=d.get("type", "BUY"),
            order_type=d.get("order_type", "MARKET"),
            price=d.get("price"),
            quantity=int(d.get("quantity", 0)),
            status=d.get("status", "PENDING"),
            filled_quantity=int(d.get("filled_quantity", 0)),
            filled_price=float(d.get("filled_price", 0)),
            stamp_tax=float(d.get("stamp_tax", 0)),
            commission=float(d.get("commission", 0)),
            transfer_fee=float(d.get("transfer_fee", 0)),
            total_fee=float(d.get("total_fee", 0)),
            slippage=float(d.get("slippage", 0)),
            created_at=self._parse_datetime(d.get("created_at")),
            updated_at=self._parse_datetime(d.get("updated_at")),
        )

    @staticmethod
    def _parse_datetime(v) -> datetime:
        if v is None:
            return datetime.now()
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                return datetime.now()
        return datetime.now()

    def _position_from_dict(self, d: dict) -> Position:
        return Position(
            stock_code=str(d.get("stock_code", "")),
            stock_name=str(d.get("stock_name", "")),
            quantity=int(d.get("quantity", 0)),
            cost_price=float(d.get("cost_price", 0)),
            current_price=float(d.get("current_price", 0)),
            market_value=float(d.get("market_value", 0)),
            profit=float(d.get("profit", 0)),
            profit_percent=float(d.get("profit_percent", 0)),
            total_fees=float(d.get("total_fees", 0)),
            realized_profit=float(d.get("realized_profit", 0)),
        )

    def _account_from_dict(self, d: dict) -> AccountInfo:
        return AccountInfo(
            total_asset=float(d.get("total_asset", 0)),
            available_cash=float(d.get("available_cash", 0)),
            market_value=float(d.get("market_value", 0)),
            profit=float(d.get("profit", 0)),
            profit_percent=float(d.get("profit_percent", 0)),
            total_fees_paid=float(d.get("total_fees_paid", 0)),
        )

    async def place_order(self, order: OrderCreate) -> Order:
        client = await self._client_get()
        payload = order.model_dump()
        try:
            r = await client.post("/order", json=payload)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            return self._order_from_dict(data)
        except Exception as e:
            logger.error(f"Broker place_order error: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        client = await self._client_get()
        try:
            r = await client.delete(f"/order/{order_id}")
            r.raise_for_status()
            data = r.json()
            return data.get("success", data.get("data", False))
        except Exception as e:
            logger.error(f"Broker cancel_order error: {e}")
            raise

    async def get_orders(self, status: Optional[str] = None) -> List[Order]:
        client = await self._client_get()
        params = {} if status is None else {"status": status}
        try:
            r = await client.get("/orders", params=params)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            return [self._order_from_dict(item) for item in (data or [])]
        except Exception as e:
            logger.error(f"Broker get_orders error: {e}")
            raise

    async def get_positions(self) -> List[Position]:
        client = await self._client_get()
        try:
            r = await client.get("/positions")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            return [self._position_from_dict(item) for item in (data or [])]
        except Exception as e:
            logger.error(f"Broker get_positions error: {e}")
            raise

    async def get_account(self) -> AccountInfo:
        client = await self._client_get()
        try:
            r = await client.get("/account")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            return self._account_from_dict(data or {})
        except Exception as e:
            logger.error(f"Broker get_account error: {e}")
            raise

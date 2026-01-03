"""
交易路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from loguru import logger

from app.schemas.trade import Order, OrderCreate, Position, AccountInfo
from app.schemas.common import ApiResponse
from app.services.trade_service import TradeService

router = APIRouter()
trade_service = TradeService()


@router.post("/order", response_model=ApiResponse[Order])
async def place_order(order: OrderCreate):
    """提交订单"""
    try:
        result = await trade_service.place_order(order)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Place order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/order/{order_id}", response_model=ApiResponse[bool])
async def cancel_order(order_id: str):
    """撤销订单"""
    try:
        success = await trade_service.cancel_order(order_id)
        return ApiResponse(success=success, message="撤单成功" if success else "撤单失败")
    except Exception as e:
        logger.error(f"Cancel order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=ApiResponse[List[Order]])
async def get_orders(status: Optional[str] = Query(None, description="订单状态")):
    """查询订单"""
    try:
        orders = await trade_service.get_orders(status)
        return ApiResponse(success=True, data=orders)
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=ApiResponse[List[Position]])
async def get_positions():
    """查询持仓"""
    try:
        positions = await trade_service.get_positions()
        return ApiResponse(success=True, data=positions)
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account", response_model=ApiResponse[AccountInfo])
async def get_account_info():
    """查询账户信息"""
    try:
        account_info = await trade_service.get_account_info()
        return ApiResponse(success=True, data=account_info)
    except Exception as e:
        logger.error(f"Get account info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


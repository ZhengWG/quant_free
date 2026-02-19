"""
交易路由
"""

import csv
import io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
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


def _dicts_to_csv(rows: List[dict], fieldnames: List[str], write_bom: bool = True) -> str:
    """将字典列表转为 CSV 字符串，UTF-8 BOM 便于 Excel 打开"""
    buf = io.StringIO()
    if write_bom:
        buf.write("\ufeff")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@router.get("/export")
async def export_trades(
    format: str = Query("csv", description="格式: csv"),
    type: str = Query("orders", description="类型: orders | positions | all"),
):
    """导出交易记录为 CSV"""
    if format != "csv":
        raise HTTPException(status_code=400, detail="仅支持 format=csv")
    if type not in ("orders", "positions", "all"):
        raise HTTPException(status_code=400, detail="type 须为 orders / positions / all")

    try:
        date_suffix = datetime.now().strftime("%Y%m%d")
        if type == "orders":
            rows = await trade_service.export_orders()
            fieldnames = [
                "id", "stock_code", "stock_name", "type", "order_type", "price", "quantity",
                "status", "filled_quantity", "filled_price", "stamp_tax", "commission",
                "transfer_fee", "total_fee", "slippage", "created_at", "updated_at",
            ]
            filename = f"orders_{date_suffix}.csv"
        elif type == "positions":
            rows = await trade_service.export_positions()
            fieldnames = [
                "stock_code", "stock_name", "quantity", "cost_price", "current_price",
                "market_value", "profit", "profit_percent", "total_fees", "realized_profit",
            ]
            filename = f"positions_{date_suffix}.csv"
        else:
            orders = await trade_service.export_orders()
            positions = await trade_service.export_positions()
            order_fields = [
                "id", "stock_code", "stock_name", "type", "order_type", "price", "quantity",
                "status", "filled_quantity", "filled_price", "stamp_tax", "commission",
                "transfer_fee", "total_fee", "slippage", "created_at", "updated_at",
            ]
            pos_fields = [
                "stock_code", "stock_name", "quantity", "cost_price", "current_price",
                "market_value", "profit", "profit_percent", "total_fees", "realized_profit",
            ]
            csv1 = _dicts_to_csv(orders, order_fields, write_bom=True)
            csv2 = _dicts_to_csv(positions, pos_fields, write_bom=False)
            content = csv1.strip() + "\n\n[持仓]\n" + csv2.strip()
            body = content.encode("utf-8-sig")
            return StreamingResponse(
                io.BytesIO(body),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="trades_{date_suffix}.csv"'},
            )

        content = _dicts_to_csv(rows, fieldnames)
        body = content.encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(body),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Export trades error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


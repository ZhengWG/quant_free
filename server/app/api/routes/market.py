"""
行情数据路由
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List
from loguru import logger

from app.schemas.market import Stock, KLineData, HistoryData
from app.schemas.common import ApiResponse
from app.services.market_data_service import MarketDataService

router = APIRouter()
market_service = MarketDataService()


@router.get("/realtime", response_model=ApiResponse[List[Stock]])
async def get_realtime_data(codes: str = Query(..., description="股票代码，逗号分隔")):
    """获取实时行情"""
    try:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        if not code_list:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        data = await market_service.get_realtime_data(code_list)
        return ApiResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Get realtime data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{code}", response_model=ApiResponse[List[HistoryData]])
async def get_history_data(code: str, period: str = Query("1d", description="周期")):
    """获取历史数据"""
    try:
        data = await market_service.get_history_data(code, period)
        return ApiResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Get history data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kline/{code}", response_model=ApiResponse[List[KLineData]])
async def get_kline_data(code: str, type: str = Query("day", description="K线类型")):
    """获取K线数据"""
    try:
        data = await market_service.get_kline_data(code, type)
        return ApiResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Get kline data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


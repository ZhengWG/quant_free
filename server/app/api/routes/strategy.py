"""
策略路由
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from loguru import logger

from app.schemas.strategy import Strategy, StrategyParams
from app.schemas.common import ApiResponse
from app.services.strategy_service import StrategyService

router = APIRouter()
strategy_service = StrategyService()


@router.post("/generate", response_model=ApiResponse[Strategy])
async def generate_strategy(params: StrategyParams):
    """生成策略"""
    try:
        strategy = await strategy_service.generate_strategy(params)
        return ApiResponse(success=True, data=strategy)
    except Exception as e:
        logger.error(f"Generate strategy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}", response_model=ApiResponse[Strategy])
async def get_strategy(id: str):
    """获取策略详情"""
    try:
        strategy = await strategy_service.get_strategy(id)
        return ApiResponse(success=True, data=strategy)
    except Exception as e:
        logger.error(f"Get strategy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/list", response_model=ApiResponse[List[Strategy]])
async def get_history_strategies(stock_code: Optional[str] = None):
    """获取历史策略"""
    try:
        strategies = await strategy_service.get_history_strategies(stock_code)
        return ApiResponse(success=True, data=strategies)
    except Exception as e:
        logger.error(f"Get history strategies error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


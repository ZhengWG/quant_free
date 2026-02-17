"""
回测路由
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.schemas.backtest import BacktestParams, BacktestResult
from app.schemas.common import ApiResponse
from app.services.backtest_service import BacktestService

router = APIRouter()
backtest_service = BacktestService()


@router.post("/run", response_model=ApiResponse[BacktestResult])
async def run_backtest(params: BacktestParams):
    """运行回测"""
    try:
        result = await backtest_service.run_backtest(params)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Run backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}", response_model=ApiResponse[BacktestResult])
async def get_backtest_result(id: str):
    """获取回测结果"""
    try:
        result = await backtest_service.get_backtest_result(id)
        return ApiResponse(success=True, data=result)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Not implemented yet")
    except Exception as e:
        logger.error(f"Get backtest result error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

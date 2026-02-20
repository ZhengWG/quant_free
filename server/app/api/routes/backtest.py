"""
回测路由
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.schemas.backtest import BacktestParams, BacktestResult, BacktestOptimizeParams, BacktestOptimizeResult
from app.schemas.screening import SmartScreenParams, SmartScreenResult
from app.schemas.prediction import PredictionParams, PredictionResult
from app.schemas.strategy_test import StrategyTestParams, StrategyTestResult, StrategyAnalyzeParams, StrategyAnalyzeResult
from app.schemas.common import ApiResponse
from app.services.backtest_service import BacktestService
from app.services.screening_service import ScreeningService
from app.services.prediction_service import PredictionService
from app.services.strategy_test_service import StrategyTestService

router = APIRouter()
backtest_service = BacktestService()
screening_service = ScreeningService()
prediction_service = PredictionService()
strategy_test_service = StrategyTestService()


@router.post("/run", response_model=ApiResponse[BacktestResult])
async def run_backtest(params: BacktestParams):
    """运行回测"""
    try:
        result = await backtest_service.run_backtest(params)
        if result is None:
            return ApiResponse(
                success=True,
                data=None,
                message=f"{params.stock_code} 暂无可用的K线数据，跳过回测"
            )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Run backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", response_model=ApiResponse[BacktestOptimizeResult])
async def optimize_backtest(params: BacktestOptimizeParams):
    """策略参数网格搜索，返回按夏普排序的 top_n 结果"""
    try:
        result = await backtest_service.run_optimize(params)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Backtest optimize error: {e}")
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


@router.post("/smart-screen", response_model=ApiResponse[SmartScreenResult])
async def smart_screen(params: SmartScreenParams):
    """智能选股回测"""
    try:
        result = await screening_service.run_smart_screen(params)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Smart screen error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=ApiResponse[PredictionResult])
async def predict(params: PredictionParams):
    """预测分析"""
    try:
        result = await prediction_service.run_prediction(params)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-test", response_model=ApiResponse[StrategyTestResult])
async def strategy_test(params: StrategyTestParams):
    """策略测试（Walk-Forward Validation）"""
    try:
        result = await strategy_test_service.run_test(params)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Strategy test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=ApiResponse[StrategyAnalyzeResult])
async def analyze_strategy(params: StrategyAnalyzeParams):
    """单股策略分析：80/20 多策略回测，按相对收益评分取 TopK 策略，并给出未来 N 月收益预测"""
    try:
        test_params = StrategyTestParams(
            stock_code=params.stock_code,
            start_date=params.start_date,
            end_date=params.end_date,
            initial_capital=params.initial_capital,
            train_ratio=params.train_ratio,
        )
        result = await strategy_test_service.run_test(test_params)
        top_items = result.items[: params.top_k] if result.items else []
        months = max(1, params.prediction_months)
        strategies_with_future = []
        for item in top_items:
            future_pct = strategy_test_service.predict_future_return_pct(
                item.train_return_pct, item.train_bars, months
            )
            strategies_with_future.append(
                item.model_copy(
                    update={
                        "prediction_months": months,
                        "predicted_future_return_pct": round(future_pct, 2),
                    }
                )
            )
        analyze_result = StrategyAnalyzeResult(
            stock_code=result.stock_code,
            stock_name=result.stock_name,
            full_start=result.full_start,
            full_end=result.full_end,
            train_ratio=result.train_ratio,
            full_bnh_pct=result.full_bnh_pct,
            test_bnh_pct=result.test_bnh_pct,
            time_taken_seconds=result.time_taken_seconds,
            prediction_months=months,
            strategies=strategies_with_future,
        )
        return ApiResponse(success=True, data=analyze_result)
    except Exception as e:
        logger.error(f"Strategy analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

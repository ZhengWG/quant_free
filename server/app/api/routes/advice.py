"""
每日交易建议路由（Phase 2）
- POST /api/v1/advice/daily/run   立即生成一次每日建议（可选发邮件）
- GET  /api/v1/advice/history     查询推荐历史（按日期/股票）
"""

from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException
from loguru import logger
from sqlalchemy import select

from app.schemas.common import ApiResponse
from app.core.database import AsyncSessionLocal
from app.models.recommendation import RecommendationHistory
from app.services.daily_advice_service import DailyAdviceService
from app.services.email_service import send_daily_advice

router = APIRouter()
advice_service = DailyAdviceService()


@router.post("/daily/run", response_model=ApiResponse)
async def run_daily_advice(
    date: Optional[str] = Query(None, description="运行日期 YYYY-MM-DD，默认今天"),
    pool: str = Query("hs_and_hk", description="股票池: hot_hs/hot_hk/hs_and_hk/industry_leaders/custom"),
    top_n: int = Query(5, ge=1, le=20),
    mode: str = Query("smart_v2", description="classic 或 smart_v2"),
    send_email: bool = Query(True, description="是否发送建议邮件"),
):
    """立即生成每日交易建议（对账历史 → 持有/新增/退出），可选发邮件。"""
    try:
        report = await advice_service.generate(
            run_date=date, pool=pool, top_n=top_n, mode=mode,
        )
        emailed = False
        if send_email:
            emailed = await send_daily_advice(report)
        return ApiResponse(success=True, data={**report, "emailed": emailed})
    except Exception as e:
        logger.exception("run_daily_advice error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=ApiResponse)
async def get_history(
    date: Optional[str] = Query(None, description="按日期过滤 YYYY-MM-DD"),
    stock_code: Optional[str] = Query(None, description="按股票代码过滤"),
    limit: int = Query(100, ge=1, le=500),
):
    """查询推荐历史记录。"""
    async with AsyncSessionLocal() as db:
        q = select(RecommendationHistory)
        if date:
            q = q.where(RecommendationHistory.date == date)
        if stock_code:
            q = q.where(RecommendationHistory.stock_code == stock_code)
        q = q.order_by(RecommendationHistory.date.desc()).limit(limit)
        rows = (await db.execute(q)).scalars().all()

    data = [
        {
            "date": r.date, "market": r.market, "stock_code": r.stock_code,
            "stock_name": r.stock_name, "strategy_label": r.strategy_label,
            "signal": r.signal, "status": r.status,
            "current_price": r.current_price, "entry_ref_price": r.entry_ref_price,
            "target_price": r.target_price, "stop_loss": r.stop_loss,
            "return_since_rec_pct": r.return_since_rec_pct,
            "first_recommended_date": r.first_recommended_date,
            "days_held": r.days_held, "miss_count": r.miss_count,
            "confidence": r.confidence, "composite_score": r.composite_score,
            "pe": r.pe, "pb": r.pb, "roe": r.roe, "ai_comment": r.ai_comment,
            "exit_reason": r.exit_reason,
        }
        for r in rows
    ]
    return ApiResponse(success=True, data=data)

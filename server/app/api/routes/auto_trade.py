"""
全自动交易 REST API
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.schemas.auto_trade import (
    AutoTradeSessionCreate,
    AutoTradeSessionOut,
    ForwardTestCreate,
    ForwardTestGroupOut,
    OfflineSimConfig,
    OfflineSimResult,
    PerformanceOut,
    PositionOut,
    SignalOut,
    STRATEGY_PRESETS,
    ValidateOnlyRequest,
    ValidateOnlyResponse,
    ValidateResult,
)
from app.services.auto_trade_service import AutoTradeService
from app.services.offline_simulation_service import OfflineSimulationService

router = APIRouter()
_svc = AutoTradeService()
_sim_svc = OfflineSimulationService()


# ──────────────────────────────────────────────
#  策略预设
# ──────────────────────────────────────────────

@router.get("/presets", summary="查看所有策略预设")
async def list_presets():
    """
    返回所有内置策略预设及其风控参数。
    创建会话或运行离线模拟时传入 `preset_name` 即可快速应用。
    """
    result = []
    for key, preset in STRATEGY_PRESETS.items():
        result.append({
            "preset_name": key,
            "display_name": preset["display_name"],
            "description": preset["description"],
            "params": {k: v for k, v in preset.items() if k not in ("display_name", "description")},
        })
    return {"success": True, "data": result}


# ──────────────────────────────────────────────
#  会话管理
# ──────────────────────────────────────────────

@router.post("/sessions", summary="创建并启动自动交易会话")
async def create_session(body: AutoTradeSessionCreate):
    """
    创建一个全自动交易会话：
    - 异步历史验证（默认5年 Walk-Forward）→ 自动选最优策略
    - `skip_validate=true` 可跳过历史验证，直接开始
    - 每日调度器在15:15后自动触发信号生成
    """
    try:
        session_id = await _svc.create_session(body)
        return {
            "success": True,
            "data": {"session_id": session_id},
            "message": (
                "会话已创建，历史验证进行中（后台），完成后自动切换 running 状态"
                if not body.skip_validate
                else "会话已创建，直接进入 running 状态"
            ),
        }
    except Exception as e:
        logger.error(f"create_session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[AutoTradeSessionOut], summary="查看所有会话")
async def list_sessions():
    return await _svc.list_sessions()


@router.get("/sessions/{session_id}", response_model=AutoTradeSessionOut, summary="会话详情")
async def get_session(session_id: str):
    session = await _svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/sessions/{session_id}", summary="停止会话")
async def stop_session(session_id: str):
    session = await _svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await _svc.stop_session(session_id)
    return {"success": True, "message": f"会话 {session_id} 已停止"}


# ──────────────────────────────────────────────
#  手动触发
# ──────────────────────────────────────────────

@router.post("/sessions/{session_id}/trigger", summary="手动触发当日信号")
async def trigger_daily(
    session_id: str,
    date: Optional[str] = Query(default=None, description="指定日期 YYYY-MM-DD，默认今天"),
):
    """
    手动触发当日信号生成（不受15:15限制）。
    可指定历史日期，用于验证回顾。
    """
    session = await _svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.status not in ("running", "paused"):
        raise HTTPException(status_code=400, detail=f"会话状态 {session.status}，无法触发信号")

    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    # 后台执行，立即返回（避免 HTTP 超时）
    asyncio.create_task(_svc.process_daily(session_id, trade_date))
    return {
        "success": True,
        "message": f"日信号处理已在后台启动，date={trade_date}",
        "data": {"session_id": session_id, "date": trade_date},
    }


@router.post("/sessions/{session_id}/rotate", summary="手动触发策略轮换")
async def trigger_rotate(session_id: str):
    """手动触发策略轮换（重新历史验证 + 更新策略）"""
    session = await _svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    asyncio.create_task(_svc.rotate_strategy(session_id))
    return {"success": True, "message": "策略轮换已在后台启动"}


# ──────────────────────────────────────────────
#  查询
# ──────────────────────────────────────────────

@router.get("/sessions/{session_id}/signals", response_model=List[SignalOut], summary="信号历史")
async def get_signals(
    session_id: str,
    date: Optional[str] = Query(default=None, description="按日期过滤 YYYY-MM-DD"),
    limit: int = Query(default=100, description="返回条数上限"),
):
    return await _svc.get_signals(session_id, date=date, limit=limit)


@router.get("/sessions/{session_id}/positions", response_model=List[PositionOut], summary="当前持仓")
async def get_positions(session_id: str):
    return await _svc.get_positions(session_id)


@router.get("/sessions/{session_id}/performance", response_model=PerformanceOut, summary="绩效报告")
async def get_performance(session_id: str):
    perf = await _svc.get_performance(session_id)
    if not perf:
        raise HTTPException(status_code=404, detail="会话不存在")
    return perf


# ──────────────────────────────────────────────
#  独立历史验证
# ──────────────────────────────────────────────

@router.post("/validate", response_model=ValidateOnlyResponse, summary="独立历史验证（不创建会话）")
async def validate_only(body: ValidateOnlyRequest):
    """
    对指定股票列表做历史验证（Walk-Forward），返回每只股票的最优策略。
    - validate_years=5：默认验证近5年，数据不足取全量
    - 不创建会话，不占用资金，纯研究用途
    """
    try:
        results = await _svc.validate_stocks(
            body.stock_codes,
            validate_years=body.validate_years,
            train_ratio=body.train_ratio,
        )
        success = [r for r in results if not r.error]
        summary = (
            f"验证 {len(results)} 只股票：{len(success)} 成功，"
            f"{len(results)-len(success)} 失败。"
            f"平均置信度 {sum(r.confidence for r in success)/len(success):.1f}%"
            if success else "所有股票验证失败"
        )
        return ValidateOnlyResponse(results=results, summary=summary)
    except Exception as e:
        logger.error(f"validate_only error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
#  离线历史模拟（含基准对比）
# ──────────────────────────────────────────────

@router.post("/simulate", response_model=OfflineSimResult, summary="离线历史模拟（含基准对比）")
async def offline_simulate(body: OfflineSimConfig):
    """
    基于历史 K 线做完整离线模拟：

    **流程：**
    1. 训练期（`start_date` 前 `validate_months` 个月）Walk-Forward → 选最优策略
    2. 模拟期（`start_date` ~ `end_date`）逐日回放：信号 → 模拟成交
    3. 与基准指数（沪深300/中证500/恒生指数等）买入持有对比，计算 Alpha

    **基准别名：** `hs300`（沪深300）、`zz500`（中证500）、`hsi`（恒生）、`sz50`（上证50）、`cy`（创业板）

    **返回：** 组合权益曲线、各股明细、基准曲线、Sharpe/回撤/Alpha 等绩效指标
    """
    try:
        result = await _sim_svc.run_simulation(body)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"offline_simulate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
#  多策略前向测试
# ──────────────────────────────────────────────

@router.post("/forward-test", summary="创建多策略前向测试组")
async def create_forward_test(body: ForwardTestCreate):
    """
    一次性为每个 preset 创建独立会话并归入同一测试组：
    - 后台异步完成历史验证（Walk-Forward）→ 自动切换 running
    - 调度器每日 15:15 后统一触发所有 running 会话的信号生成
    - 通过 `GET /forward-test/{group_id}` 查看各策略实时对比绩效

    **presets 可选值：** `defensive`（防守型）、`aggressive`（激进型）
    """
    try:
        group_id = await _svc.create_forward_test(body)
        return {
            "success": True,
            "data": {
                "group_id": group_id,
                "preset_count": len(body.presets),
                "presets": body.presets,
            },
            "message": (
                f"已创建 {len(body.presets)} 个会话（{', '.join(body.presets)}），"
                "历史验证在后台进行，完成后自动切换 running。"
                f"通过 GET /api/v1/auto-trade/forward-test/{group_id} 查看实时对比绩效。"
            ),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"create_forward_test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forward-test", summary="列出所有前向测试组")
async def list_forward_tests():
    """返回所有前向测试组摘要（group_id、名称、会话数、各会话状态）"""
    try:
        groups = await _svc.list_forward_tests()
        return {"success": True, "data": groups, "total": len(groups)}
    except Exception as e:
        logger.error(f"list_forward_tests error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/forward-test/{group_id}",
    response_model=ForwardTestGroupOut,
    summary="查看前向测试组实时对比绩效",
)
async def get_forward_test_compare(group_id: str):
    """
    实时查询测试组中所有 preset 会话的横向对比绩效：
    收益率、胜率、已实现/浮动盈亏、可用资金、最近5条信号。
    每次请求均返回最新数据（无缓存）。
    """
    result = await _svc.get_forward_test_compare(group_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"测试组 {group_id} 不存在")
    return result

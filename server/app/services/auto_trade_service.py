"""
全自动交易引擎 AutoTradeService
────────────────────────────────
功能：
1. 历史验证（5年 Walk-Forward）→ 为每只股票选出最优策略
2. 每个交易日收盘后生成信号 → 执行模拟交易（独立账户）
3. 每30天策略轮换：重新验证，更新 strategy_map
"""

import asyncio
import json
import math
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.auto_trade import (
    AutoTradeSession as SessionModel,
    AutoTradeSignal as SignalModel,
    AutoTradePosition as PositionModel,
)
from app.schemas.auto_trade import (
    AutoTradeSessionCreate,
    AutoTradeSessionOut,
    ForwardTestCreate,
    ForwardTestGroupOut,
    PerformanceOut,
    PositionOut,
    SessionCompareItem,
    SignalOut,
    STRATEGY_PRESETS,
    StrategyInfo,
    ValidateResult,
)
from app.schemas.backtest import BacktestParams
from app.schemas.strategy_test import StrategyTestParams
from app.services.backtest_service import BacktestService
from app.services.strategy_test_service import StrategyTestService
from app.services.strategy_constants import BACKTEST_STRATEGIES
from app.adapters.market.sina_adapter import SinaAdapter

# ── 模拟交易费率（与 TradeService 保持一致）──
COMMISSION_RATE = 0.00025
COMMISSION_MIN = 5.0
STAMP_TAX_RATE = 0.0005
TRANSFER_FEE_RATE = 0.00001
LOT_SIZE = 100


def _calc_fees(action: str, price: float, qty: int) -> float:
    amount = price * qty
    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    stamp_tax = amount * STAMP_TAX_RATE if action == "SELL" else 0.0
    transfer_fee = amount * TRANSFER_FEE_RATE
    return round(commission + stamp_tax + transfer_fee, 2)


def _is_trading_day(dt: datetime) -> bool:
    """简单判断：周一至周五（不含法定节假日，节假日跳过不影响正确性）"""
    return dt.weekday() < 5


# strategy_info 中存储的键与 BACKTEST_STRATEGIES 元组的映射
def _strategy_tuple(name: str) -> Tuple[str, int, int, str]:
    for s, sw, lw, lbl in BACKTEST_STRATEGIES:
        if s == name:
            return s, sw, lw, lbl
    return name, 5, 20, name


def _parse_preset_from_name(session_name: str) -> str:
    """
    从会话名 '{prefix}-{preset_name}' 中解析 preset_name。
    使用 rsplit('-', 1) 只切最后一个连字符，兼容 prefix 中含 '-' 的情况。
    """
    if not session_name or "-" not in session_name:
        return ""
    parts = session_name.rsplit("-", 1)
    return parts[1] if len(parts) == 2 and parts[1] in STRATEGY_PRESETS else ""


class AutoTradeService:

    def __init__(self):
        self.backtest_svc = BacktestService()
        self.strategy_test_svc = StrategyTestService()
        self.market_adapter = SinaAdapter()

    # ══════════════════════════════════════════════════════
    #  会话管理
    # ══════════════════════════════════════════════════════

    async def create_session(self, cfg: AutoTradeSessionCreate) -> str:
        """
        创建会话，若 skip_validate=False 则先做历史验证选策略，
        再切换 status → running 并设置第一个周期日期。
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()
        name = cfg.name or f"AutoSession-{now.strftime('%m%d-%H%M')}"

        # 周期结束日（自然日）
        cycle_end = now + timedelta(days=cfg.cycle_days)

        model = SessionModel(
            id=session_id,
            name=name,
            initial_capital=cfg.initial_capital,
            available_cash=cfg.initial_capital,
            cycle_days=cfg.cycle_days,
            current_cycle=1,
            cycle_start_date=now.strftime("%Y-%m-%d"),
            cycle_end_date=cycle_end.strftime("%Y-%m-%d"),
            validate_years=cfg.validate_years,
            train_ratio=cfg.train_ratio,
            max_position_pct=cfg.max_position_pct,
            stop_loss_pct=cfg.stop_loss_pct,
            take_profit_pct=cfg.take_profit_pct,
            max_hold_days=cfg.max_hold_days,
            min_test_return_pct=cfg.min_test_return_pct,
            market_regime_filter=cfg.market_regime_filter,
            data_scale=cfg.data_scale,
            status="validating",
        )
        model.stock_codes = cfg.stock_codes

        async with AsyncSessionLocal() as session:
            session.add(model)
            await session.commit()

        logger.info(f"[AutoTrader] Session {session_id} created: {cfg.stock_codes}")

        if cfg.skip_validate:
            # 跳过历史验证：使用指定策略或默认第一个策略
            preset = cfg.preset_strategy or BACKTEST_STRATEGIES[0][0]
            s, sw, lw, lbl = _strategy_tuple(preset)
            strategy_map = {
                code: {
                    "strategy": s, "short_window": sw, "long_window": lw,
                    "label": lbl, "confidence": 0.0,
                    "train_return_pct": 0.0, "test_return_pct": 0.0, "test_alpha_pct": 0.0,
                }
                for code in cfg.stock_codes
            }
            await self._update_session(session_id, {
                "strategy_map_json": json.dumps(strategy_map, ensure_ascii=False),
                "status": "running",
            })
        else:
            # 异步历史验证（在后台完成）
            asyncio.create_task(self._validate_and_activate(session_id, cfg.stock_codes,
                                                             cfg.validate_years, cfg.train_ratio))

        return session_id

    async def _validate_and_activate(
        self,
        session_id: str,
        stock_codes: List[str],
        validate_years: float,
        train_ratio: float,
    ):
        """历史验证 → 选出最优策略 → 切换 running"""
        try:
            logger.info(f"[AutoTrader] 开始历史验证 session={session_id} stocks={stock_codes}")
            results = await self._validate_stocks(stock_codes, validate_years, train_ratio)
            strategy_map = {}
            summary = {}
            for r in results:
                if r.error:
                    # 验证失败的股票使用默认策略
                    strategy_map[r.stock_code] = {
                        "strategy": "macd", "short_window": 12, "long_window": 26,
                        "label": "MACD", "confidence": 0.0,
                        "train_return_pct": 0.0, "test_return_pct": 0.0, "test_alpha_pct": 0.0,
                    }
                else:
                    strategy_map[r.stock_code] = {
                        "strategy": r.best_strategy,
                        "short_window": r.__dict__.get("short_window", 0),
                        "long_window": r.__dict__.get("long_window", 0),
                        "label": r.best_strategy_label,
                        "confidence": r.confidence,
                        "train_return_pct": r.train_return_pct,
                        "test_return_pct": r.test_return_pct,
                        "test_alpha_pct": r.test_alpha_pct,
                    }
                summary[r.stock_code] = {
                    "best_strategy": r.best_strategy,
                    "confidence": r.confidence,
                    "error": r.error,
                }
            await self._update_session(session_id, {
                "strategy_map_json": json.dumps(strategy_map, ensure_ascii=False),
                "validate_summary_json": json.dumps(summary, ensure_ascii=False),
                "status": "running",
            })
            logger.info(f"[AutoTrader] 历史验证完成 session={session_id}，切换为 running")
        except Exception as e:
            logger.error(f"[AutoTrader] 历史验证异常 session={session_id}: {e}")
            await self._update_session(session_id, {"status": "running"})

    async def stop_session(self, session_id: str):
        await self._update_session(session_id, {"status": "stopped"})
        logger.info(f"[AutoTrader] Session {session_id} stopped")

    async def get_session(self, session_id: str) -> Optional[AutoTradeSessionOut]:
        async with AsyncSessionLocal() as db:
            model = await db.get(SessionModel, session_id)
            if not model:
                return None
            return self._model_to_out(model)

    async def list_sessions(self) -> List[AutoTradeSessionOut]:
        async with AsyncSessionLocal() as db:
            stmt = select(SessionModel).order_by(SessionModel.created_at.desc())
            rows = (await db.execute(stmt)).scalars().all()
            return [self._model_to_out(r) for r in rows]

    # ══════════════════════════════════════════════════════
    #  多策略前向测试
    # ══════════════════════════════════════════════════════

    async def create_forward_test(self, cfg: ForwardTestCreate) -> str:
        """
        批量创建多 preset 会话，归入同一 group_id。
        每个 preset 独立进行历史验证 + 实盘调度。
        返回 group_id 供后续对比查询。
        """
        group_id = str(uuid.uuid4())
        name_prefix = cfg.name or f"ForwardTest-{datetime.now().strftime('%m%d-%H%M')}"

        for preset_name in cfg.presets:
            session_cfg = AutoTradeSessionCreate(
                preset_name=preset_name,
                name=f"{name_prefix}-{preset_name}",
                stock_codes=cfg.stock_codes,
                initial_capital=cfg.initial_capital,
                validate_years=cfg.validate_years,
                cycle_days=cfg.cycle_days,
                data_scale=cfg.data_scale,
            )
            session_id = await self.create_session(session_cfg)
            # create_session 已 commit，_validate_and_activate 只写 strategy_map/status
            # 安全地回写 group_id
            await self._update_session(session_id, {"group_id": group_id})
            logger.info(f"[ForwardTest] group={group_id} preset={preset_name} session={session_id}")

        return group_id

    async def list_forward_tests(self) -> List[dict]:
        """列出所有前向测试组摘要（按创建时间降序）"""
        async with AsyncSessionLocal() as db:
            stmt = (
                select(SessionModel)
                .where(SessionModel.group_id != "")
                .order_by(SessionModel.created_at.desc())
            )
            rows = (await db.execute(stmt)).scalars().all()

        groups: Dict[str, dict] = {}
        for row in rows:
            gid = row.group_id
            if gid not in groups:
                preset = _parse_preset_from_name(row.name)
                prefix = row.name[:-(len(preset) + 1)] if preset else row.name
                groups[gid] = {
                    "group_id": gid,
                    "name": prefix,
                    "created_at": row.created_at,
                    "session_count": 0,
                    "statuses": [],
                }
            groups[gid]["session_count"] += 1
            groups[gid]["statuses"].append(row.status)

        return list(groups.values())

    async def get_forward_test_compare(self, group_id: str) -> Optional[ForwardTestGroupOut]:
        """查询某测试组所有会话的绩效，汇总为横向对比视图"""
        async with AsyncSessionLocal() as db:
            stmt = (
                select(SessionModel)
                .where(SessionModel.group_id == group_id)
                .order_by(SessionModel.created_at.asc())
            )
            rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            return None

        first = rows[0]
        first_preset = _parse_preset_from_name(first.name)
        group_name = first.name[:-(len(first_preset) + 1)] if first_preset else first.name

        items: List[SessionCompareItem] = []
        for row in rows:
            perf = await self.get_performance(row.id)
            preset_name = _parse_preset_from_name(row.name)
            preset_display = STRATEGY_PRESETS.get(preset_name, {}).get("display_name", preset_name)
            recent = perf.recent_signals[:5] if perf and perf.recent_signals else []
            items.append(SessionCompareItem(
                session_id=row.id,
                preset_name=preset_name,
                preset_display_name=preset_display,
                status=row.status,
                total_return_pct=perf.total_return_pct if perf else 0.0,
                total_trades=perf.total_trades if perf else 0,
                win_rate=perf.win_rate if perf else 0.0,
                realized_profit=perf.realized_profit if perf else 0.0,
                unrealized_profit=perf.unrealized_profit if perf else 0.0,
                available_cash=perf.available_cash if perf else float(row.available_cash),
                market_value=perf.market_value if perf else 0.0,
                recent_signals=recent,
            ))

        return ForwardTestGroupOut(
            group_id=group_id,
            name=group_name,
            created_at=first.created_at,
            sessions=items,
        )

    # ══════════════════════════════════════════════════════
    #  历史验证（供外部调用 & 内部复用）
    # ══════════════════════════════════════════════════════

    async def validate_stocks(
        self,
        stock_codes: List[str],
        validate_years: float = 5.0,
        train_ratio: float = 0.8,
    ) -> List[ValidateResult]:
        return await self._validate_stocks(stock_codes, validate_years, train_ratio)

    async def _validate_stocks(
        self,
        stock_codes: List[str],
        validate_years: float,
        train_ratio: float,
    ) -> List[ValidateResult]:
        results = []
        for code in stock_codes:
            r = await self._validate_one(code, validate_years, train_ratio)
            results.append(r)
        return results

    async def _validate_one(
        self, stock_code: str, validate_years: float, train_ratio: float
    ) -> ValidateResult:
        """
        对单只股票做历史验证：
        - 尝试获取最近 validate_years 年 kline
        - 数据不足时自动取全量
        - 跑 Walk-Forward (80/20)，返回最优策略
        """
        try:
            # 目标 datalen：每年约 250 交易日
            target_bars = int(validate_years * 250) + 100
            kline = []
            for datalen in [target_bars, min(target_bars, 1500), 800, 400]:
                kline = await self.market_adapter.get_kline_data(
                    stock_code, scale=240, datalen=datalen
                )
                if kline and len(kline) >= 60:
                    break

            if not kline or len(kline) < 60:
                return ValidateResult(
                    stock_code=stock_code,
                    best_strategy="macd", best_strategy_label="MACD",
                    confidence=0.0, train_return_pct=0.0,
                    test_return_pct=0.0, test_alpha_pct=0.0,
                    train_period="", test_period="",
                    total_strategies_tested=0, data_bars=len(kline or []),
                    error=f"数据不足 ({len(kline or [])} 条)",
                )

            actual_bars = len(kline)
            start_date = kline[0]["date"][:10]
            end_date = kline[-1]["date"][:10]
            logger.info(f"[AutoTrader] 验证 {stock_code}: {actual_bars} bars [{start_date}~{end_date}]")

            params = StrategyTestParams(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                train_ratio=train_ratio,
                initial_capital=1_000_000.0,
            )
            result = self.strategy_test_svc.run_test_with_kline(params, kline, stock_code)

            if not result or not result.items:
                return ValidateResult(
                    stock_code=stock_code,
                    best_strategy="macd", best_strategy_label="MACD",
                    confidence=0.0, train_return_pct=0.0,
                    test_return_pct=0.0, test_alpha_pct=0.0,
                    train_period=f"{start_date}~{end_date}",
                    test_period="",
                    total_strategies_tested=0, data_bars=actual_bars,
                    error="策略测试无结果",
                )

            best = result.items[0]  # 已按 confidence_score 降序排列
            # 从 BACKTEST_STRATEGIES 找出对应的 short_window / long_window
            sw, lw = 0, 0
            for s, s_w, l_w, lbl in BACKTEST_STRATEGIES:
                if s == best.strategy and lbl == best.strategy_label:
                    sw, lw = s_w, l_w
                    break

            vr = ValidateResult(
                stock_code=stock_code,
                best_strategy=best.strategy,
                best_strategy_label=best.strategy_label,
                confidence=best.confidence_score,
                train_return_pct=best.train_return_pct,
                test_return_pct=best.actual_return_pct,
                test_alpha_pct=best.test_alpha_pct,
                train_period=f"{best.train_start}~{best.train_end}",
                test_period=f"{best.test_start}~{best.test_end}",
                total_strategies_tested=result.total_strategies,
                data_bars=actual_bars,
            )
            # 临时挂上 window 参数供 strategy_map 使用
            vr.__dict__["short_window"] = sw
            vr.__dict__["long_window"] = lw
            return vr

        except Exception as e:
            logger.error(f"[AutoTrader] 验证 {stock_code} 异常: {e}")
            return ValidateResult(
                stock_code=stock_code,
                best_strategy="macd", best_strategy_label="MACD",
                confidence=0.0, train_return_pct=0.0,
                test_return_pct=0.0, test_alpha_pct=0.0,
                train_period="", test_period="",
                total_strategies_tested=0, data_bars=0,
                error=str(e),
            )

    # ══════════════════════════════════════════════════════
    #  每日信号生成 + 模拟执行
    # ══════════════════════════════════════════════════════

    async def process_daily(self, session_id: str, trade_date: Optional[str] = None) -> List[SignalOut]:
        """
        处理当日信号：
        1. 加载会话策略 map
        2. 逐股票生成当日信号
        3. 执行模拟买卖（独立账户）
        4. 写入 auto_trade_signals
        5. 若今日 >= cycle_end_date → 触发策略轮换
        """
        today = trade_date or datetime.now().strftime("%Y-%m-%d")

        # 乐观锁：先写 last_run_date，防止并发重复执行
        async with AsyncSessionLocal() as db:
            model = await db.get(SessionModel, session_id)
            if not model or model.status != "running":
                logger.warning(f"[AutoTrader] process_daily: session {session_id} 不存在或非运行状态")
                return []
            if model.last_run_date == today:
                logger.info(f"[AutoTrader] process_daily: session {session_id} 今日已执行，跳过")
                return []
            model.last_run_date = today
            await db.commit()

        logger.info(f"[AutoTrader] 处理日信号 session={session_id} date={today}")

        strategy_map = json.loads((await self._get_field(session_id, "strategy_map_json")) or "{}")
        stock_codes = json.loads((await self._get_field(session_id, "stock_codes_json")) or "[]")
        available_cash = await self._get_field(session_id, "available_cash")
        initial_capital = await self._get_field(session_id, "initial_capital")
        max_position_pct = await self._get_field(session_id, "max_position_pct")
        stop_loss_pct = float((await self._get_field(session_id, "stop_loss_pct")) or 0.06)
        take_profit_pct = float((await self._get_field(session_id, "take_profit_pct")) or 0.05)
        max_hold_days = int((await self._get_field(session_id, "max_hold_days")) or 15)
        min_test_return_pct = float((await self._get_field(session_id, "min_test_return_pct")) or -1.0)
        mrf = await self._get_field(session_id, "market_regime_filter")
        market_regime_filter = bool(mrf) if mrf is not None else True
        data_scale = int((await self._get_field(session_id, "data_scale")) or 240)

        signals_out: List[SignalOut] = []
        cash = float(available_cash or initial_capital or 1_000_000)
        max_pct = float(max_position_pct or 0.3)

        # 市场环境过滤：一次性检查，所有股票共用
        market_ok = True
        if market_regime_filter:
            market_ok = await self._check_market_regime()

        for code in stock_codes:
            info = strategy_map.get(code, {})
            if not info:
                continue
            # 每只股票之间加小延迟，避免行情接口限速
            if signals_out:
                await asyncio.sleep(0.5)
            sig_out = await self._process_stock_signal(
                session_id, code, info, today, cash,
                float(initial_capital or 1_000_000), max_pct,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_hold_days=max_hold_days,
                min_test_return_pct=min_test_return_pct,
                market_ok=market_ok,
            )
            if sig_out:
                signals_out.append(sig_out)
                if sig_out.signal == "BUY" and sig_out.executed:
                    cash -= sig_out.amount + sig_out.fees
                elif sig_out.signal == "SELL" and sig_out.executed:
                    cash += sig_out.amount - sig_out.fees

        # 更新 available_cash & last_run_date（日K用日期防重）
        await self._update_session(session_id, {
            "available_cash": max(cash, 0.0),
            "last_run_date": today,
        })

        # 检查是否到达周期结束日
        cycle_end = await self._get_field(session_id, "cycle_end_date")
        if cycle_end and today >= cycle_end:
            logger.info(f"[AutoTrader] 周期结束 session={session_id}，触发策略轮换")
            asyncio.create_task(self._rotate_strategy(session_id))

        return signals_out

    async def _check_market_regime(
        self, index_code: str = "sh000300", ma_days: int = 20
    ) -> bool:
        """
        返回 True 表示市场处于上升趋势（指数 >= N日均线），允许新开多仓。
        获取失败时默认返回 True（宽松处理，避免误杀信号）。
        """
        try:
            kline = await self.market_adapter.get_kline_data(
                index_code, scale=240, datalen=ma_days + 10
            )
            if not kline or len(kline) < ma_days:
                return True
            closes = [k["close"] for k in kline]
            ma = sum(closes[-ma_days:]) / ma_days
            current = closes[-1]
            above = current >= ma
            logger.info(
                f"[AutoTrader] 市场环境 {index_code}: 当前{current:.1f} "
                f"MA{ma_days}={ma:.1f} {'↑允许建仓' if above else '↓禁止新仓'}"
            )
            return above
        except Exception as e:
            logger.warning(f"[AutoTrader] 市场环境检测失败: {e}，默认放行")
            return True

    async def _process_stock_signal(
        self,
        session_id: str,
        stock_code: str,
        strategy_info: dict,
        today: str,
        available_cash: float,
        initial_capital: float,
        max_position_pct: float,
        stop_loss_pct: float = 0.06,
        take_profit_pct: float = 0.05,
        max_hold_days: int = 15,
        min_test_return_pct: float = -1.0,
        market_ok: bool = True,
    ) -> Optional[SignalOut]:
        """对单只股票生成信号并执行模拟交易"""
        try:
            strategy = strategy_info.get("strategy", "macd")
            short_w = strategy_info.get("short_window", 0)
            long_w = strategy_info.get("long_window", 0)
            label = strategy_info.get("label", strategy)

            # 获取最新日K（失败重试1次）
            kline = await self.market_adapter.get_kline_data(stock_code, scale=240, datalen=200)
            if not kline or len(kline) < 30:
                await asyncio.sleep(1.0)
                kline = await self.market_adapter.get_kline_data(stock_code, scale=240, datalen=200)
            if not kline or len(kline) < 30:
                logger.warning(f"[AutoTrader] {stock_code} 行情获取失败，跳过")
                return None

            latest_price = kline[-1]["close"]
            signal = self.backtest_svc.get_current_signal(strategy, kline, short_w, long_w)

            # 查当前持仓
            position = await self._get_position(session_id, stock_code)
            holding_qty = position.quantity if position else 0

            qty = 0
            amount = 0.0
            fees = 0.0
            profit = 0.0
            executed = False
            notes = ""

            # ── 修复1：止损检查（优先于策略信号）────────────────
            if holding_qty > 0 and position:
                loss_pct = (latest_price - position.avg_cost) / position.avg_cost
                if loss_pct <= -stop_loss_pct:
                    signal = "SELL"
                    notes = f"[止损] 亏损{loss_pct*100:.1f}%，触发止损阈值{stop_loss_pct*100:.0f}%"
                    logger.info(f"[AutoTrader] {stock_code} {notes}")

            # ── 止盈检查 ──────────────────────────────────────
            if holding_qty > 0 and position and signal != "SELL":
                gain_pct = (latest_price - position.avg_cost) / position.avg_cost
                if gain_pct >= take_profit_pct:
                    signal = "SELL"
                    notes = f"[止盈] 盈利{gain_pct*100:.1f}%，触发止盈阈值{take_profit_pct*100:.0f}%"
                    logger.info(f"[AutoTrader] {stock_code} {notes}")

            # ── 持仓期上限检查 ────────────────────────────────
            if holding_qty > 0 and position and signal != "SELL":
                entry = getattr(position, "entry_date", "") or ""
                if entry:
                    hold_days_actual = (
                        datetime.strptime(today, "%Y-%m-%d") -
                        datetime.strptime(entry, "%Y-%m-%d")
                    ).days
                    if hold_days_actual >= max_hold_days:
                        signal = "SELL"
                        notes = f"[持仓超期] 已持{hold_days_actual}天，超过上限{max_hold_days}天"
                        logger.info(f"[AutoTrader] {stock_code} {notes}")

            # ── 修复2 & 3：建仓前检查验证底线和市场环境 ──────────
            # 用 Alpha（跑赢买入持有）过滤，避免熊市所有策略被绝对收益门槛误杀
            test_alpha = strategy_info.get("test_alpha_pct", 0.0)
            allow_new_position = True
            if signal == "BUY" and holding_qty == 0:
                if test_alpha < min_test_return_pct:
                    allow_new_position = False
                    signal = "HOLD"
                    notes = f"策略验证Alpha{test_alpha:.1f}%低于阈值{min_test_return_pct:.1f}%，暂停建仓"
                elif not market_ok:
                    allow_new_position = False
                    signal = "HOLD"
                    notes = "沪深300低于20日均线，市场下行趋势，暂停建仓"

            if signal == "BUY" and holding_qty == 0 and allow_new_position:
                # 计算最大可买数量
                max_invest = initial_capital * max_position_pct
                max_invest = min(max_invest, available_cash * 0.95)
                raw_qty = int(max_invest / latest_price)
                qty = (raw_qty // LOT_SIZE) * LOT_SIZE
                if qty > 0:
                    amount = round(latest_price * qty, 2)
                    fees = _calc_fees("BUY", latest_price, qty)
                    if available_cash >= amount + fees:
                        await self._update_position(session_id, stock_code, "BUY",
                                                     latest_price, qty, fees, today)
                        executed = True
                        notes = f"买入 {qty} 股 @{latest_price}"
                    else:
                        signal = "HOLD"
                        notes = f"资金不足 (需¥{amount+fees:.0f}，可用¥{available_cash:.0f})"
                else:
                    signal = "HOLD"
                    notes = "可买数量不足100股"

            elif signal == "SELL" and holding_qty > 0:
                qty = holding_qty
                amount = round(latest_price * qty, 2)
                fees = _calc_fees("SELL", latest_price, qty)
                avg_cost = position.avg_cost if position else latest_price
                profit = round((latest_price - avg_cost) * qty - fees, 2)
                await self._update_position(session_id, stock_code, "SELL",
                                             latest_price, qty, fees)
                executed = True
                notes = f"卖出 {qty} 股 @{latest_price}，盈亏¥{profit:.1f}"
            else:
                signal = "HOLD"
                notes = f"持仓{holding_qty}股，无操作"

            sig_model = SignalModel(
                id=str(uuid.uuid4()),
                session_id=session_id,
                date=today,
                stock_code=stock_code,
                strategy=strategy,
                strategy_label=label,
                signal=signal,
                price=latest_price,
                quantity=qty,
                amount=amount,
                fees=fees,
                profit=profit,
                executed=executed,
                notes=notes,
            )
            async with AsyncSessionLocal() as db:
                db.add(sig_model)
                await db.commit()

            logger.info(f"[AutoTrader] {stock_code} {signal} executed={executed} {notes}")

            return SignalOut(
                id=sig_model.id,
                session_id=session_id,
                date=today,
                stock_code=stock_code,
                strategy=strategy,
                strategy_label=label,
                signal=signal,
                price=latest_price,
                quantity=qty,
                amount=amount,
                fees=fees,
                profit=profit,
                executed=executed,
                notes=notes,
            )

        except Exception as e:
            logger.error(f"[AutoTrader] _process_stock_signal {stock_code}: {e}")
            return None

    # ══════════════════════════════════════════════════════
    #  策略轮换（每30天）
    # ══════════════════════════════════════════════════════

    async def rotate_strategy(self, session_id: str):
        """手动触发策略轮换"""
        await self._rotate_strategy(session_id)

    async def _rotate_strategy(self, session_id: str):
        """
        周期末策略轮换：
        1. 重新对所有股票做历史验证
        2. 更新 strategy_map
        3. 开启新周期
        """
        try:
            logger.info(f"[AutoTrader] 策略轮换 session={session_id}")
            stock_codes = json.loads((await self._get_field(session_id, "stock_codes_json")) or "[]")
            validate_years = float((await self._get_field(session_id, "validate_years")) or 5.0)
            train_ratio = float((await self._get_field(session_id, "train_ratio")) or 0.8)
            cycle_days = int((await self._get_field(session_id, "cycle_days")) or 30)
            current_cycle = int((await self._get_field(session_id, "current_cycle")) or 1)

            results = await self._validate_stocks(stock_codes, validate_years, train_ratio)

            strategy_map = {}
            for r in results:
                sw = r.__dict__.get("short_window", 0)
                lw = r.__dict__.get("long_window", 0)
                if r.error:
                    # 保留原策略，不替换
                    orig = json.loads((await self._get_field(session_id, "strategy_map_json")) or "{}")
                    strategy_map[r.stock_code] = orig.get(r.stock_code, {
                        "strategy": "macd", "short_window": 12, "long_window": 26,
                        "label": "MACD", "confidence": 0.0,
                        "train_return_pct": 0.0, "test_return_pct": 0.0, "test_alpha_pct": 0.0,
                    })
                else:
                    strategy_map[r.stock_code] = {
                        "strategy": r.best_strategy,
                        "short_window": sw,
                        "long_window": lw,
                        "label": r.best_strategy_label,
                        "confidence": r.confidence,
                        "train_return_pct": r.train_return_pct,
                        "test_return_pct": r.test_return_pct,
                        "test_alpha_pct": r.test_alpha_pct,
                    }

            now = datetime.now()
            new_cycle_end = now + timedelta(days=cycle_days)
            await self._update_session(session_id, {
                "strategy_map_json": json.dumps(strategy_map, ensure_ascii=False),
                "current_cycle": current_cycle + 1,
                "cycle_start_date": now.strftime("%Y-%m-%d"),
                "cycle_end_date": new_cycle_end.strftime("%Y-%m-%d"),
            })
            logger.info(f"[AutoTrader] 策略轮换完成 session={session_id} 进入第{current_cycle+1}轮")

        except Exception as e:
            logger.error(f"[AutoTrader] 策略轮换失败 session={session_id}: {e}")

    # ══════════════════════════════════════════════════════
    #  查询接口
    # ══════════════════════════════════════════════════════

    async def get_signals(
        self,
        session_id: str,
        date: Optional[str] = None,
        limit: int = 100,
    ) -> List[SignalOut]:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(SignalModel)
                .where(SignalModel.session_id == session_id)
                .order_by(SignalModel.created_at.desc())
                .limit(limit)
            )
            if date:
                stmt = stmt.where(SignalModel.date == date)
            rows = (await db.execute(stmt)).scalars().all()
            return [self._signal_to_out(r) for r in rows]

    async def get_positions(self, session_id: str) -> List[PositionOut]:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(PositionModel)
                .where(PositionModel.session_id == session_id)
                .where(PositionModel.quantity > 0)
            )
            rows = (await db.execute(stmt)).scalars().all()

        result = []
        for pos in rows:
            # 获取实时价格
            current_price = pos.avg_cost
            try:
                stocks = await self.market_adapter.get_realtime_data([pos.stock_code])
                if stocks:
                    current_price = stocks[0].get("price", pos.avg_cost)
            except Exception:
                pass
            market_value = round(current_price * pos.quantity, 2)
            cost_total = round(pos.avg_cost * pos.quantity, 2)
            unrealized = round(market_value - cost_total, 2)
            unrealized_pct = round(unrealized / cost_total * 100 if cost_total > 0 else 0.0, 2)
            result.append(PositionOut(
                session_id=session_id,
                stock_code=pos.stock_code,
                stock_name=pos.stock_name,
                quantity=pos.quantity,
                avg_cost=round(pos.avg_cost, 4),
                current_price=current_price,
                market_value=market_value,
                unrealized_profit=unrealized,
                unrealized_profit_pct=unrealized_pct,
                realized_profit=round(pos.realized_profit or 0, 2),
                total_fees=round(pos.total_fees or 0, 2),
            ))
        return result

    async def check_intraday_stops(self, session_id: str) -> List[SignalOut]:
        """
        日内实时止损/止盈/超期检查（不依赖K线，使用实时报价）。
        只产生 SELL 信号，BUY 信号仍在收盘后由 process_daily 处理。
        """
        async with AsyncSessionLocal() as db:
            model = await db.get(SessionModel, session_id)
            if not model or model.status != "running":
                return []

        stop_loss_pct = float((await self._get_field(session_id, "stop_loss_pct")) or 0.06)
        take_profit_pct = float((await self._get_field(session_id, "take_profit_pct")) or 0.05)
        max_hold_days = int((await self._get_field(session_id, "max_hold_days")) or 15)
        available_cash = float((await self._get_field(session_id, "available_cash")) or 0)

        # 获取所有持仓
        async with AsyncSessionLocal() as db:
            stmt = (
                select(PositionModel)
                .where(PositionModel.session_id == session_id)
                .where(PositionModel.quantity > 0)
            )
            positions = (await db.execute(stmt)).scalars().all()

        if not positions:
            return []

        # 批量获取实时报价
        codes = [p.stock_code for p in positions]
        try:
            realtime = await self.market_adapter.get_realtime_data(codes)
            price_map = {r["code"]: r.get("price", 0.0) for r in realtime if r.get("price")}
        except Exception as e:
            logger.warning(f"[AutoTrader] 日内实时报价失败 session={session_id}: {e}")
            return []

        today = datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        signals_out: List[SignalOut] = []
        cash = available_cash

        for pos in positions:
            current_price = price_map.get(pos.stock_code, 0.0)
            if not current_price:
                continue

            sell_reason = ""
            loss_pct = (current_price - pos.avg_cost) / pos.avg_cost

            if loss_pct <= -stop_loss_pct:
                sell_reason = f"[日内止损] 亏损{loss_pct*100:.1f}%，触发{stop_loss_pct*100:.0f}%阈值"
            elif loss_pct >= take_profit_pct:
                sell_reason = f"[日内止盈] 盈利{loss_pct*100:.1f}%，触发{take_profit_pct*100:.0f}%阈值"
            elif pos.entry_date:
                hold_days = (
                    datetime.strptime(today, "%Y-%m-%d") -
                    datetime.strptime(pos.entry_date[:10], "%Y-%m-%d")
                ).days
                if hold_days >= max_hold_days:
                    sell_reason = f"[日内超期] 已持{hold_days}天，上限{max_hold_days}天"

            if not sell_reason:
                continue

            qty = pos.quantity
            amount = round(current_price * qty, 2)
            fees = _calc_fees("SELL", current_price, qty)
            profit = round((current_price - pos.avg_cost) * qty - fees, 2)

            await self._update_position(session_id, pos.stock_code, "SELL", current_price, qty, fees)
            cash += amount - fees

            sig_model = SignalModel(
                id=str(uuid.uuid4()),
                session_id=session_id,
                date=now_str,
                stock_code=pos.stock_code,
                strategy="intraday_stop",
                strategy_label="日内止损/止盈",
                signal="SELL",
                price=current_price,
                quantity=qty,
                amount=amount,
                fees=fees,
                profit=profit,
                executed=True,
                notes=sell_reason,
            )
            async with AsyncSessionLocal() as db:
                db.add(sig_model)
                await db.commit()

            logger.info(f"[AutoTrader] 日内平仓 {pos.stock_code} {sell_reason} profit={profit:.1f}")
            signals_out.append(SignalOut(
                id=sig_model.id, session_id=session_id, date=now_str,
                stock_code=pos.stock_code, strategy="intraday_stop",
                strategy_label="日内止损/止盈", signal="SELL",
                price=current_price, quantity=qty, amount=amount,
                fees=fees, profit=profit, executed=True, notes=sell_reason,
            ))

        if signals_out:
            await self._update_session(session_id, {"available_cash": max(cash, 0.0)})

        return signals_out

    async def get_performance(self, session_id: str) -> Optional[PerformanceOut]:
        async with AsyncSessionLocal() as db:
            model = await db.get(SessionModel, session_id)
            if not model:
                return None

        positions = await self.get_positions(session_id)
        recent_signals = await self.get_signals(session_id, limit=20)

        market_value = sum(p.market_value for p in positions)
        total_asset = float(model.available_cash) + market_value
        total_return = total_asset - float(model.initial_capital)
        total_return_pct = round(total_return / float(model.initial_capital) * 100, 2)

        # 统计交易信息
        async with AsyncSessionLocal() as db:
            stmt = (
                select(SignalModel)
                .where(SignalModel.session_id == session_id)
                .where(SignalModel.executed == True)
            )
            executed_sigs = (await db.execute(stmt)).scalars().all()

        sell_sigs = [s for s in executed_sigs if s.signal == "SELL"]
        win_trades = sum(1 for s in sell_sigs if s.profit > 0)
        total_trades = len(sell_sigs)
        win_rate = round(win_trades / total_trades * 100 if total_trades > 0 else 0.0, 2)
        total_fees = round(sum(s.fees for s in executed_sigs), 2)
        realized_profit = round(sum(s.profit for s in sell_sigs), 2)
        unrealized_profit = round(sum(p.unrealized_profit for p in positions), 2)

        # 剩余天数
        try:
            days_remaining = max(
                0,
                (datetime.strptime(model.cycle_end_date, "%Y-%m-%d") - datetime.now()).days,
            )
        except Exception:
            days_remaining = 0

        return PerformanceOut(
            session_id=session_id,
            status=model.status,
            current_cycle=model.current_cycle,
            cycle_start_date=model.cycle_start_date,
            cycle_end_date=model.cycle_end_date,
            days_remaining=days_remaining,
            initial_capital=float(model.initial_capital),
            current_total_asset=round(total_asset, 2),
            available_cash=round(float(model.available_cash), 2),
            market_value=round(market_value, 2),
            total_return=round(total_return, 2),
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            win_trades=win_trades,
            win_rate=win_rate,
            total_fees=total_fees,
            realized_profit=realized_profit,
            unrealized_profit=unrealized_profit,
            per_stock=positions,
            recent_signals=recent_signals,
        )

    # ══════════════════════════════════════════════════════
    #  内部工具
    # ══════════════════════════════════════════════════════

    async def _get_position(self, session_id: str, stock_code: str) -> Optional[PositionModel]:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(PositionModel)
                .where(PositionModel.session_id == session_id)
                .where(PositionModel.stock_code == stock_code)
            )
            return (await db.execute(stmt)).scalar_one_or_none()

    async def _update_position(
        self,
        session_id: str,
        stock_code: str,
        action: str,
        price: float,
        qty: int,
        fees: float,
        trade_date: str = "",
    ):
        async with AsyncSessionLocal() as db:
            stmt = (
                select(PositionModel)
                .where(PositionModel.session_id == session_id)
                .where(PositionModel.stock_code == stock_code)
            )
            pos = (await db.execute(stmt)).scalar_one_or_none()

            if action == "BUY":
                cost_with_fee = (price * qty + fees) / qty
                if pos:
                    old_total = pos.avg_cost * pos.quantity
                    new_total = cost_with_fee * qty
                    pos.quantity += qty
                    pos.avg_cost = (old_total + new_total) / pos.quantity
                    pos.total_fees = (pos.total_fees or 0) + fees
                    if not pos.entry_date and trade_date:
                        pos.entry_date = trade_date
                else:
                    pos = PositionModel(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        stock_code=stock_code,
                        quantity=qty,
                        avg_cost=cost_with_fee,
                        entry_date=trade_date,
                        total_fees=fees,
                        realized_profit=0.0,
                    )
                    db.add(pos)
            elif action == "SELL" and pos:
                sell_revenue = price * qty - fees
                cost_basis = pos.avg_cost * qty
                realized = sell_revenue - cost_basis
                pos.quantity -= qty
                pos.total_fees = (pos.total_fees or 0) + fees
                pos.realized_profit = (pos.realized_profit or 0) + realized

            await db.commit()

    async def _update_session(self, session_id: str, fields: dict):
        async with AsyncSessionLocal() as db:
            model = await db.get(SessionModel, session_id)
            if model:
                for k, v in fields.items():
                    setattr(model, k, v)
                model.updated_at = datetime.now()
                await db.commit()

    async def _get_field(self, session_id: str, field: str):
        async with AsyncSessionLocal() as db:
            model = await db.get(SessionModel, session_id)
            return getattr(model, field, None) if model else None

    @staticmethod
    def _model_to_out(model: SessionModel) -> AutoTradeSessionOut:
        return AutoTradeSessionOut(
            id=model.id,
            name=model.name or "",
            status=model.status,
            stock_codes=model.stock_codes,
            initial_capital=model.initial_capital,
            available_cash=model.available_cash,
            cycle_days=model.cycle_days,
            current_cycle=model.current_cycle,
            cycle_start_date=model.cycle_start_date or "",
            cycle_end_date=model.cycle_end_date or "",
            validate_years=model.validate_years,
            max_position_pct=model.max_position_pct,
            data_scale=getattr(model, "data_scale", 240) or 240,
            strategy_map=model.strategy_map,
            last_run_date=model.last_run_date or "",
            created_at=model.created_at,
        )

    @staticmethod
    def _signal_to_out(model: SignalModel) -> SignalOut:
        return SignalOut(
            id=model.id,
            session_id=model.session_id,
            date=model.date,
            stock_code=model.stock_code,
            strategy=model.strategy or "",
            strategy_label=model.strategy_label or "",
            signal=model.signal,
            price=model.price,
            quantity=model.quantity,
            amount=model.amount,
            fees=model.fees,
            profit=model.profit,
            executed=model.executed,
            notes=model.notes or "",
            created_at=model.created_at,
        )

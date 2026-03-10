"""
全自动交易调度器（asyncio 实现，无额外依赖）
────────────────────────────────────────────
双模式触发：
1. 日内实时止损/止盈（9:30-15:00，每5分钟）
   - 用实时报价检查所有持仓
   - 触及止损/止盈/超期 → 立即平仓
2. 收盘后策略信号（15:15 后，当日只执行一次）
   - 用日K生成 BUY/SELL 策略信号
"""

import asyncio
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.services.auto_trade_service import AutoTradeService
from app.services.email_service import send_daily_report


class AutoScheduler:

    def __init__(self):
        self.service = AutoTradeService()
        self._running = False
        self._task: asyncio.Task = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[AutoScheduler] 调度器已启动（每5分钟轮询）")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[AutoScheduler] 调度器已停止")

    async def _loop(self):
        await asyncio.sleep(2)
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AutoScheduler] 调度异常: {e}")
            await asyncio.sleep(300)  # 每5分钟

    async def _tick(self):
        now = datetime.now()
        if not self._is_trading_day(now):
            return

        try:
            sessions = await self.service.list_sessions()
        except Exception as e:
            logger.warning(f"[AutoScheduler] list_sessions 失败: {e}")
            return

        running = [s for s in sessions if s.status == "running"]
        if not running:
            return

        total_min = now.hour * 60 + now.minute
        in_trading = 9 * 60 + 30 <= total_min <= 15 * 60
        after_close = now.hour > 15 or (now.hour == 15 and now.minute >= 15)
        today = now.strftime("%Y-%m-%d")

        eod_pending = []  # 收集需要跑 EOD 的会话
        for session in running:
            # ── 日内实时止损/止盈（9:30-15:00）────────────────────
            if in_trading:
                asyncio.create_task(self._run_intraday_stops(session.id))

            # ── 收盘后日K策略信号（15:15 后，当日唯一）────────────
            if after_close and session.last_run_date != today:
                logger.info(
                    f"[AutoScheduler] 触发收盘信号 session={session.id} ({session.name}) date={today}"
                )
                eod_pending.append(session)

        if eod_pending:
            asyncio.create_task(self._run_eod_and_notify(eod_pending, today))

    async def _run_intraday_stops(self, session_id: str):
        try:
            signals = await self.service.check_intraday_stops(session_id)
            if signals:
                logger.info(
                    f"[AutoScheduler] 日内平仓 session={session_id}: "
                    f"{len(signals)} 笔 ({', '.join(s.stock_code for s in signals)})"
                )
        except Exception as e:
            logger.error(f"[AutoScheduler] 日内止损检查失败 session={session_id}: {e}")

    async def _run_eod_and_notify(self, eod_sessions, today: str):
        """依次执行需要 EOD 的会话，全部完成后汇总所有 running 会话绩效发邮件"""
        # 1. 执行 EOD 信号
        for session in eod_sessions:
            try:
                signals = await self.service.process_daily(session.id, today)
                executed = [s for s in signals if s.executed]
                buys  = [s for s in executed if s.signal == "BUY"]
                sells = [s for s in executed if s.signal == "SELL"]
                logger.info(
                    f"[AutoScheduler] session={session.id} 完成 {today}："
                    f"{len(signals)}条信号，买{len(buys)}笔 卖{len(sells)}笔"
                )
            except Exception as e:
                logger.error(f"[AutoScheduler] session={session.id} 执行失败: {e}")

        # 2. 汇总所有 running 会话的绩效（不只是今天跑过的）
        if not settings.EMAIL_ENABLED:
            return
        try:
            all_sessions = await self.service.list_sessions()
            running = [s for s in all_sessions if s.status == "running"]
        except Exception as e:
            logger.warning(f"[AutoScheduler] 邮件报告: list_sessions 失败: {e}")
            return

        session_reports = []
        for session in running:
            try:
                perf = await self.service.get_performance(session.id)
                # 取今日已执行信号
                from app.services.auto_trade_service import AutoTradeService as _Svc
                all_sigs = await self.service.get_signals(session.id, date=today, limit=50)
                today_sigs = [
                    {"date": s.date, "stock_code": s.stock_code, "signal": s.signal,
                     "price": s.price, "quantity": s.quantity, "profit": s.profit}
                    for s in all_sigs if s.executed
                ]
                session_reports.append({
                    "name": session.name,
                    "status": session.status,
                    "total_return_pct": perf.total_return_pct if perf else 0.0,
                    "total_trades": perf.total_trades if perf else 0,
                    "win_rate": perf.win_rate if perf else 0.0,
                    "realized_profit": perf.realized_profit if perf else 0.0,
                    "available_cash": perf.available_cash if perf else float(session.available_cash),
                    "today_signals": today_sigs,
                })
            except Exception as e:
                logger.error(f"[AutoScheduler] 邮件报告: session={session.id} 绩效获取失败: {e}")

        if session_reports:
            report = {"date": today, "sessions": session_reports}
            await send_daily_report(report)

    async def _run_session(self, session_id: str, today: str):
        try:
            signals = await self.service.process_daily(session_id, today)
            executed = [s for s in signals if s.executed]
            buys  = [s for s in executed if s.signal == "BUY"]
            sells = [s for s in executed if s.signal == "SELL"]
            logger.info(
                f"[AutoScheduler] session={session_id} 完成 {today}："
                f"{len(signals)}条信号，买{len(buys)}笔 卖{len(sells)}笔"
            )
        except Exception as e:
            logger.error(f"[AutoScheduler] session={session_id} 执行失败: {e}")

    @staticmethod
    def _is_trading_day(dt: datetime) -> bool:
        return dt.weekday() < 5


# 全局单例
_scheduler: AutoScheduler = None


def get_scheduler() -> AutoScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutoScheduler()
    return _scheduler

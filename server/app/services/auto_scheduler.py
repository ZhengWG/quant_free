"""
全自动交易调度器（asyncio 实现，无额外依赖）
────────────────────────────────────────────
行为：
- 服务启动时立即检查一次（补跑当天已错过的信号）
- 之后每5分钟检查一次
- 交易日 15:15 以后才执行当日信号
- 同一天同一会话只执行一次（last_run_date 防重）
"""

import asyncio
from datetime import datetime
from loguru import logger

from app.services.auto_trade_service import AutoTradeService


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
        logger.info("[AutoScheduler] 调度器已启动（每5分钟轮询，启动时立即检查一次）")

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
        # 启动后先等2秒让服务完全就绪，再立即检查一次（补跑）
        await asyncio.sleep(2)
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AutoScheduler] 调度异常: {e}")
            await asyncio.sleep(300)  # 每5分钟检查一次

    async def _tick(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 只在交易日（周一~周五）15:15 以后执行
        if not self._is_trading_day(now):
            return
        if now.hour < 15 or (now.hour == 15 and now.minute < 15):
            return

        # 查询所有 running 状态的会话
        try:
            sessions = await self.service.list_sessions()
        except Exception as e:
            logger.warning(f"[AutoScheduler] list_sessions 失败: {e}")
            return

        running = [s for s in sessions if s.status == "running"]
        if not running:
            return

        for session in running:
            # 同一天已执行过，跳过
            if session.last_run_date == today:
                continue
            logger.info(f"[AutoScheduler] 触发日信号 session={session.id} ({session.name}) date={today}")
            asyncio.create_task(self._run_session(session.id, today))

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
        """周一~周五（法定节假日当天无价格变动，信号不触发，影响极小）"""
        return dt.weekday() < 5


# 全局单例
_scheduler: AutoScheduler = None


def get_scheduler() -> AutoScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutoScheduler()
    return _scheduler

"""
每日交易建议服务（Phase 2）
──────────────────────────
每个交易日跑一遍全市场 smart-screen，并与历史推荐对账，输出带**延续性**的建议：
  - holding : 昨日推荐今日仍在前列 → 保留首推日/参考价，累计收益
  - new     : 今日新进 Top-N
  - exit    : 触止损 / 信号转看跌 / 连续掉出榜单（滞后阈值防抖）

依赖：ScreeningService.run_smart_screen（复用现有多策略回测 + 估值 + AI 基本面）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.models.recommendation import RecommendationHistory
from app.adapters.market.sina_adapter import SinaAdapter
from app.schemas.screening import SmartScreenParams
from app.services.screening_service import ScreeningService


class DailyAdviceService:
    # 延续性护栏
    MISS_THRESHOLD = 2          # 连续掉出榜单达到此次数才 exit
    DEFAULT_STOP_PCT = 0.08     # 新推荐默认止损 8%
    DEFAULT_TARGET_PCT = 10.0   # 无预测收益时的默认目标 +10%

    def __init__(self):
        self.screening = ScreeningService()
        self.adapter = SinaAdapter()

    # ------------------------------------------------------------------
    # 代码规范化：跨市场统一匹配键（消除 hk00700 / 00700 / AAPL 格式差异）
    # ------------------------------------------------------------------
    def _canon(self, code: str) -> str:
        n = self.adapter._normalize_code(code)
        if n.startswith(("sh", "sz")):
            return n[2:]
        if n.startswith("hk"):
            return n[2:]
        if n.startswith("gb_"):
            return n[3:].upper()
        return n.upper()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    async def generate(
        self,
        run_date: Optional[str] = None,
        pool: str = "hs_and_hk",
        top_n: int = 5,
        mode: str = "smart_v2",
        lookback_days: int = 730,
    ) -> dict:
        run_date = run_date or datetime.now().strftime("%Y-%m-%d")
        end_date = run_date
        start_date = (
            datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")

        logger.info(f"[DailyAdvice] generate date={run_date} pool={pool} top_n={top_n} mode={mode}")

        # 1) 跑 smart-screen（放宽 top_n 以便对账延续性）
        broad_top = max(top_n * 3, 15)
        params = SmartScreenParams(
            stock_pool=pool, start_date=start_date, end_date=end_date,
            top_n=broad_top, mode=mode,
        )
        screen = await self.screening.run_smart_screen(params)
        rankings = screen.rankings or []
        rank_map = {self._canon(r.stock_code): r for r in rankings}
        today_top = [self._canon(r.stock_code) for r in rankings[:top_n]]
        logger.info(f"[DailyAdvice] screen 得 {len(rankings)} 条，Top-{top_n}={today_top}")

        # 2) 加载昨日（及更早）仍活跃的推荐
        prior_map = await self._load_prior_active(run_date)

        # 3) 批量取现价（活跃 + 今日 Top-N 的并集）
        price_map = await self._fetch_prices(prior_map, rankings, top_n)

        # 4) 对账
        holding, new, exit_ = [], [], []
        handled = set()

        for canon, prow in prior_map.items():
            rr = rank_map.get(canon)
            cur = price_map.get(canon) or prow.current_price or prow.entry_ref_price
            entry = prow.entry_ref_price or cur
            ret = (cur - entry) / entry * 100 if entry else 0.0
            days = self._days_between(prow.first_recommended_date, run_date)
            sig = (rr.signal if rr and rr.signal else prow.signal) or ""

            stop_hit = prow.stop_loss > 0 and cur <= prow.stop_loss
            reversed_sig = "看跌" in sig
            in_top = canon in today_top
            in_rank = canon in rank_map

            status, reason, miss = "holding", "", prow.miss_count
            if stop_hit or reversed_sig:
                status = "exit"
                reason = "触及止损" if stop_hit else "信号转看跌"
            elif in_top:
                miss = 0
            elif in_rank:
                miss = prow.miss_count + 1
                if miss >= self.MISS_THRESHOLD:
                    status, reason = "exit", "连续掉出前列"
            else:
                miss = prow.miss_count + 1
                if miss >= self.MISS_THRESHOLD:
                    status, reason = "exit", "连续掉出榜单"

            row = self._build_row(
                run_date=run_date, canon=canon, rr=rr, prior=prow,
                cur_price=cur, entry_ref=entry, ret=ret, days=days,
                status=status, miss=miss, exit_reason=reason, sig=sig,
            )
            (exit_ if status == "exit" else holding).append(row)
            handled.add(canon)

        # 5) 新推荐：今日 Top-N 中未被处理的
        for canon in today_top:
            if canon in handled:
                continue
            rr = rank_map[canon]
            cur = price_map.get(canon) or self._rr_last_close(rr) or 0.0
            if cur <= 0:
                continue
            row = self._build_row(
                run_date=run_date, canon=canon, rr=rr, prior=None,
                cur_price=cur, entry_ref=cur, ret=0.0, days=0,
                status="new", miss=0, exit_reason="", sig=rr.signal or "",
            )
            new.append(row)
            handled.add(canon)

        # 6) 落库（先删同日旧数据，保证可重复运行）
        await self._persist(run_date, holding + new + exit_)

        report = {
            "date": run_date, "pool": pool, "mode": mode, "top_n": top_n,
            "holding": holding, "new": new, "exit": exit_,
            "counts": {"holding": len(holding), "new": len(new), "exit": len(exit_)},
        }
        logger.info(f"[DailyAdvice] 完成: holding={len(holding)} new={len(new)} exit={len(exit_)}")
        return report

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    async def _load_prior_active(self, run_date: str) -> Dict[str, RecommendationHistory]:
        """取 run_date 之前最近一个快照日、且状态为 new/holding 的推荐，键为 canon。"""
        async with AsyncSessionLocal() as db:
            # 最近的历史快照日期（严格早于 run_date）
            latest = (
                await db.execute(
                    select(RecommendationHistory.date)
                    .where(RecommendationHistory.date < run_date)
                    .order_by(RecommendationHistory.date.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not latest:
                return {}
            rows = (
                await db.execute(
                    select(RecommendationHistory).where(
                        RecommendationHistory.date == latest,
                        RecommendationHistory.status.in_(["new", "holding"]),
                    )
                )
            ).scalars().all()
        return {self._canon(r.stock_code): r for r in rows}

    async def _fetch_prices(self, prior_map, rankings, top_n) -> Dict[str, float]:
        codes = [r.stock_code for r in prior_map.values()]
        codes += [r.stock_code for r in rankings[:top_n]]
        codes = list({c for c in codes if c})
        if not codes:
            return {}
        try:
            raw = await self.adapter.get_realtime_data(codes)
        except Exception as e:
            logger.warning(f"[DailyAdvice] 取现价失败: {e}")
            return {}
        out = {}
        for item in raw:
            price = item.get("price") or 0.0
            if price > 0:
                out[self._canon(item.get("code", ""))] = float(price)
        return out

    def _rr_last_close(self, rr) -> Optional[float]:
        series = getattr(rr, "full_price_series", None)
        if series:
            try:
                return float(series[-1].get("close"))
            except Exception:
                pass
        return None

    def _days_between(self, d0: str, d1: str) -> int:
        try:
            return (datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d0, "%Y-%m-%d")).days
        except Exception:
            return 0

    def _build_row(self, run_date, canon, rr, prior, cur_price, entry_ref,
                   ret, days, status, miss, exit_reason, sig) -> dict:
        """构造一行推荐记录（dict，供落库 + 邮件）。rr 可能为空（掉榜的持有股）。"""
        first_rec = (prior.first_recommended_date if prior else run_date) or run_date
        stop = prior.stop_loss if prior else round(entry_ref * (1 - self.DEFAULT_STOP_PCT), 3)

        # 目标价：优先用预测收益，其次默认
        pred = getattr(rr, "predicted_return_pct", None) if rr else (prior.predicted_return_pct if prior else None)
        pred = pred if pred is not None else self.DEFAULT_TARGET_PCT
        target = prior.target_price if prior else round(entry_ref * (1 + max(pred, 0) / 100), 3)

        def pick(attr, default=None):
            if rr is not None and getattr(rr, attr, None) is not None:
                return getattr(rr, attr)
            if prior is not None:
                return getattr(prior, {"strategy_label": "strategy_label",
                                        "confidence_score": "confidence",
                                        "score": "composite_score",
                                        "ai_analysis": "ai_comment"}.get(attr, attr), default)
            return default

        return {
            "id": str(uuid.uuid4()),
            "date": run_date,
            "market": self.adapter._market_of(rr.stock_code if rr else prior.stock_code),
            "stock_code": rr.stock_code if rr else prior.stock_code,
            "stock_name": (rr.stock_name if rr else prior.stock_name) or "",
            "strategy": (rr.strategy if rr else prior.strategy) or "",
            "strategy_label": (rr.strategy_label if rr else prior.strategy_label) or "",
            "signal": sig,
            "entry_ref_price": round(entry_ref, 3),
            "current_price": round(cur_price, 3),
            "target_price": target,
            "stop_loss": stop,
            "confidence": float(pick("confidence_score", 0.0) or 0.0),
            "composite_score": float(pick("score", 0.0) or 0.0),
            "predicted_return_pct": float(pred or 0.0),
            "pe": getattr(rr, "pe", None) if rr else (prior.pe if prior else None),
            "pb": getattr(rr, "pb", None) if rr else (prior.pb if prior else None),
            "roe": getattr(rr, "roe", None) if rr else (prior.roe if prior else None),
            "ai_comment": (getattr(rr, "ai_analysis", None) if rr else prior.ai_comment) or "",
            "status": status,
            "first_recommended_date": first_rec,
            "days_held": days,
            "return_since_rec_pct": round(ret, 2),
            "miss_count": miss,
            "exit_reason": exit_reason,
        }

    async def _persist(self, run_date: str, rows: List[dict]):
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(RecommendationHistory).where(RecommendationHistory.date == run_date)
            )
            for r in rows:
                db.add(RecommendationHistory(
                    id=r["id"], date=r["date"], market=r["market"],
                    stock_code=r["stock_code"], stock_name=r["stock_name"],
                    strategy=r["strategy"], strategy_label=r["strategy_label"], signal=r["signal"],
                    entry_ref_price=r["entry_ref_price"], current_price=r["current_price"],
                    target_price=r["target_price"], stop_loss=r["stop_loss"],
                    confidence=r["confidence"], composite_score=r["composite_score"],
                    predicted_return_pct=r["predicted_return_pct"],
                    pe=r["pe"], pb=r["pb"], roe=r["roe"], ai_comment=r["ai_comment"],
                    status=r["status"], first_recommended_date=r["first_recommended_date"],
                    days_held=r["days_held"], return_since_rec_pct=r["return_since_rec_pct"],
                    miss_count=r["miss_count"], exit_reason=r["exit_reason"],
                ))
            await db.commit()

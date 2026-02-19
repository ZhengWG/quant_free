"""
策略测试服务（Walk-Forward Validation）v2
改进：
- CAGR 复合增长率预测（替代线性外推）
- 买入持有基准线 + Alpha 超额收益
- 策略测试专用参数（比默认更激进）
- 基于 Alpha + 一致性 的置信度评分
"""

import math
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from loguru import logger

from app.schemas.backtest import BacktestParams
from app.schemas.strategy_test import (
    StrategyTestParams, StrategyTestResult, StrategyTestItem, ProjectedPoint,
)
from app.services.backtest_service import BacktestService
from app.adapters.market.sina_adapter import SinaAdapter
from app.services.strategy_constants import BACKTEST_STRATEGIES


class StrategyTestService:

    def __init__(self):
        self.adapter = SinaAdapter()
        self.backtest_service = BacktestService()

    # ====================================================================

    async def run_test(self, params: StrategyTestParams) -> StrategyTestResult:
        start_ts = time.time()

        d_start = datetime.strptime(params.start_date, "%Y-%m-%d")
        d_end = datetime.strptime(params.end_date, "%Y-%m-%d")
        total_days = (d_end - d_start).days

        # 尝试不同 datalen 获取 kline，从大到小
        kline = []
        for datalen in [
            max(600, int(total_days * 0.8) + 300),
            min(1000, max(400, int(total_days * 0.6) + 100)),
            500,
            300,
        ]:
            kline = await self.adapter.get_kline_data(
                params.stock_code, scale=240, datalen=datalen
            )
            if kline and len(kline) >= 40:
                break
            logger.warning(f"[StrategyTest] {params.stock_code}: datalen={datalen} got {len(kline or [])} bars, retrying...")

        if not kline or len(kline) < 40:
            raise ValueError(
                f"K线数据不足: {params.stock_code}，仅获取到 {len(kline or [])} 条。"
                f"请检查股票代码是否正确（A股直接输入数字如600519，港股加HK前缀如HK00700）"
            )

        logger.info(f"[StrategyTest] {params.stock_code}: fetched {len(kline)} bars, "
                     f"range {kline[0]['date'][:10]} ~ {kline[-1]['date'][:10]}")

        name = params.stock_code
        try:
            stocks = await self.adapter.get_realtime_data([params.stock_code])
            if stocks:
                name = stocks[0].get("name", name)
        except Exception:
            pass

        filtered = [k for k in kline if params.start_date <= k["date"][:10] <= params.end_date]

        # 如果选定区间内数据不足，自动使用全部可用数据
        if len(filtered) < 40 and len(kline) >= 40:
            logger.warning(f"[StrategyTest] filtered only {len(filtered)} bars in [{params.start_date}, {params.end_date}], "
                           f"auto-adjusting to full kline range")
            filtered = kline
            params = StrategyTestParams(
                stock_code=params.stock_code,
                start_date=kline[0]["date"][:10],
                end_date=kline[-1]["date"][:10],
                initial_capital=params.initial_capital,
                train_ratio=params.train_ratio,
            )

        logger.info(f"[StrategyTest] filtered bars: {len(filtered)}")
        if len(filtered) < 40:
            raise ValueError(
                f"K线数据不足: {params.stock_code} 在 {params.start_date}~{params.end_date} 区间仅有 {len(filtered)} 条数据"
            )

        split_idx = int(len(filtered) * params.train_ratio)
        if split_idx < 20 or len(filtered) - split_idx < 5:
            raise ValueError("区间太短，无法有效拆分训练/测试集")

        train_kline = filtered[:split_idx]
        test_kline = filtered[split_idx:]

        train_start = train_kline[0]["date"][:10]
        train_end = train_kline[-1]["date"][:10]
        test_start = test_kline[0]["date"][:10]
        test_end = test_kline[-1]["date"][:10]

        train_bars = len(train_kline)
        test_bars = len(test_kline)

        logger.info(f"[StrategyTest] train {train_start}~{train_end} ({train_bars} bars), "
                     f"test {test_start}~{test_end} ({test_bars} bars)")

        # 买入持有基准
        train_bnh = self._bnh_return(train_kline)
        test_bnh = self._bnh_return(test_kline)
        full_bnh = self._bnh_return(filtered)

        # 价格序列
        price_series = self._sample_price_series(filtered)

        # 策略测试
        items: List[StrategyTestItem] = []
        for strategy, short_w, long_w, label in BACKTEST_STRATEGIES:
            item = self._test_one_strategy(
                params, strategy, short_w, long_w, label,
                kline, train_kline, test_kline,
                train_start, train_end, test_start, test_end,
                train_bars, test_bars,
                train_bnh, test_bnh, price_series,
            )
            if item is not None:
                items.append(item)

        items.sort(key=lambda x: x.confidence_score, reverse=True)
        avg_conf = sum(it.confidence_score for it in items) / len(items) if items else 0
        best = items[0] if items else None

        elapsed = round(time.time() - start_ts, 2)
        logger.info(f"[StrategyTest] done: {len(items)} strategies, avg_conf={avg_conf:.1f}, "
                     f"full_bnh={full_bnh:.2f}%, elapsed={elapsed}s")

        return StrategyTestResult(
            stock_code=params.stock_code,
            stock_name=name,
            full_start=params.start_date,
            full_end=params.end_date,
            train_ratio=params.train_ratio,
            total_strategies=len(items),
            avg_confidence=round(avg_conf, 1),
            best_strategy=best.strategy if best else "",
            best_strategy_label=best.strategy_label if best else "",
            full_bnh_pct=round(full_bnh, 2),
            test_bnh_pct=round(test_bnh, 2),
            time_taken_seconds=elapsed,
            items=items,
        )

    def run_test_with_kline(
        self,
        params: StrategyTestParams,
        kline: list,
        stock_name: str,
    ) -> Optional[StrategyTestResult]:
        """
        使用已有 K 线执行策略测试（与 run_test 逻辑一致，供智能选股等复用）。
        同步方法，无网络 IO。
        """
        if not kline or len(kline) < 40:
            return None
        start_ts = time.time()
        filtered = [k for k in kline if params.start_date <= k["date"][:10] <= params.end_date]
        if len(filtered) < 40 and len(kline) >= 40:
            filtered = kline
        split_idx = int(len(filtered) * params.train_ratio)
        if split_idx < 20 or len(filtered) - split_idx < 5:
            return None
        train_kline = filtered[:split_idx]
        test_kline = filtered[split_idx:]
        train_start = train_kline[0]["date"][:10]
        train_end = train_kline[-1]["date"][:10]
        test_start = test_kline[0]["date"][:10]
        test_end = test_kline[-1]["date"][:10]
        train_bars = len(train_kline)
        test_bars = len(test_kline)
        train_bnh = self._bnh_return(train_kline)
        test_bnh = self._bnh_return(test_kline)
        full_bnh = self._bnh_return(filtered)
        price_series = self._sample_price_series(filtered)
        items: List[StrategyTestItem] = []
        for strategy, short_w, long_w, label in BACKTEST_STRATEGIES:
            item = self._test_one_strategy(
                params, strategy, short_w, long_w, label,
                kline, train_kline, test_kline,
                train_start, train_end, test_start, test_end,
                train_bars, test_bars,
                train_bnh, test_bnh, price_series,
            )
            if item is not None:
                items.append(item)
        if not items:
            return None
        items.sort(key=lambda x: x.confidence_score, reverse=True)
        avg_conf = sum(it.confidence_score for it in items) / len(items)
        best = items[0]
        elapsed = round(time.time() - start_ts, 2)
        return StrategyTestResult(
            stock_code=params.stock_code,
            stock_name=stock_name,
            full_start=filtered[0]["date"][:10],
            full_end=filtered[-1]["date"][:10],
            train_ratio=params.train_ratio,
            total_strategies=len(items),
            avg_confidence=round(avg_conf, 1),
            best_strategy=best.strategy,
            best_strategy_label=best.strategy_label,
            full_bnh_pct=round(full_bnh, 2),
            test_bnh_pct=round(test_bnh, 2),
            time_taken_seconds=elapsed,
            items=items,
        )

    # ====================================================================

    def _test_one_strategy(
        self, params, strategy, short_w, long_w, label,
        kline, train_kline, test_kline,
        train_start, train_end, test_start, test_end,
        train_bars, test_bars,
        train_bnh, test_bnh, price_series,
    ) -> Optional[StrategyTestItem]:

        # 策略测试专用参数：比默认更激进，更多交易，更少过滤
        common = dict(
            stock_code=params.stock_code,
            strategy=strategy,
            initial_capital=params.initial_capital,
            short_window=short_w,
            long_window=long_w,
            risk_per_trade=0.08,        # 8% (default 4%)
            max_position_pct=0.95,
            stop_loss_pct=0.10,         # 10% (default 7%)
            trailing_stop_pct=0.22,     # 22% (default 18%)
            trend_ma_len=20,            # 20 (default 40) — 更灵敏
            cooldown_bars=1,            # 1 (default 2)
        )

        # ---- 训练期 ----
        train_bp = BacktestParams(start_date=train_start, end_date=train_end, **common)
        try:
            train_result = self.backtest_service.run_backtest_sync(train_bp, kline)
        except Exception as e:
            logger.warning(f"[StrategyTest] {label} train exception: {e}")
            return None

        if train_result is None:
            logger.info(f"[StrategyTest] {label}: train returned None")
            return None
        if train_result.total_trades < 1:
            logger.info(f"[StrategyTest] {label}: 0 train trades, skip")
            return None

        logger.info(f"[StrategyTest] {label}: train ret={train_result.total_return_percent:.2f}%, "
                     f"trades={train_result.total_trades}, bnh={train_bnh:.2f}%")

        # ---- 测试期 ----
        test_bp = BacktestParams(start_date=test_start, end_date=test_end, **common)
        try:
            test_result = self.backtest_service.run_backtest_sync(test_bp, kline)
        except Exception as e:
            logger.warning(f"[StrategyTest] {label} test exception: {e}")
            return None

        if test_result is None:
            logger.info(f"[StrategyTest] {label}: test returned None")
            return None

        test_has_trades = test_result.total_trades > 0
        actual_ret = test_result.total_return_percent

        logger.info(f"[StrategyTest] {label}: test ret={actual_ret:.2f}%, "
                     f"trades={test_result.total_trades}, bnh={test_bnh:.2f}%")

        # 测试期无交易 → 用买入持有作为实际表现
        if not test_has_trades:
            actual_ret = test_bnh
            logger.info(f"[StrategyTest] {label}: no test trades, fallback to bnh={actual_ret:.2f}%")

        # ---- 预测：用 CAGR 外推 ----
        predicted_ret = self._predict_return(
            train_result.total_return_percent, train_bars, test_bars
        )

        predicted_dir = self._direction(predicted_ret)
        actual_dir = self._direction(actual_ret)

        # ---- Alpha ----
        train_alpha = train_result.total_return_percent - train_bnh
        test_alpha = actual_ret - test_bnh

        # ---- 置信度评估 ----
        dir_correct = predicted_dir == actual_dir
        ret_error = abs(predicted_ret - actual_ret)

        score = self._calc_confidence(
            predicted_ret, actual_ret, ret_error, dir_correct,
            train_result, test_result,
            train_alpha, test_alpha, test_has_trades,
        )

        # ---- 图表数据 ----
        train_eq = self._build_equity_points(
            train_result, kline, train_start, train_end, params.initial_capital
        )
        last_train_eq = train_eq[-1].value if train_eq else params.initial_capital

        test_eq_pred = self._build_predicted_equity(
            last_train_eq, predicted_ret, test_start, test_bars
        )
        test_eq_actual = self._build_equity_points(
            test_result, kline, test_start, test_end, params.initial_capital
        )
        if test_eq_actual:
            offset = last_train_eq - params.initial_capital
            test_eq_actual = [
                ProjectedPoint(date=p.date, value=round(p.value + offset, 2))
                for p in test_eq_actual
            ]

        # 测试期买入持有权益线
        test_eq_bnh = self._build_bnh_equity(
            test_kline, last_train_eq
        )

        return StrategyTestItem(
            strategy=strategy,
            strategy_label=label,
            train_start=train_start, train_end=train_end,
            test_start=test_start, test_end=test_end,
            train_bars=train_bars, test_bars=test_bars,
            train_return_pct=train_result.total_return_percent,
            train_sharpe=train_result.sharpe_ratio,
            train_max_drawdown=train_result.max_drawdown,
            train_win_rate=train_result.win_rate,
            train_trades=train_result.total_trades,
            train_bnh_pct=round(train_bnh, 2),
            test_bnh_pct=round(test_bnh, 2),
            predicted_return_pct=round(predicted_ret, 2),
            predicted_direction=predicted_dir,
            actual_return_pct=round(actual_ret, 2),
            actual_sharpe=test_result.sharpe_ratio,
            actual_max_drawdown=test_result.max_drawdown,
            actual_win_rate=test_result.win_rate,
            actual_trades=test_result.total_trades,
            actual_direction=actual_dir,
            train_alpha_pct=round(train_alpha, 2),
            test_alpha_pct=round(test_alpha, 2),
            direction_correct=dir_correct,
            return_error_pct=round(ret_error, 2),
            confidence_score=round(score, 1),
            test_has_trades=test_has_trades,
            train_equity=train_eq,
            test_equity_predicted=test_eq_pred,
            test_equity_actual=test_eq_actual,
            test_equity_bnh=test_eq_bnh,
            full_price_series=price_series,
        )

    # ====================================================================
    # 辅助方法
    # ====================================================================

    @staticmethod
    def _bnh_return(kline_segment: list) -> float:
        """买入持有收益率"""
        if len(kline_segment) < 2:
            return 0.0
        c0 = kline_segment[0]["close"]
        c1 = kline_segment[-1]["close"]
        return (c1 - c0) / c0 * 100 if c0 > 0 else 0.0

    @staticmethod
    def _predict_return(train_ret_pct: float, train_bars: int, test_bars: int) -> float:
        """
        用 CAGR 复合增长率从训练期外推测试期收益。
        train_bars / test_bars 是交易日数。
        """
        if train_bars < 5 or test_bars < 1:
            return 0.0
        r = train_ret_pct / 100
        if r <= -1:
            return -100.0
        # 年化收益 → 按交易日复利外推
        cagr_daily = (1 + r) ** (1.0 / train_bars) - 1
        projected = (1 + cagr_daily) ** test_bars - 1
        return projected * 100

    @staticmethod
    def _direction(ret: float) -> str:
        if ret > 3:
            return "看涨"
        if ret < -3:
            return "看跌"
        return "震荡"

    @staticmethod
    def _calc_confidence(
        predicted_ret, actual_ret, ret_error, dir_correct,
        train_result, test_result,
        train_alpha, test_alpha, test_has_trades,
    ) -> float:
        score = 0.0

        # (1) 方向准确 — 25 分
        if dir_correct:
            score += 25
        elif (predicted_ret >= 0 and actual_ret >= 0) or (predicted_ret < 0 and actual_ret < 0):
            score += 12

        # (2) 收益误差 — 25 分（误差 0% → 25, 误差 30%+ → 0）
        score += max(0.0, 25 - ret_error * 0.83)

        # (3) Alpha 一致性 — 20 分
        #     训练期和测试期 Alpha 同号 → 策略一致跑赢/跑输大盘
        if train_alpha >= 0 and test_alpha >= 0:
            score += 20
        elif train_alpha < 0 and test_alpha < 0:
            score += 10  # 一致跑输也算一致
        elif abs(train_alpha) < 3 and abs(test_alpha) < 3:
            score += 8   # 都很接近大盘

        # (4) 训练期质量 — 15 分
        if train_result.sharpe_ratio > 1.5:
            score += 10
        elif train_result.sharpe_ratio > 0.5:
            score += 6
        elif train_result.sharpe_ratio > 0:
            score += 3
        if train_result.win_rate > 55:
            score += 5
        elif train_result.win_rate > 40:
            score += 3

        # (5) 测试期活跃度 — 15 分
        if test_has_trades and test_result.total_trades >= 3:
            score += 15
        elif test_has_trades and test_result.total_trades >= 1:
            score += 8
        else:
            score += 0  # 无交易不加分

        return min(100.0, max(0.0, score))

    def _sample_price_series(self, filtered: list) -> list:
        closes = [k["close"] for k in filtered]
        dates = [k["date"][:10] for k in filtered]
        step = max(1, len(filtered) // 250)
        pts = [
            ProjectedPoint(date=dates[i], value=closes[i])
            for i in range(0, len(filtered), step)
        ]
        if (len(filtered) - 1) % step != 0:
            pts.append(ProjectedPoint(date=dates[-1], value=closes[-1]))
        return pts

    def _build_predicted_equity(
        self, start_equity: float, predicted_ret_pct: float,
        test_start: str, test_bars: int,
    ) -> list:
        pts = [ProjectedPoint(date=test_start, value=start_equity)]
        if test_bars < 1:
            return pts
        daily_mult = (1 + predicted_ret_pct / 100) ** (1.0 / max(1, test_bars))
        n_pts = min(30, test_bars)
        step_b = max(1, test_bars // n_pts)
        for b in range(step_b, test_bars + 1, step_b):
            dt = datetime.strptime(test_start, "%Y-%m-%d") + timedelta(days=int(b * 365 / 252))
            v = start_equity * (daily_mult ** b)
            pts.append(ProjectedPoint(date=dt.strftime("%Y-%m-%d"), value=round(v, 2)))
        return pts

    def _build_bnh_equity(self, test_kline: list, start_equity: float) -> list:
        """构建测试期买入持有权益线"""
        if len(test_kline) < 2:
            return []
        c0 = test_kline[0]["close"]
        if c0 <= 0:
            return []
        pts = []
        step = max(1, len(test_kline) // 100)
        for i in range(0, len(test_kline), step):
            ratio = test_kline[i]["close"] / c0
            pts.append(ProjectedPoint(
                date=test_kline[i]["date"][:10],
                value=round(start_equity * ratio, 2),
            ))
        if (len(test_kline) - 1) % step != 0:
            ratio = test_kline[-1]["close"] / c0
            pts.append(ProjectedPoint(
                date=test_kline[-1]["date"][:10],
                value=round(start_equity * ratio, 2),
            ))
        return pts

    def _build_equity_points(
        self, result, kline: list,
        start_date: str, end_date: str, initial_capital: float,
    ) -> list:
        dates = [k["date"][:10] for k in kline]
        closes = [k["close"] for k in kline]
        trades = result.trades

        capital = initial_capital
        holding_qty = 0
        t_idx = 0
        points = []

        for i in range(len(dates)):
            if dates[i] < start_date or dates[i] > end_date:
                continue
            while t_idx < len(trades) and trades[t_idx].date <= dates[i]:
                t = trades[t_idx]
                if t.date == dates[i]:
                    if t.action == "BUY":
                        capital -= t.price * t.quantity
                        holding_qty += t.quantity
                    elif t.action == "SELL":
                        capital += t.price * t.quantity
                        holding_qty -= t.quantity
                t_idx += 1
            eq = capital + holding_qty * closes[i]
            points.append(ProjectedPoint(date=dates[i], value=round(eq, 2)))

        if len(points) > 200:
            step = max(1, len(points) // 200)
            sampled = [points[j] for j in range(0, len(points), step)]
            if sampled[-1].date != points[-1].date:
                sampled.append(points[-1])
            return sampled
        return points

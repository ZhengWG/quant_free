"""
预测分析服务
多因子评分 + 历史回测 + 前瞻模拟
"""

import asyncio
import math
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from loguru import logger

from app.schemas.backtest import BacktestParams
from app.schemas.prediction import (
    PredictionParams, PredictionResult, PredictionItem,
    FundamentalInfo, ProjectedPoint,
)
from app.services.backtest_service import BacktestService
from app.adapters.market.sina_adapter import SinaAdapter

# 复用 screening_service 中的股票池常量
from app.services.screening_service import (
    HOT_HS_CODES, INDUSTRY_LEADERS_CODES, HOT_HK_CODES,
    BACKTEST_STRATEGIES,
)

# 回测历史窗口：用最近 N 天历史做回测（越近越能反映当前市场环境）
LOOKBACK_DAYS = 365


class PredictionService:
    """预测分析服务"""

    def __init__(self):
        self.adapter = SinaAdapter()
        self.backtest_service = BacktestService()

    # ============================================================
    # 公开方法
    # ============================================================

    async def run_prediction(self, params: PredictionParams) -> PredictionResult:
        start_ts = time.time()

        codes = self._resolve_pool(params.stock_pool, params.custom_codes)
        logger.info(f"Prediction: pool={params.stock_pool}, stocks={len(codes)}, months={params.prediction_months}")

        # 并行获取：K线 + 基本面 + 名称
        kline_task = self._fetch_kline_batch(codes)
        fund_task = self.adapter.get_fundamental_data(codes)
        name_task = self._fetch_name_map(codes)
        kline_map, fund_map, name_map = await asyncio.gather(kline_task, fund_task, name_task)

        # 逐只股票分析
        items: List[PredictionItem] = []
        for code in codes:
            kline = kline_map.get(code, [])
            if len(kline) < 60:
                continue
            fund = fund_map.get(code, {})
            name = name_map.get(code, code)

            item = self._analyze_stock(
                code, name, kline, fund,
                params.prediction_months,
                params.initial_capital,
            )
            if item is not None:
                items.append(item)

        # 排序：按综合得分降序
        items.sort(key=lambda x: x.composite_score, reverse=True)
        items = items[: params.top_n]
        for i, item in enumerate(items):
            item.rank = i + 1

        elapsed = round(time.time() - start_ts, 2)
        return PredictionResult(
            pool_name=params.stock_pool,
            prediction_months=params.prediction_months,
            total_analyzed=len(codes),
            time_taken_seconds=elapsed,
            rankings=items,
        )

    # ============================================================
    # 股票分析（单只）
    # ============================================================

    def _analyze_stock(
        self,
        code: str,
        name: str,
        kline: List[dict],
        fund: dict,
        pred_months: int,
        initial_capital: float,
    ) -> Optional[PredictionItem]:

        closes = [k["close"] for k in kline]
        volumes = [k["volume"] for k in kline]
        highs = [k["high"] for k in kline]
        lows = [k["low"] for k in kline]
        n = len(closes)

        # ---------- 因子得分 ----------
        val_score = self._valuation_score(fund)
        trend_score = self._trend_score(closes)
        mom_score = self._momentum_score(closes)
        vol_score = self._volatility_score(closes, highs, lows)
        volume_score = self._volume_score(closes, volumes)

        composite = (
            val_score * 0.25
            + trend_score * 0.25
            + mom_score * 0.20
            + vol_score * 0.15
            + volume_score * 0.15
        )

        # ---------- 历史回测（取最近 LOOKBACK_DAYS 天数据）----------
        lookback_idx = max(0, n - LOOKBACK_DAYS)
        recent_kline = kline[lookback_idx:]
        if len(recent_kline) < 60:
            recent_kline = kline

        end_date = recent_kline[-1]["date"][:10]
        start_date = recent_kline[0]["date"][:10]

        best_ret = -999.0
        best_strat = ""
        best_label = ""
        best_result = None

        for strategy, short_w, long_w, label in BACKTEST_STRATEGIES:
            bp = BacktestParams(
                stock_code=code,
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                short_window=short_w,
                long_window=long_w,
            )
            result = self.backtest_service.run_backtest_sync(bp, recent_kline)
            if result is not None and result.total_trades >= 2:
                if result.total_return_percent > best_ret:
                    best_ret = result.total_return_percent
                    best_strat = strategy
                    best_label = label
                    best_result = result

        if best_result is None:
            return None

        # ---------- 构建历史权益曲线 & 月度收益 ----------
        hist_equity, monthly_rets = self._build_equity_curve(
            best_result, recent_kline, initial_capital
        )

        # ---------- R² 拟合度 ----------
        fit_score = self._calc_fit_score(hist_equity)

        # 月度统计
        if monthly_rets:
            mr_mean = sum(monthly_rets) / len(monthly_rets)
            mr_std = (sum((r - mr_mean) ** 2 for r in monthly_rets) / len(monthly_rets)) ** 0.5
        else:
            mr_mean, mr_std = 0.0, 0.0

        # ---------- 预测收益 ----------
        hist_days = max(1, (datetime.strptime(end_date, "%Y-%m-%d")
                           - datetime.strptime(start_date, "%Y-%m-%d")).days)
        annual_hist_ret = best_ret / hist_days * 365

        # 因子调整：composite_score 映射到 [0.75, 1.25]（温和调整，不大幅缩减）
        factor_mult = 0.75 + (composite / 100) * 0.50

        # 拟合度权重：R² 决定"相信历史回测"的程度
        # R² 高 → 更信历史；R² 低 → 向因子中性收益收缩
        fit_weight = 0.4 + (fit_score / 100) * 0.6  # [0.4, 1.0]
        # 中性基准 = 年化 8%（大盘长期均值）
        neutral_annual = 8.0
        predicted_annual = (
            fit_weight * annual_hist_ret * factor_mult
            + (1 - fit_weight) * neutral_annual
        )

        predicted_ret = predicted_annual * pred_months / 12

        # ---------- 信号 & 置信度（融合拟合度）----------
        bullish_factors = sum([
            val_score > 55,
            trend_score > 55,
            mom_score > 55,
            volume_score > 55,
        ])
        if predicted_ret > 5 and bullish_factors >= 3:
            signal = "看涨"
        elif predicted_ret < -5 or bullish_factors <= 1:
            signal = "看跌"
        else:
            signal = "震荡"

        if bullish_factors >= 3 and fit_score >= 50 and abs(predicted_ret) > 10:
            confidence = "高"
        elif bullish_factors >= 2 and fit_score >= 30:
            confidence = "中"
        else:
            confidence = "低"

        # ---------- 历史价格序列（采样 ~200 点）----------
        sample_step = max(1, n // 200)
        hist_prices = [
            ProjectedPoint(date=kline[i]["date"][:10], value=closes[i])
            for i in range(0, n, sample_step)
        ]
        if (n - 1) % sample_step != 0:
            hist_prices.append(ProjectedPoint(date=kline[-1]["date"][:10], value=closes[-1]))

        # ---------- 前瞻投影（基准 / 乐观 / 悲观）----------
        last_price = closes[-1]
        last_date = datetime.strptime(kline[-1]["date"][:10], "%Y-%m-%d")
        # 以预测年化收益为基准月度回报
        mr_base = predicted_annual / 12 / 100
        # 乐观/悲观：若有月度 std 则用 ±1σ，否则用 ±30%
        if monthly_rets and mr_std > 0:
            mr_opt = mr_base + mr_std / 100
            mr_pes = mr_base - mr_std / 100
        else:
            mr_opt = mr_base * 1.3
            mr_pes = mr_base * 0.7

        proj_prices = [ProjectedPoint(date=last_date.strftime("%Y-%m-%d"), value=last_price)]
        proj_opt = [ProjectedPoint(date=last_date.strftime("%Y-%m-%d"), value=last_price)]
        proj_pes = [ProjectedPoint(date=last_date.strftime("%Y-%m-%d"), value=last_price)]
        proj_equity = [ProjectedPoint(date=last_date.strftime("%Y-%m-%d"), value=initial_capital)]
        proj_eq_opt = [ProjectedPoint(date=last_date.strftime("%Y-%m-%d"), value=initial_capital)]
        proj_eq_pes = [ProjectedPoint(date=last_date.strftime("%Y-%m-%d"), value=initial_capital)]

        for m in range(1, pred_months + 1):
            d = last_date + timedelta(days=30 * m)
            ds = d.strftime("%Y-%m-%d")
            proj_prices.append(ProjectedPoint(date=ds, value=round(last_price * (1 + mr_base) ** m, 2)))
            proj_opt.append(ProjectedPoint(date=ds, value=round(last_price * (1 + mr_opt) ** m, 2)))
            proj_pes.append(ProjectedPoint(date=ds, value=round(last_price * (1 + mr_pes) ** m, 2)))
            proj_equity.append(ProjectedPoint(date=ds, value=round(initial_capital * (1 + mr_base) ** m, 2)))
            proj_eq_opt.append(ProjectedPoint(date=ds, value=round(initial_capital * (1 + mr_opt) ** m, 2)))
            proj_eq_pes.append(ProjectedPoint(date=ds, value=round(initial_capital * (1 + mr_pes) ** m, 2)))

        return PredictionItem(
            rank=0,
            stock_code=code,
            stock_name=name,
            fundamental=FundamentalInfo(
                pe_dynamic=fund.get("pe"),
                pb=fund.get("pb"),
                market_cap_yi=fund.get("market_cap_yi"),
            ),
            valuation_score=round(val_score, 1),
            trend_score=round(trend_score, 1),
            momentum_score=round(mom_score, 1),
            volatility_score=round(vol_score, 1),
            volume_score=round(volume_score, 1),
            composite_score=round(composite, 1),
            predicted_return_pct=round(predicted_ret, 2),
            predicted_annual_return_pct=round(predicted_annual, 2),
            best_strategy=best_strat,
            best_strategy_label=best_label,
            historical_return_pct=round(best_ret, 2),
            confidence=confidence,
            signal=signal,
            fit_score=round(fit_score, 1),
            monthly_return_mean=round(mr_mean, 2),
            monthly_return_std=round(mr_std, 2),
            historical_prices=hist_prices,
            projected_prices=proj_prices,
            projected_prices_optimistic=proj_opt,
            projected_prices_pessimistic=proj_pes,
            projected_equity=proj_equity,
            projected_equity_optimistic=proj_eq_opt,
            projected_equity_pessimistic=proj_eq_pes,
            historical_equity=hist_equity,
        )

    # ============================================================
    # 历史权益曲线 & 拟合度
    # ============================================================

    def _build_equity_curve(
        self, result, kline: List[dict], initial_capital: float,
    ) -> Tuple[List[ProjectedPoint], List[float]]:
        """
        从回测结果构建逐日权益曲线并提取月度收益率。
        返回 (equity_points, monthly_returns_pct)
        """
        trades = result.trades
        closes = [k["close"] for k in kline]
        dates = [k["date"][:10] for k in kline]
        n = len(closes)

        capital = initial_capital
        holding_qty = 0
        trade_idx = 0
        equity_vals: List[float] = []

        for i in range(n):
            while trade_idx < len(trades) and trades[trade_idx].date == dates[i]:
                t = trades[trade_idx]
                if t.action == "BUY":
                    capital -= t.price * t.quantity
                    holding_qty += t.quantity
                elif t.action == "SELL":
                    capital += t.price * t.quantity
                    holding_qty -= t.quantity
                trade_idx += 1
            eq = capital + holding_qty * closes[i]
            equity_vals.append(eq)

        if not equity_vals:
            return [], []

        # 采样 ~200 点
        step = max(1, n // 200)
        eq_points = [
            ProjectedPoint(date=dates[i], value=round(equity_vals[i], 2))
            for i in range(0, n, step)
        ]
        if (n - 1) % step != 0:
            eq_points.append(ProjectedPoint(date=dates[-1], value=round(equity_vals[-1], 2)))

        # 按月分桶取收益率
        monthly_rets: List[float] = []
        month_start_eq = equity_vals[0]
        cur_month = dates[0][:7]  # "YYYY-MM"
        for i in range(1, n):
            m = dates[i][:7]
            if m != cur_month:
                month_end_eq = equity_vals[i - 1]
                if month_start_eq > 0:
                    monthly_rets.append(
                        (month_end_eq - month_start_eq) / month_start_eq * 100
                    )
                month_start_eq = equity_vals[i - 1]
                cur_month = m
        # 最后一个月
        if month_start_eq > 0 and equity_vals[-1] != month_start_eq:
            monthly_rets.append(
                (equity_vals[-1] - month_start_eq) / month_start_eq * 100
            )

        return eq_points, monthly_rets

    def _calc_fit_score(self, equity_points: List[ProjectedPoint]) -> float:
        """
        计算 R²：权益曲线对线性回归的拟合优度。
        R² 高表示策略收益稳定、接近线性增长，预测可信度高。
        返回 0-100。
        """
        if len(equity_points) < 5:
            return 0.0

        vals = [p.value for p in equity_points]
        n = len(vals)
        xs = list(range(n))

        # 线性回归 y = a + b*x
        sum_x = sum(xs)
        sum_y = sum(vals)
        sum_xy = sum(x * y for x, y in zip(xs, vals))
        sum_x2 = sum(x * x for x in xs)
        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return 0.0

        b = (n * sum_xy - sum_x * sum_y) / denom
        a = (sum_y - b * sum_x) / n

        # R²
        y_mean = sum_y / n
        ss_tot = sum((y - y_mean) ** 2 for y in vals)
        ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, vals))

        if ss_tot == 0:
            return 100.0

        r2 = 1 - ss_res / ss_tot
        return max(0.0, min(100.0, r2 * 100))

    # ============================================================
    # 因子评分
    # ============================================================

    def _valuation_score(self, fund: dict) -> float:
        """估值因子 (0-100)：PE/PB 越低越好"""
        pe = fund.get("pe")
        pb = fund.get("pb")
        score = 50.0  # 无数据时默认中性

        if pe is not None:
            if pe < 0:
                score = 15.0  # 亏损企业
            elif pe < 10:
                score = 90.0
            elif pe < 20:
                score = 75.0
            elif pe < 35:
                score = 55.0
            elif pe < 60:
                score = 35.0
            else:
                score = 15.0

        if pb is not None:
            if pb < 0:
                pb_s = 10.0
            elif pb < 1:
                pb_s = 90.0
            elif pb < 2:
                pb_s = 70.0
            elif pb < 5:
                pb_s = 50.0
            elif pb < 10:
                pb_s = 30.0
            else:
                pb_s = 15.0
            score = score * 0.6 + pb_s * 0.4

        return score

    def _trend_score(self, closes: List[float]) -> float:
        """趋势因子 (0-100)"""
        n = len(closes)
        score = 50.0

        ma5 = sum(closes[-5:]) / 5 if n >= 5 else closes[-1]
        ma20 = sum(closes[-20:]) / 20 if n >= 20 else closes[-1]
        ma60 = sum(closes[-60:]) / 60 if n >= 60 else closes[-1]
        price = closes[-1]

        pts = 0.0
        if ma5 > ma20:
            pts += 20
        if ma20 > ma60:
            pts += 20
        if price > ma60:
            pts += 20
        if price > ma20:
            pts += 15

        # MA20 斜率
        if n >= 25:
            slope = (sum(closes[-5:]) / 5 - sum(closes[-25:-20]) / 5) / (sum(closes[-25:-20]) / 5) * 100
            if slope > 5:
                pts += 25
            elif slope > 0:
                pts += 15
            elif slope > -5:
                pts += 5

        return min(100.0, pts)

    def _momentum_score(self, closes: List[float]) -> float:
        """动量因子 (0-100)"""
        n = len(closes)
        pts = 0.0

        # 20日涨幅
        if n >= 20:
            ret20 = (closes[-1] - closes[-20]) / closes[-20] * 100
            if ret20 > 10:
                pts += 35
            elif ret20 > 3:
                pts += 25
            elif ret20 > 0:
                pts += 15
            elif ret20 > -5:
                pts += 8

        # 60日涨幅
        if n >= 60:
            ret60 = (closes[-1] - closes[-60]) / closes[-60] * 100
            if ret60 > 20:
                pts += 30
            elif ret60 > 5:
                pts += 20
            elif ret60 > 0:
                pts += 12
            elif ret60 > -10:
                pts += 5

        # RSI14
        if n >= 16:
            gains, losses = 0.0, 0.0
            for j in range(n - 14, n):
                d = closes[j] - closes[j - 1]
                if d > 0:
                    gains += d
                else:
                    losses -= d
            avg_g = gains / 14
            avg_l = losses / 14
            rs = avg_g / avg_l if avg_l > 0 else 100
            rsi = 100 - 100 / (1 + rs)
            # RSI 40-60 中性(+15), 30-40 超卖反弹(+25), <30(+35), 60-70(+10), >70 过热(+0)
            if rsi < 30:
                pts += 35
            elif rsi < 40:
                pts += 25
            elif rsi <= 60:
                pts += 15
            elif rsi <= 70:
                pts += 10
            # >70: overbought, no bonus

        return min(100.0, pts)

    def _volatility_score(self, closes: List[float], highs: List[float], lows: List[float]) -> float:
        """波动率因子 (0-100)：低波优先"""
        n = len(closes)
        if n < 20:
            return 50.0

        # ATR%（最近20日）
        atr_sum = 0.0
        for i in range(n - 20, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]) if i > 0 else highs[i] - lows[i],
                abs(lows[i] - closes[i - 1]) if i > 0 else highs[i] - lows[i],
            )
            atr_sum += tr
        atr = atr_sum / 20
        atr_pct = atr / closes[-1] * 100 if closes[-1] > 0 else 5

        # ATR% 越低越好
        if atr_pct < 1.5:
            score = 90.0
        elif atr_pct < 2.5:
            score = 75.0
        elif atr_pct < 4.0:
            score = 55.0
        elif atr_pct < 6.0:
            score = 35.0
        else:
            score = 15.0

        # 近20日最大回撤
        peak = closes[n - 20]
        max_dd = 0.0
        for i in range(n - 20, n):
            if closes[i] > peak:
                peak = closes[i]
            dd = (peak - closes[i]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        if max_dd < 3:
            score = score * 0.6 + 90 * 0.4
        elif max_dd < 8:
            score = score * 0.6 + 65 * 0.4
        elif max_dd < 15:
            score = score * 0.6 + 40 * 0.4
        else:
            score = score * 0.6 + 15 * 0.4

        return score

    def _volume_score(self, closes: List[float], volumes: List[float]) -> float:
        """量能因子 (0-100)"""
        n = len(closes)
        if n < 20:
            return 50.0

        vol5 = sum(volumes[-5:]) / 5
        vol20 = sum(volumes[-20:]) / 20
        vol60 = sum(volumes[-60:]) / 60 if n >= 60 else vol20

        pts = 0.0

        # 近期量比
        ratio = vol5 / vol20 if vol20 > 0 else 1
        if 1.2 < ratio < 2.5:
            pts += 40  # 温和放量
        elif ratio >= 2.5:
            pts += 25  # 爆量，可能是顶
        elif 0.8 < ratio <= 1.2:
            pts += 30  # 正常
        else:
            pts += 10  # 缩量

        # 量价配合：最近5天中，价涨量升的天数
        concordant = 0
        for i in range(n - 5, n):
            if closes[i] > closes[i - 1] and volumes[i] > volumes[i - 1]:
                concordant += 1
            elif closes[i] < closes[i - 1] and volumes[i] < volumes[i - 1]:
                concordant += 1
        # concordant 0-5 -> 0-40
        pts += concordant * 8

        # 长期量能趋势
        if vol20 > vol60 * 1.1:
            pts += 20
        elif vol20 > vol60 * 0.9:
            pts += 10

        return min(100.0, pts)

    # ============================================================
    # 数据获取
    # ============================================================

    def _resolve_pool(self, pool: str, custom_codes: Optional[str]) -> List[str]:
        if pool == "custom" and custom_codes:
            return [c.strip() for c in custom_codes.split(",") if c.strip()]
        elif pool == "industry_leaders":
            return list(INDUSTRY_LEADERS_CODES)
        elif pool == "hot_hk":
            return list(HOT_HK_CODES)
        elif pool == "hs_and_hk":
            return list(HOT_HS_CODES) + list(HOT_HK_CODES)
        else:
            return list(HOT_HS_CODES)

    async def _fetch_kline_batch(self, codes: List[str]) -> Dict[str, List[dict]]:
        sem = asyncio.Semaphore(15)
        datalen = max(400, LOOKBACK_DAYS + 100)

        async def _one(code: str):
            async with sem:
                try:
                    data = await self.adapter.get_kline_data(code, scale=240, datalen=datalen)
                    return code, data or []
                except Exception as e:
                    logger.warning(f"Fetch kline for {code}: {e}")
                    return code, []

        results = await asyncio.gather(*[_one(c) for c in codes])
        return {c: d for c, d in results}

    async def _fetch_name_map(self, codes: List[str]) -> Dict[str, str]:
        try:
            stocks = await self.adapter.get_realtime_data(codes)
            nm: Dict[str, str] = {}
            for s in stocks:
                raw = s["code"]
                name = s.get("name", raw)
                nm[raw] = name
                if s.get("market") == "港股" and not raw.upper().startswith("HK"):
                    nm[f"HK{raw}"] = name
            for c in codes:
                if c not in nm:
                    nm[c] = c
            return nm
        except Exception as e:
            logger.warning(f"Fetch names: {e}")
            return {c: c for c in codes}

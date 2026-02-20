"""
智能选股回测服务
"""

import asyncio
import json
import math
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from loguru import logger

from app.schemas.backtest import BacktestParams, BacktestResult
from app.schemas.screening import (
    SmartScreenParams, SmartScreenResult, ScreenedStock, RankedResult,
)
from app.schemas.strategy_test import StrategyTestParams
from app.services.backtest_service import BacktestService
from app.services.strategy_test_service import StrategyTestService
from app.services.strategy_constants import BACKTEST_STRATEGIES
from app.adapters.market.sina_adapter import SinaAdapter
from app.core.config import settings


# --------------- 股票池 ---------------

# 沪深热门 80 只（蓝筹 + 成长 + 消费 + 科技 + 金融 + 医药 + 新能源）
HOT_HS_CODES = [
    # 大消费
    "600519", "000858", "000568", "600809", "002304", "603288", "600887",
    "000895", "600600", "002557", "603369", "000799",
    # 金融
    "601318", "600036", "000001", "601166", "601398", "601288", "601328",
    "600030", "601688", "000776", "601601", "600000",
    # 科技电子
    "000725", "002415", "300750", "002714", "300059", "603501", "002371",
    "600460", "002049", "603986", "300782", "002916",
    # 医药生物
    "600276", "300015", "000661", "300122", "300760", "002007", "600196",
    "300347", "000538", "002001",
    # 新能源 / 电力
    "600900", "601012", "300274", "002594", "600585", "601985", "600886",
    "002129", "300763", "601899",
    # 制造 / 机械
    "000333", "600031", "601669", "002352", "601100", "000157", "002008",
    "601766", "600104", "000338",
    # 地产 / 基建
    "600048", "001979", "600406", "601668", "601390",
    # 传媒 / 互联网
    "002602", "300413", "002555", "603444",
    # 旅游 / 服务
    "601888", "600138",
]

# 行业龙头 60 只（各行业 Top 2-3）
INDUSTRY_LEADERS_CODES = [
    # 白酒
    "600519", "000858", "000568",
    # 银行
    "601398", "601288", "600036", "000001",
    # 保险
    "601318", "601628", "601601",
    # 券商
    "600030", "601688", "000776",
    # 地产
    "600048", "001979",
    # 家电
    "000333", "000651", "002032",
    # 医药
    "600276", "000661", "300015", "300122",
    # 食品饮料
    "600887", "603288", "002557",
    # 电子 / 半导体
    "002415", "300782", "603501", "002049",
    # 新能源车
    "002594", "300750", "002714",
    # 光伏 / 风电
    "601012", "300274", "600900",
    # 电力
    "600886", "601985",
    # 机械
    "600031", "601100", "000157",
    # 军工
    "600893", "000768", "600760",
    # 汽车
    "600104", "601238", "000338",
    # 建筑
    "601668", "601390",
    # 化工
    "600309", "002601", "600352",
    # 钢铁 / 有色
    "601899", "600585", "601600",
    # 通信
    "600050", "000063",
    # 传媒
    "002602", "300413",
    # 旅游
    "601888", "600138",
]

# 港股热门 30 只
HOT_HK_CODES = [
    "HK00700",  # 腾讯控股
    "HK09988",  # 阿里巴巴
    "HK09618",  # 京东集团
    "HK03690",  # 美团
    "HK09888",  # 百度集团
    "HK01024",  # 快手
    "HK09999",  # 网易
    "HK00981",  # 中芯国际
    "HK02015",  # 理想汽车
    "HK09866",  # 蔚来
    "HK09868",  # 小鹏汽车
    "HK01810",  # 小米集团
    "HK00941",  # 中国移动
    "HK00388",  # 香港交易所
    "HK00005",  # 汇丰控股
    "HK02318",  # 中国平安
    "HK00939",  # 建设银行
    "HK01398",  # 工商银行
    "HK00883",  # 中国海洋石油
    "HK02628",  # 中国人寿
    "HK00027",  # 银河娱乐
    "HK01928",  # 金沙中国
    "HK00669",  # 创科实业
    "HK02269",  # 药明生物
    "HK01177",  # 中国生物制药
    "HK06098",  # 碧桂园服务
    "HK02020",  # 安踏体育
    "HK00291",  # 华润啤酒
    "HK06862",  # 海底捞
    "HK01211",  # 比亚迪股份
]

# --------------- 回测策略：已迁至 strategy_constants，此处保留别名便于本文件内引用 ---------------


class ScreeningService:
    """智能选股回测服务"""

    def __init__(self):
        self.adapter = SinaAdapter()
        self.backtest_service = BacktestService()
        self.strategy_test_service = StrategyTestService()

    async def run_smart_screen(self, params: SmartScreenParams) -> SmartScreenResult:
        """执行智能选股回测"""
        start_time = time.time()

        # 1. 解析股票池
        codes = self._resolve_pool(params.stock_pool, params.custom_codes)
        total_stocks = len(codes)
        logger.info(f"Smart screen: pool={params.stock_pool}, {total_stocks} stocks, mode={params.mode}")

        # 2. 批量获取K线数据
        kline_map = await self._fetch_kline_batch(codes, params.start_date, params.end_date)

        # 3. 获取股票名称
        name_map = await self._fetch_name_map(codes)

        # smart_v2 走新管线
        if params.mode == "smart_v2":
            return await self._run_smart_v2(
                params, codes, kline_map, name_map, total_stocks, start_time
            )

        # 4. 技术面筛选
        screened_list, passed_codes = self._screen_stocks(
            codes, kline_map, name_map, params.screening_strategy
        )

        # 5. 批量回测 + 排名（复用已获取的 K 线数据，无额外网络开销）
        rankings = self._rank_results(
            passed_codes, kline_map, name_map, params
        )

        # 取 Top N
        rankings = rankings[: params.top_n]

        elapsed = round(time.time() - start_time, 2)
        total_backtests = len(passed_codes) * len(BACKTEST_STRATEGIES)

        return SmartScreenResult(
            pool_name=params.stock_pool,
            screening_strategy=params.screening_strategy,
            total_stocks=total_stocks,
            screened_stocks=len(passed_codes),
            total_backtests=total_backtests,
            time_taken_seconds=elapsed,
            rankings=rankings,
            all_screened=screened_list,
        )

    # ==================================================================
    # smart_v2: 综合智选管线
    # ==================================================================

    async def _run_smart_v2(
        self,
        params: SmartScreenParams,
        codes: List[str],
        kline_map: Dict[str, List[dict]],
        name_map: Dict[str, str],
        total_stocks: int,
        start_time: float,
    ) -> SmartScreenResult:
        """
        综合智选管线：
        1. 基本面估值筛选（PE/PB）
        2. Walk-forward 策略测试 80/20
        3. 每股选最高置信度策略
        4. CAGR 预测未来 N 月收益
        5. 复合排名 TopK
        """

        # ---- (a) 获取基本面数据 ----
        fund_map = await self.adapter.get_fundamental_data(codes)

        # ---- (b) 池内百分位估值评分 + 过滤 ----
        kline_ok_codes = [c for c in codes if len(kline_map.get(c, [])) >= 60]
        pe_valid_codes = [c for c in kline_ok_codes
                          if fund_map.get(c, {}).get("pe") is not None
                          and fund_map.get(c, {}).get("pe") > 0]
        v_score_map = self._valuation_scores_pool(fund_map, pe_valid_codes)

        screened_list: List[ScreenedStock] = []
        valuation_passed: List[Tuple[str, float, Optional[float], Optional[float]]] = []

        for code in codes:
            kline = kline_map.get(code, [])
            name = name_map.get(code, code)

            if len(kline) < 60:
                screened_list.append(ScreenedStock(
                    code=code, name=name, passed=False, reason="K线数据不足"
                ))
                continue

            fund = fund_map.get(code, {})
            v_score = v_score_map.get(code, 50.0)
            industry = fund.get("industry", "")

            if v_score < 25:
                screened_list.append(ScreenedStock(
                    code=code, name=name, passed=False,
                    reason=f"[{industry}] 综合排名靠后(PE={fund.get('pe')}, ROE={fund.get('roe')}, 分={v_score:.0f})"
                ))
                continue

            screened_list.append(ScreenedStock(
                code=code, name=name, passed=True,
                reason=f"[{industry}] 通过(PE={fund.get('pe')}, ROE={fund.get('roe')}, 分={v_score:.0f})"
            ))
            valuation_passed.append((code, v_score, fund.get("pe"), fund.get("pb")))

        logger.info(f"[smart_v2] valuation filter: {len(valuation_passed)}/{len(codes)} passed")

        # ---- (b2) AI 基本面分析（DeepSeek） ----
        ai_stocks_data = [
            {
                "code": code, "name": name_map.get(code, code),
                "industry": fund_map.get(code, {}).get("industry", ""),
                "pe": pe, "pb": pb,
                "roe": fund_map.get(code, {}).get("roe"),
                "revenue_growth": fund_map.get(code, {}).get("revenue_growth"),
                "profit_growth": fund_map.get(code, {}).get("profit_growth"),
                "gross_margin": fund_map.get(code, {}).get("gross_margin"),
                "market_cap_yi": fund_map.get(code, {}).get("market_cap_yi"),
                "valuation_score": round(v_score, 1),
            }
            for code, v_score, pe, pb in valuation_passed
        ]
        ai_map = await self._ai_fundamental_analysis(ai_stocks_data)
        logger.info(f"[smart_v2] AI analysis returned for {len(ai_map)} stocks")

        # ---- (c) 单股策略分析（80/20 多策略评分 + 最佳策略），与 POST /backtest/analyze 一致 ----
        candidates: List[dict] = []
        total_backtests = 0

        for code, v_score, pe, pb in valuation_passed:
            kline = kline_map.get(code, [])
            if not kline or len(kline) < 40:
                continue

            test_params = StrategyTestParams(
                stock_code=code,
                start_date=params.start_date,
                end_date=params.end_date,
                initial_capital=params.initial_capital,
                train_ratio=0.8,
            )
            result = self.strategy_test_service.run_test_with_kline(
                test_params, kline, name_map.get(code, code)
            )
            if result is None or not result.items:
                continue
            total_backtests += len(result.items)
            best = result.items[0]

            # 预测未来 N 月收益（基于最佳策略的训练期 CAGR）
            proj_bars = int(params.prediction_months * 21)
            future_ret = self._predict_return_static(
                best.train_return_pct, best.train_bars, proj_bars
            )
            signal = self._direction_static(future_ret)

            # 权益曲线：训练 + 测试（StrategyTestItem 已含 train_equity / test_equity_actual）
            train_eq = [{"date": p.date, "value": p.value} for p in best.train_equity]
            last_train_eq = train_eq[-1]["value"] if train_eq else params.initial_capital
            test_eq_actual = [
                {"date": p.date, "value": p.value} for p in best.test_equity_actual
            ]
            combined_eq = train_eq + test_eq_actual
            if len(combined_eq) > 200:
                step = max(1, len(combined_eq) // 200)
                eq_curve = [combined_eq[j] for j in range(0, len(combined_eq), step)]
                if eq_curve[-1]["date"] != combined_eq[-1]["date"]:
                    eq_curve.append(combined_eq[-1])
            else:
                eq_curve = combined_eq

            last_eq = eq_curve[-1]["value"] if eq_curve else params.initial_capital
            proj_eq = self._build_future_projection(
                last_eq, future_ret, best.test_end, params.prediction_months
            )

            full_ps = [{"date": p.date, "close": p.value} for p in best.full_price_series]
            if len(full_ps) > 250:
                step = max(1, len(full_ps) // 250)
                full_ps_sampled = [full_ps[j] for j in range(0, len(full_ps), step)]
                if full_ps_sampled[-1]["date"] != full_ps[-1]["date"]:
                    full_ps_sampled.append(full_ps[-1])
                full_ps = full_ps_sampled

            ai_info = ai_map.get(code, {})
            fund = fund_map.get(code, {})
            candidates.append(dict(
                code=code,
                name=name_map.get(code, code),
                v_score=v_score,
                pe=pe,
                pb=pb,
                roe=fund.get("roe"),
                industry=fund.get("industry", ""),
                revenue_growth=fund.get("revenue_growth"),
                profit_growth=fund.get("profit_growth"),
                gross_margin=fund.get("gross_margin"),
                ai_score=ai_info.get("ai_score", 50.0),
                ai_analysis=ai_info.get("ai_analysis", ""),
                ai_signal=ai_info.get("ai_signal", ""),
                strategy=best.strategy,
                label=best.strategy_label,
                confidence=best.confidence_score,
                predicted_return=future_ret,
                alpha=best.test_alpha_pct,
                signal=signal,
                train_ret=best.train_return_pct,
                actual_ret=best.actual_return_pct,
                test_bnh=best.test_bnh_pct,
                sharpe=best.train_sharpe,
                max_dd=best.train_max_drawdown,
                win_rate=best.train_win_rate,
                total_trades=best.train_trades + best.actual_trades,
                backtest_result=None,
                equity_curve=eq_curve,
                projected_equity=proj_eq,
                full_price_series=full_ps,
                all_trades=[],
                split_date=best.test_start,
            ))

        logger.info(f"[smart_v2] walk-forward done: {len(candidates)} candidates, "
                     f"{total_backtests} backtests")

        if not candidates:
            elapsed = round(time.time() - start_time, 2)
            return SmartScreenResult(
                pool_name=params.stock_pool,
                screening_strategy="smart_v2",
                total_stocks=total_stocks,
                screened_stocks=len(valuation_passed),
                total_backtests=total_backtests,
                time_taken_seconds=elapsed,
                rankings=[],
                all_screened=screened_list,
                mode="smart_v2",
            )

        # ---- (e) 复合排名（含 AI 评分维度） ----
        v_scores = [c["v_score"] for c in candidates]
        ai_scores = [c["ai_score"] for c in candidates]
        confs = [c["confidence"] for c in candidates]
        preds = [c["predicted_return"] for c in candidates]
        alphas = [c["alpha"] for c in candidates]

        def _norm(vals: List[float], higher_better: bool = True) -> List[float]:
            mn, mx = min(vals), max(vals)
            rng = mx - mn
            if rng == 0:
                return [50.0] * len(vals)
            if higher_better:
                return [(v - mn) / rng * 100 for v in vals]
            return [(mx - v) / rng * 100 for v in vals]

        n_v = _norm(v_scores)
        n_ai = _norm(ai_scores)
        n_c = _norm(confs)
        n_p = _norm(preds)
        n_a = _norm(alphas)

        for i, c in enumerate(candidates):
            c["composite"] = round(
                n_v[i] * 0.10 + n_ai[i] * 0.20
                + n_c[i] * 0.25 + n_p[i] * 0.25 + n_a[i] * 0.20, 2
            )

        candidates.sort(key=lambda x: x["composite"], reverse=True)
        top = candidates[: params.top_n]

        rankings: List[RankedResult] = []
        for idx, c in enumerate(top, 1):
            rankings.append(RankedResult(
                rank=idx,
                stock_code=c["code"],
                stock_name=c["name"],
                strategy=c["strategy"],
                strategy_label=c["label"],
                total_return_percent=round(c["train_ret"], 2),
                sharpe_ratio=round(c["sharpe"], 2),
                max_drawdown=round(c["max_dd"], 2),
                win_rate=round(c["win_rate"], 2),
                total_trades=c["total_trades"],
                score=c["composite"],
                backtest_result=c["backtest_result"],
                valuation_score=round(c["v_score"], 1),
                confidence_score=round(c["confidence"], 1),
                predicted_return_pct=round(c["predicted_return"], 2),
                alpha_pct=round(c["alpha"], 2),
                pe=c["pe"],
                pb=c["pb"],
                roe=c.get("roe"),
                industry=c.get("industry", ""),
                revenue_growth=c.get("revenue_growth"),
                profit_growth=c.get("profit_growth"),
                gross_margin=c.get("gross_margin"),
                signal=c["signal"],
                ai_score=round(c.get("ai_score", 50.0), 1),
                ai_analysis=c.get("ai_analysis", ""),
                equity_curve=c.get("equity_curve"),
                projected_equity=c.get("projected_equity"),
                full_price_series=c.get("full_price_series"),
                all_trades=c.get("all_trades"),
                split_date=c.get("split_date"),
            ))

        avg_conf = sum(c["confidence"] for c in top) / len(top) if top else 0
        avg_pred = sum(c["predicted_return"] for c in top) / len(top) if top else 0
        avg_test_bnh = sum(c["test_bnh"] for c in top) / len(top) if top else 0

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"[smart_v2] final: {len(rankings)} stocks, "
                     f"avg_conf={avg_conf:.1f}, avg_pred={avg_pred:.2f}%, "
                     f"elapsed={elapsed}s")

        return SmartScreenResult(
            pool_name=params.stock_pool,
            screening_strategy="smart_v2",
            total_stocks=total_stocks,
            screened_stocks=len(valuation_passed),
            total_backtests=total_backtests,
            time_taken_seconds=elapsed,
            rankings=rankings,
            all_screened=screened_list,
            mode="smart_v2",
            test_bnh_pct=round(avg_test_bnh, 2),
            avg_confidence=round(avg_conf, 1),
            avg_predicted_return=round(avg_pred, 2),
            prediction_months=params.prediction_months,
        )

    # ==================================================================
    # smart_v2 static helpers (inlined to avoid circular imports)
    # ==================================================================

    @staticmethod
    def _valuation_scores_pool(fund_map: Dict[str, dict], codes: List[str]) -> Dict[str, float]:
        """
        池内百分位排名评分 (0-100)。
        不同指标按百分位排名，避免跨行业固定阈值的不合理性。
        PE/PB: 越低越好 (反向排名)
        ROE/利润增长/毛利率: 越高越好 (正向排名)
        """
        def _collect(key: str) -> List[Tuple[str, float]]:
            out = []
            for c in codes:
                v = fund_map.get(c, {}).get(key)
                if v is not None and isinstance(v, (int, float)):
                    out.append((c, float(v)))
            return out

        def _percentile_scores(
            pairs: List[Tuple[str, float]], higher_better: bool
        ) -> Dict[str, float]:
            if len(pairs) < 2:
                return {c: 50.0 for c, _ in pairs}
            sorted_p = sorted(pairs, key=lambda x: x[1], reverse=higher_better)
            n = len(sorted_p)
            return {
                code: round(((n - rank) / (n - 1)) * 100, 1)
                for rank, (code, _) in enumerate(sorted_p)
            }

        pe_pairs = [(c, v) for c, v in _collect("pe") if v > 0]
        pb_pairs = [(c, v) for c, v in _collect("pb") if v > 0]
        roe_pairs = _collect("roe")
        grow_pairs = _collect("profit_growth")
        gm_pairs = _collect("gross_margin")

        pe_sc = _percentile_scores(pe_pairs, higher_better=False)
        pb_sc = _percentile_scores(pb_pairs, higher_better=False)
        roe_sc = _percentile_scores(roe_pairs, higher_better=True)
        grow_sc = _percentile_scores(grow_pairs, higher_better=True)
        gm_sc = _percentile_scores(gm_pairs, higher_better=True)

        result: Dict[str, float] = {}
        for code in codes:
            pe_s = pe_sc.get(code, 50.0)
            pb_s = pb_sc.get(code, 50.0)
            roe_s = roe_sc.get(code, 50.0)
            grow_s = grow_sc.get(code, 50.0)
            gm_s = gm_sc.get(code, 50.0)
            score = pe_s * 0.20 + pb_s * 0.15 + roe_s * 0.30 + grow_s * 0.20 + gm_s * 0.15
            result[code] = round(score, 1)
        return result

    async def _ai_fundamental_analysis(
        self, stocks_data: List[dict]
    ) -> Dict[str, dict]:
        """
        批量调用 DeepSeek 进行基本面分析，返回 {code: {ai_score, ai_analysis, ai_signal}}。
        API 不可用时静默降级返回空 dict。
        """
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY not set – skipping AI fundamental analysis")
            return {}

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=60.0,
        )
        model = settings.DEEPSEEK_MODEL or "deepseek-chat"
        result: Dict[str, dict] = {}

        BATCH_SIZE = 15
        batches = [
            stocks_data[i: i + BATCH_SIZE]
            for i in range(0, len(stocks_data), BATCH_SIZE)
        ]

        def _fmt(v):
            if v is None:
                return "N/A"
            return str(v)

        def _call_batch(batch: List[dict]) -> Dict[str, dict]:
            header = "| 代码 | 名称 | 行业 | PE | PB | ROE% | 营收增长% | 净利润增长% | 毛利率% | 市值(亿) |"
            sep = "|------|------|------|-----|-----|------|---------|----------|--------|---------|"
            rows = header + "\n" + sep + "\n"
            for s in batch:
                rows += (
                    f"| {s.get('code','')} | {s.get('name','')} "
                    f"| {_fmt(s.get('industry'))} "
                    f"| {_fmt(s.get('pe'))} | {_fmt(s.get('pb'))} "
                    f"| {_fmt(s.get('roe'))} | {_fmt(s.get('revenue_growth'))} "
                    f"| {_fmt(s.get('profit_growth'))} | {_fmt(s.get('gross_margin'))} "
                    f"| {_fmt(s.get('market_cap_yi'))} |\n"
                )

            prompt = (
                "你是一位资深A股基本面分析师。请对以下股票进行基本面分析评分。\n\n"
                "**重要**：不同行业的合理PE/PB/ROE标准差异很大，请务必结合行业特点评分：\n"
                "- 银行/保险：低PE(5-8)、低PB(<1)是正常的，ROE 10-15%算优秀\n"
                "- 消费/白酒：PE 20-30合理，高ROE(>20%)和高毛利率是关键\n"
                "- 科技/新能源：PE可容忍更高(30-50)，重点看成长性\n"
                "- 周期行业：需考虑周期位置，低PE可能是景气顶点\n\n"
                f"股票列表：\n{rows}\n"
                "请结合各股票所属行业的合理估值范围，综合评分(0-100)：\n"
                "1. 行业内估值合理性（PE/PB相对同行业是否偏低）\n"
                "2. 盈利质量（ROE、毛利率在行业中的水平）\n"
                "3. 成长性（营收/利润增长是否超越行业平均）\n"
                "4. 行业地位与竞争优势\n"
                "5. 风险因素（行业周期、政策风险等）\n\n"
                "以JSON数组返回，每只股票一个对象：\n"
                '[{"code":"600519","score":78,"analysis":"白酒龙头，ROE 24%行业顶级...","signal":"看涨"}]\n'
                "signal只能是：看涨/看跌/中性\n"
                "只返回JSON数组，不要其他文字。"
            )
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是专业的A股基本面分析师，只返回JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                    max_tokens=4000,
                )
                text = (resp.choices[0].message.content or "").strip()
                logger.debug(f"AI raw response (first 300): {text[:300]}")
                m = re.search(r"\[.*\]", text, re.S)
                if not m:
                    logger.warning(f"AI analysis: no JSON array in response: {text[:200]}")
                    return {}
                items = json.loads(m.group())
                batch_map: Dict[str, dict] = {}
                for item in items:
                    code = str(item.get("code", ""))
                    batch_map[code] = {
                        "ai_score": float(item.get("score", 50)),
                        "ai_analysis": str(item.get("analysis", "")),
                        "ai_signal": str(item.get("signal", "")),
                    }
                logger.info(f"AI batch parsed {len(batch_map)} stocks OK")
                return batch_map
            except Exception as e:
                logger.error(f"AI fundamental analysis batch error: {type(e).__name__}: {e}")
                return {}

        loop = asyncio.get_running_loop()
        for idx, batch in enumerate(batches):
            try:
                logger.info(f"AI batch {idx+1}/{len(batches)}: {len(batch)} stocks ...")
                batch_result = await loop.run_in_executor(None, _call_batch, batch)
                result.update(batch_result)
            except Exception as e:
                logger.error(f"AI batch executor error: {type(e).__name__}: {e}")

        logger.info(f"AI fundamental analysis done: {len(result)}/{len(stocks_data)} stocks")
        return result

    @staticmethod
    def _bnh_return(kline_segment: list) -> float:
        if len(kline_segment) < 2:
            return 0.0
        c0 = kline_segment[0]["close"]
        c1 = kline_segment[-1]["close"]
        return (c1 - c0) / c0 * 100 if c0 > 0 else 0.0

    @staticmethod
    def _predict_return_static(train_ret_pct: float, train_bars: int, target_bars: int) -> float:
        if train_bars < 5 or target_bars < 1:
            return 0.0
        r = train_ret_pct / 100
        if r <= -1:
            return -100.0
        cagr_daily = (1 + r) ** (1.0 / train_bars) - 1
        projected = (1 + cagr_daily) ** target_bars - 1
        return projected * 100

    @staticmethod
    def _direction_static(ret: float) -> str:
        if ret > 3:
            return "看涨"
        if ret < -3:
            return "看跌"
        return "震荡"

    @staticmethod
    def _calc_confidence_static(
        predicted_ret, actual_ret, ret_error, dir_correct,
        train_result, test_result,
        train_alpha, test_alpha, test_has_trades,
    ) -> float:
        score = 0.0

        if dir_correct:
            score += 25
        elif (predicted_ret >= 0 and actual_ret >= 0) or (predicted_ret < 0 and actual_ret < 0):
            score += 12

        score += max(0.0, 25 - ret_error * 0.83)

        if train_alpha >= 0 and test_alpha >= 0:
            score += 20
        elif train_alpha < 0 and test_alpha < 0:
            score += 10
        elif abs(train_alpha) < 3 and abs(test_alpha) < 3:
            score += 8

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

        if test_has_trades and test_result.total_trades >= 3:
            score += 15
        elif test_has_trades and test_result.total_trades >= 1:
            score += 8

        return min(100.0, max(0.0, score))

    @staticmethod
    def _build_equity_from_result(result, kline, start_date, end_date, initial_capital):
        """从回测结果构建权益曲线点 [{date, value}]"""
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
            points.append({"date": dates[i], "value": round(eq, 2)})

        if len(points) > 200:
            step = max(1, len(points) // 200)
            sampled = [points[j] for j in range(0, len(points), step)]
            if sampled[-1]["date"] != points[-1]["date"]:
                sampled.append(points[-1])
            return sampled
        return points

    @staticmethod
    def _build_future_projection(last_equity, predicted_return_pct, start_date_str, months):
        """构建未来预测权益曲线 [{date, value}]"""
        total_days = months * 21
        if total_days < 1:
            return []

        daily_mult = (1 + predicted_return_pct / 100) ** (1.0 / max(1, total_days))
        n_pts = min(30, total_days)
        step = max(1, total_days // n_pts)

        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        pts = [{"date": start_date_str, "value": round(last_equity, 2)}]

        from datetime import timedelta
        for b in range(step, total_days + 1, step):
            dt = start + timedelta(days=int(b * 365 / 252))
            v = last_equity * (daily_mult ** b)
            pts.append({"date": dt.strftime("%Y-%m-%d"), "value": round(v, 2)})

        return pts

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

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

    async def _fetch_kline_batch(
        self, codes: List[str], start_date: str, end_date: str
    ) -> Dict[str, List[dict]]:
        """并发获取K线数据"""
        sem = asyncio.Semaphore(15)

        try:
            d_start = datetime.strptime(start_date, "%Y-%m-%d")
            d_end = datetime.strptime(end_date, "%Y-%m-%d")
            days = (d_end - d_start).days
        except ValueError:
            days = 600
        datalen = max(300, int(days * 0.75) + 110)

        async def fetch_one(code: str) -> Tuple[str, List[dict]]:
            async with sem:
                try:
                    data = await self.adapter.get_kline_data(code, scale=240, datalen=datalen)
                    return code, data or []
                except Exception as e:
                    logger.warning(f"Fetch kline failed for {code}: {e}")
                    return code, []

        results = await asyncio.gather(*[fetch_one(c) for c in codes])
        return {code: data for code, data in results}

    async def _fetch_name_map(self, codes: List[str]) -> Dict[str, str]:
        """获取股票名称映射（兼容 HK 前缀）"""
        try:
            stocks = await self.adapter.get_realtime_data(codes)
            name_map: Dict[str, str] = {}
            for s in stocks:
                raw = s["code"]
                name = s.get("name", raw)
                name_map[raw] = name
                if s.get("market") == "港股" and not raw.upper().startswith("HK"):
                    name_map[f"HK{raw}"] = name
            for c in codes:
                if c not in name_map:
                    name_map[c] = c
            return name_map
        except Exception as e:
            logger.warning(f"Fetch realtime data for names failed: {e}")
            return {c: c for c in codes}

    def _screen_stocks(
        self,
        codes: List[str],
        kline_map: Dict[str, List[dict]],
        name_map: Dict[str, str],
        strategy: str,
    ) -> Tuple[List[ScreenedStock], List[str]]:
        """技术面筛选"""
        screened: List[ScreenedStock] = []
        passed: List[str] = []

        for code in codes:
            kline = kline_map.get(code, [])
            name = name_map.get(code, code)

            if len(kline) < 60:
                screened.append(ScreenedStock(code=code, name=name, passed=False, reason="K线数据不足"))
                continue

            check_map = {
                "uptrend": self._check_uptrend,
                "volume_breakout": self._check_volume_breakout,
                "rsi_oversold": self._check_rsi_oversold,
                "macd_golden": self._check_macd_golden,
            }

            if strategy == "all":
                screened.append(ScreenedStock(code=code, name=name, passed=True, reason="全部通过"))
                passed.append(code)
            elif strategy == "momentum":
                screened.append(ScreenedStock(code=code, name=name, passed=True, reason="待排序"))
                passed.append(code)
            elif strategy in check_map:
                ok, reason = check_map[strategy](kline)
                screened.append(ScreenedStock(code=code, name=name, passed=ok, reason=reason))
                if ok:
                    passed.append(code)
            else:
                screened.append(ScreenedStock(code=code, name=name, passed=True, reason="默认通过"))
                passed.append(code)

        # momentum：按 20 日涨幅排序取前半
        if strategy == "momentum" and passed:
            scored = []
            for code in passed:
                kline = kline_map.get(code, [])
                if len(kline) >= 20:
                    change = (kline[-1]["close"] - kline[-20]["close"]) / kline[-20]["close"]
                else:
                    change = 0
                scored.append((code, change))
            scored.sort(key=lambda x: x[1], reverse=True)
            half = max(1, len(scored) // 2)
            top_codes = {c for c, _ in scored[:half]}

            new_passed = []
            for item in screened:
                if item.code in passed:
                    if item.code in top_codes:
                        idx = next(i for i, (c, _) in enumerate(scored) if c == item.code)
                        item.reason = f"20日涨幅 {scored[idx][1]*100:.1f}%，排名前半"
                        item.passed = True
                        new_passed.append(item.code)
                    else:
                        item.reason = "20日涨幅排名靠后"
                        item.passed = False
            passed = new_passed

        return screened, passed

    def _check_uptrend(self, kline: List[dict]) -> Tuple[bool, str]:
        """趋势向上：MA5 > MA20 且 价格 > MA60"""
        closes = [k["close"] for k in kline]
        if len(closes) < 60:
            return False, "数据不足60日"

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60
        price = closes[-1]

        if ma5 > ma20 and price > ma60:
            return True, f"MA5({ma5:.2f})>MA20({ma20:.2f}), 价格({price:.2f})>MA60({ma60:.2f})"
        return False, f"MA5({ma5:.2f}) vs MA20({ma20:.2f}), 价格({price:.2f}) vs MA60({ma60:.2f})"

    def _check_volume_breakout(self, kline: List[dict]) -> Tuple[bool, str]:
        """放量突破：近5日均量 > 1.5× 60日均量"""
        if len(kline) < 60:
            return False, "数据不足60日"

        vol_5 = sum(k["volume"] for k in kline[-5:]) / 5
        vol_60 = sum(k["volume"] for k in kline[-60:]) / 60

        if vol_60 > 0 and vol_5 > 1.5 * vol_60:
            ratio = vol_5 / vol_60
            return True, f"5日均量/60日均量 = {ratio:.2f}x (>1.5x)"
        ratio = vol_5 / vol_60 if vol_60 > 0 else 0
        return False, f"5日均量/60日均量 = {ratio:.2f}x (<1.5x)"

    def _check_rsi_oversold(self, kline: List[dict]) -> Tuple[bool, str]:
        """RSI 超卖：RSI14 < 35"""
        closes = [k["close"] for k in kline]
        if len(closes) < 16:
            return False, "数据不足"
        period = 14
        gains, losses = 0.0, 0.0
        for j in range(len(closes) - period, len(closes)):
            delta = closes[j] - closes[j - 1]
            if delta > 0:
                gains += delta
            else:
                losses -= delta
        avg_gain = gains / period
        avg_loss = losses / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - 100 / (1 + rs)
        if rsi < 35:
            return True, f"RSI14={rsi:.1f} < 35 超卖"
        return False, f"RSI14={rsi:.1f} ≥ 35"

    def _check_macd_golden(self, kline: List[dict]) -> Tuple[bool, str]:
        """MACD 金叉：DIF 上穿 DEA（近5日内发生）"""
        closes = [k["close"] for k in kline]
        if len(closes) < 35:
            return False, "数据不足"

        def _ema(data, period):
            result = [0.0] * len(data)
            m = 2 / (period + 1)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = (data[i] - result[i - 1]) * m + result[i - 1]
            return result

        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        dif = [ema12[i] - ema26[i] for i in range(len(closes))]
        dea = _ema(dif, 9)

        for i in range(len(closes) - 5, len(closes)):
            if i >= 1 and dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
                return True, f"MACD金叉(DIF={dif[i]:.3f}, DEA={dea[i]:.3f})"
        return False, f"近5日无MACD金叉(DIF={dif[-1]:.3f}, DEA={dea[-1]:.3f})"

    def _rank_results(
        self,
        codes: List[str],
        kline_map: Dict[str, List[dict]],
        name_map: Dict[str, str],
        params: SmartScreenParams,
    ) -> List[RankedResult]:
        """对每只股票 × 多种策略回测，综合评分排名（纯计算，无网络IO）"""
        valid: List[Tuple[str, str, str, BacktestResult]] = []

        for code in codes:
            kline = kline_map.get(code, [])
            if not kline:
                continue
            for strategy, short_w, long_w, label in BACKTEST_STRATEGIES:
                bp = BacktestParams(
                    stock_code=code,
                    strategy=strategy,
                    start_date=params.start_date,
                    end_date=params.end_date,
                    initial_capital=params.initial_capital,
                    short_window=short_w,
                    long_window=long_w,
                    stop_loss_pct=params.stop_loss_pct,
                    trailing_stop_pct=params.trailing_stop_pct,
                    risk_per_trade=params.risk_per_trade,
                    max_position_pct=params.max_position_pct,
                    trend_ma_len=params.trend_ma_len,
                    cooldown_bars=params.cooldown_bars,
                )
                result = self.backtest_service.run_backtest_sync(bp, kline)
                if result is not None:
                    valid.append((code, strategy, label, result))

        # 过滤：至少 2 笔完整交易才有统计意义
        valid = [(c, s, l, r) for c, s, l, r in valid if r.total_trades >= 2]
        if not valid:
            return []

        returns = [r.total_return_percent for _, _, _, r in valid]
        sharpes = [r.sharpe_ratio for _, _, _, r in valid]
        drawdowns = [r.max_drawdown for _, _, _, r in valid]
        win_rates = [r.win_rate for _, _, _, r in valid]

        def normalize(values: List[float], higher_better: bool = True) -> List[float]:
            min_v = min(values)
            max_v = max(values)
            rng = max_v - min_v
            if rng == 0:
                return [50.0] * len(values)
            if higher_better:
                return [(v - min_v) / rng * 100 for v in values]
            else:
                return [(max_v - v) / rng * 100 for v in values]

        norm_ret = normalize(returns, higher_better=True)
        norm_sharpe = normalize(sharpes, higher_better=True)
        norm_dd = normalize(drawdowns, higher_better=False)
        norm_wr = normalize(win_rates, higher_better=True)

        # 综合评分 = 收益率(35%) + 夏普(30%) + 回撤控制(20%) + 胜率(15%)
        scored: List[Tuple[float, str, str, str, BacktestResult]] = []
        for i, (code, strat, label, r) in enumerate(valid):
            raw_score = (
                norm_ret[i] * 0.35
                + norm_sharpe[i] * 0.30
                + norm_dd[i] * 0.20
                + norm_wr[i] * 0.15
            )
            # 负收益惩罚：收益为负时最高只能拿 40 分
            if r.total_return_percent < 0:
                raw_score = min(raw_score, 40.0)
            scored.append((round(raw_score, 2), code, strat, label, r))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 每只股票只保留评分最高的策略
        seen_codes: set = set()
        rankings: List[RankedResult] = []
        rank_idx = 0
        for score, code, strat, label, r in scored:
            if code in seen_codes:
                continue
            seen_codes.add(code)
            rank_idx += 1
            rankings.append(
                RankedResult(
                    rank=rank_idx,
                    stock_code=code,
                    stock_name=name_map.get(code, code),
                    strategy=strat,
                    strategy_label=label,
                    total_return_percent=r.total_return_percent,
                    sharpe_ratio=r.sharpe_ratio,
                    max_drawdown=r.max_drawdown,
                    win_rate=r.win_rate,
                    total_trades=r.total_trades,
                    score=score,
                    backtest_result=r,
                )
            )

        return rankings

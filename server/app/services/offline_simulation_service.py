"""
离线历史模拟服务 OfflineSimulationService
────────────────────────────────────────────
流程：
  1. 拉取全量历史 K 线（训练期 + 模拟期）
  2. 训练期做 Walk-Forward 选最优策略
  3. 模拟期：按日回放，信号→模拟成交（独立账户）
  4. 拉取基准指数 K 线，做买入持有基准
  5. 计算绩效 & Alpha 对比
"""

import math
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from loguru import logger

from app.schemas.auto_trade import (
    BENCHMARK_ALIASES,
    BenchmarkResult,
    EquityPoint,
    OfflineSimConfig,
    OfflineSimResult,
    StockSimDetail,
    TradeRecord,
)
from app.schemas.strategy_test import StrategyTestParams
from app.services.backtest_service import BacktestService
from app.services.strategy_test_service import StrategyTestService
from app.services.strategy_constants import BACKTEST_STRATEGIES
from app.adapters.market.sina_adapter import SinaAdapter

# ── 手续费（与 TradeService 一致）──
_COMMISSION_RATE = 0.00025
_COMMISSION_MIN = 5.0
_STAMP_TAX_RATE = 0.0005
_TRANSFER_FEE_RATE = 0.00001
_LOT_SIZE = 100


def _fees(action: str, price: float, qty: int) -> float:
    amt = price * qty
    com = max(amt * _COMMISSION_RATE, _COMMISSION_MIN)
    tax = amt * _STAMP_TAX_RATE if action == "SELL" else 0.0
    tr = amt * _TRANSFER_FEE_RATE
    return round(com + tax + tr, 2)


def _resolve_benchmark(code: str) -> Tuple[str, str]:
    """将别名或任意代码统一到 (fetch_code, 显示名)"""
    lower = code.lower()
    if lower in BENCHMARK_ALIASES:
        return BENCHMARK_ALIASES[lower]
    # 尝试常见全称匹配
    for alias, (fetch, name) in BENCHMARK_ALIASES.items():
        if code == fetch:
            return fetch, name
    # 未知代码，原样传给 adapter，名称用代码本身
    return code, code


class OfflineSimulationService:

    def __init__(self):
        self.backtest_svc = BacktestService()
        self.strategy_test_svc = StrategyTestService()
        self.adapter = SinaAdapter()

    # ══════════════════════════════════════════════════════
    # 主入口
    # ══════════════════════════════════════════════════════

    async def run_simulation(self, cfg: OfflineSimConfig) -> OfflineSimResult:
        """
        完整离线历史模拟：
          - 训练期（start_date 前 validate_months 个月）: 选最优策略
          - 模拟期（start_date ~ end_date）: 按日回放
          - 与基准指数买入持有对比
        """
        start_dt = datetime.strptime(cfg.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(cfg.end_date, "%Y-%m-%d")
        train_start_dt = start_dt - timedelta(days=cfg.validate_months * 31)
        train_start = train_start_dt.strftime("%Y-%m-%d")

        # 需要拉取的总 K 线条数：从训练起始到今日（API 始终返回最近 N 条）
        today_dt = datetime.now()
        days_to_today = (today_dt - train_start_dt).days
        needed_bars = int(days_to_today * 0.72) + 100   # 0.72 ≈ 交易日占自然日比例
        needed_bars = max(needed_bars, 300)

        logger.info(
            f"[OfflineSim] 训练期 {train_start}~{cfg.start_date}, "
            f"模拟期 {cfg.start_date}~{cfg.end_date}, "
            f"target_bars={needed_bars}"
        )

        # ── 1. 拉取所有股票 K 线 ──────────────────────────
        stock_klines: Dict[str, List[dict]] = {}
        for code in cfg.stock_codes:
            kline = await self._fetch_kline(code, needed_bars)
            if kline and len(kline) >= 60:
                stock_klines[code] = kline
                logger.info(f"[OfflineSim] {code}: {len(kline)} bars "
                             f"[{kline[0]['date'][:10]}~{kline[-1]['date'][:10]}]")
            else:
                logger.warning(f"[OfflineSim] {code}: 数据不足 ({len(kline or [])} bars)，跳过")

        valid_codes = list(stock_klines.keys())
        if not valid_codes:
            raise ValueError("所有股票数据获取失败，无法进行模拟")

        # ── 2. 训练期选策略 ───────────────────────────────
        strategy_map = self._select_strategies(
            valid_codes, stock_klines, train_start, cfg.start_date, cfg.train_ratio
        )
        logger.info(f"[OfflineSim] 策略选择完成: "
                     + ", ".join(f"{c}→{v['label']}" for c, v in strategy_map.items()))

        # ── 3. 预计算每只股票的信号序列 ─────────────────────
        signals_by_date: Dict[str, Dict[str, str]] = {}  # {code: {date: BUY/SELL}}
        for code in valid_codes:
            kline = stock_klines[code]
            info = strategy_map[code]
            sig_map = self._precompute_signals(kline, info)
            signals_by_date[code] = sig_map

        # ── 4. 构建价格查询表 ────────────────────────────
        price_lut: Dict[str, Dict[str, dict]] = {}
        for code in valid_codes:
            price_lut[code] = {k["date"][:10]: k for k in stock_klines[code]}

        # ── 4b. 市场环境查询表（沪深300均线）─────────────────
        market_regime_lut: Dict[str, bool] = {}
        if cfg.market_regime_filter:
            regime_kline = await self._fetch_kline(cfg.market_regime_code, needed_bars)
            market_regime_lut = self._build_regime_lut(
                regime_kline, cfg.start_date, cfg.end_date
            )
            allow_days = sum(1 for v in market_regime_lut.values() if v)
            logger.info(
                f"[OfflineSim] 市场环境过滤({cfg.market_regime_code}): "
                f"{allow_days}/{len(market_regime_lut)} 天允许建仓"
            )

        # ── 5. 模拟期逐日回放 ────────────────────────────
        all_sim_dates = sorted({
            d for code in valid_codes
            for d in price_lut[code].keys()
            if cfg.start_date <= d <= cfg.end_date
        })
        if not all_sim_dates:
            raise ValueError(f"模拟期 {cfg.start_date}~{cfg.end_date} 内无交易日数据")

        cash = cfg.initial_capital
        positions: Dict[str, dict] = {
            code: {"qty": 0, "avg_cost": 0.0, "entry_date": ""}
            for code in valid_codes
        }
        equity_curve: List[EquityPoint] = []
        trade_records: List[TradeRecord] = []
        trade_stats: Dict[str, dict] = {
            code: {"total": 0, "wins": 0, "fees": 0.0, "realized": 0.0}
            for code in valid_codes
        }

        for date in all_sim_dates:
            # --- 处理信号 ---
            for code in valid_codes:
                bar = price_lut[code].get(date)
                if bar is None:
                    continue
                price = bar["close"]
                signal = signals_by_date[code].get(date, "HOLD")
                pos = positions[code]

                # ── 修复1：止损 / 止盈 / 持仓超期检查 ────────────
                stop_note = ""
                if pos["qty"] > 0 and pos["avg_cost"] > 0:
                    chg_pct = (price - pos["avg_cost"]) / pos["avg_cost"]
                    if chg_pct <= -cfg.stop_loss_pct:
                        signal = "SELL"
                        stop_note = f"止损{chg_pct*100:.1f}%"
                    elif chg_pct >= cfg.take_profit_pct and signal != "SELL":
                        signal = "SELL"
                        stop_note = f"止盈{chg_pct*100:.1f}%"

                if pos["qty"] > 0 and pos["entry_date"] and signal != "SELL":
                    from datetime import datetime as _dt
                    hold_days_actual = (
                        _dt.strptime(date, "%Y-%m-%d") -
                        _dt.strptime(pos["entry_date"], "%Y-%m-%d")
                    ).days
                    if hold_days_actual >= cfg.max_hold_days:
                        signal = "SELL"
                        stop_note = f"持仓超期{hold_days_actual}天"

                if signal == "SELL" and pos["qty"] > 0:
                    qty = pos["qty"]
                    fee = _fees("SELL", price, qty)
                    revenue = price * qty - fee
                    profit = round(revenue - pos["avg_cost"] * qty, 2)
                    cash += revenue
                    trade_stats[code]["total"] += 1
                    trade_stats[code]["fees"] += fee
                    trade_stats[code]["realized"] += profit
                    if profit > 0:
                        trade_stats[code]["wins"] += 1
                    pos["qty"] = 0
                    pos["avg_cost"] = 0.0
                    trade_records.append(TradeRecord(
                        date=date, stock_code=code, action="SELL",
                        price=price, quantity=qty, fees=fee,
                        profit=profit, cash_after=round(cash, 2),
                        note=stop_note,
                    ))

                elif signal == "BUY" and pos["qty"] == 0:
                    # ── 修复2：策略验证底线（用 Alpha 过滤，熊市同样适用）────
                    test_alpha = strategy_map[code].get("test_alpha_pct", 0.0)
                    if test_alpha < cfg.min_test_return_pct:
                        continue  # 策略跑输买入持有超过阈值，不开仓
                    # ── 修复3：市场环境过滤 ────────────────────────
                    if cfg.market_regime_filter:
                        market_ok = market_regime_lut.get(date, True)
                        if not market_ok:
                            continue  # 市场处于下行趋势，不开新仓

                    max_invest = cfg.initial_capital * cfg.max_position_pct
                    max_invest = min(max_invest, cash * 0.95)
                    raw_qty = int(max_invest / price) if price > 0 else 0
                    qty = (raw_qty // _LOT_SIZE) * _LOT_SIZE
                    if qty > 0:
                        fee = _fees("BUY", price, qty)
                        total_cost = price * qty + fee
                        if cash >= total_cost:
                            cash -= total_cost
                            cost_per = (price * qty + fee) / qty
                            pos["qty"] = qty
                            pos["avg_cost"] = cost_per
                            pos["entry_date"] = date
                            trade_stats[code]["fees"] += fee
                            trade_records.append(TradeRecord(
                                date=date, stock_code=code, action="BUY",
                                price=price, quantity=qty, fees=fee, cash_after=round(cash, 2)
                            ))

            # --- 计算当日组合市值 ---
            mkt_val = 0.0
            for code in valid_codes:
                if positions[code]["qty"] > 0:
                    bar = price_lut[code].get(date)
                    if bar:
                        mkt_val += bar["close"] * positions[code]["qty"]
            equity_curve.append(EquityPoint(date=date, value=round(cash + mkt_val, 2)))

        # ── 6. 计算组合绩效指标 ──────────────────────────
        final_capital = equity_curve[-1].value if equity_curve else cfg.initial_capital
        total_return = final_capital - cfg.initial_capital
        total_return_pct = round(total_return / cfg.initial_capital * 100, 2)

        sim_years = max((end_dt - start_dt).days / 365.0, 0.01)
        ann_ret = round((((final_capital / cfg.initial_capital) ** (1 / sim_years)) - 1) * 100, 2)
        max_dd = self._max_drawdown([p.value for p in equity_curve])
        sharpe = self._sharpe([p.value for p in equity_curve])

        total_trades = sum(s["total"] for s in trade_stats.values())
        win_trades = sum(s["wins"] for s in trade_stats.values())
        win_rate = round(win_trades / total_trades * 100 if total_trades > 0 else 0.0, 2)
        total_fees = round(sum(s["fees"] for s in trade_stats.values()), 2)

        # ── 7. 拉取基准指数并计算买入持有 ───────────────────
        bm_results = await self._calc_benchmarks(
            cfg.benchmarks, cfg.start_date, cfg.end_date,
            cfg.initial_capital, int((end_dt - start_dt).days * 0.75) + 50,
        )

        alpha_summary = {
            bm.name: round(total_return_pct - bm.total_return_pct, 2)
            for bm in bm_results
        }

        # ── 8. 组装每股明细 ──────────────────────────────
        per_stock = []
        for code in valid_codes:
            pos = positions[code]
            last_bar = price_lut[code].get(all_sim_dates[-1]) or {}
            last_price = last_bar.get("close", pos["avg_cost"])
            unreal = round((last_price - pos["avg_cost"]) * pos["qty"], 2) if pos["qty"] > 0 else 0.0
            st = trade_stats[code]
            per_stock.append(StockSimDetail(
                stock_code=code,
                strategy=strategy_map[code]["strategy"],
                strategy_label=strategy_map[code]["label"],
                confidence=round(strategy_map[code].get("confidence", 0.0), 1),
                total_trades=st["total"],
                win_trades=st["wins"],
                win_rate=round(st["wins"] / st["total"] * 100 if st["total"] > 0 else 0.0, 2),
                total_fees=round(st["fees"], 2),
                realized_profit=round(st["realized"], 2),
                unrealized_profit=unreal,
                final_qty=pos["qty"],
                final_price=last_price,
            ))

        return OfflineSimResult(
            start_date=cfg.start_date,
            end_date=cfg.end_date,
            training_period=f"{train_start} ~ {cfg.start_date}",
            initial_capital=cfg.initial_capital,
            stock_codes=valid_codes,
            final_capital=round(final_capital, 2),
            total_return=round(total_return, 2),
            total_return_pct=total_return_pct,
            annualized_return_pct=ann_ret,
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 4),
            win_rate=win_rate,
            total_trades=total_trades,
            win_trades=win_trades,
            total_fees=total_fees,
            benchmarks=bm_results,
            alpha_summary=alpha_summary,
            portfolio_curve=equity_curve,
            strategy_map=strategy_map,
            per_stock=per_stock,
            trades=trade_records[:500],  # 最多返回500条，防止响应过大
        )

    # ══════════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════════

    async def _fetch_kline(self, code: str, bars: int) -> List[dict]:
        """拉取 K 线，自动尝试多个 datalen（最多支持约10年历史）"""
        # 最大2500条，约覆盖10年历史；按需降级
        cap = min(bars, 2500)
        for datalen in sorted({cap, min(cap, 1500), 800, 400}, reverse=True):
            kline = await self.adapter.get_kline_data(code, scale=240, datalen=datalen)
            if kline and len(kline) >= 60:
                return kline
        return []

    def _select_strategies(
        self,
        codes: List[str],
        stock_klines: Dict[str, List[dict]],
        train_start: str,
        train_end: str,
        train_ratio: float,
    ) -> Dict[str, dict]:
        """在训练期对每只股票做 Walk-Forward，选置信度最高的策略"""
        strategy_map = {}
        for code in codes:
            kline = stock_klines[code]
            # 只取训练期内的 K 线
            train_kline = [k for k in kline if train_start <= k["date"][:10] <= train_end]
            if len(train_kline) < 60:
                # 训练数据不足，用全量
                train_kline = kline
                logger.warning(f"[OfflineSim] {code} 训练期数据不足，使用全量 {len(train_kline)} bars")

            s_start = train_kline[0]["date"][:10]
            s_end = train_kline[-1]["date"][:10]
            params = StrategyTestParams(
                stock_code=code,
                start_date=s_start,
                end_date=s_end,
                train_ratio=train_ratio,
                initial_capital=1_000_000.0,
            )
            try:
                result = self.strategy_test_svc.run_test_with_kline(params, kline, code)
            except Exception as e:
                logger.warning(f"[OfflineSim] {code} 策略测试异常: {e}")
                result = None

            if result and result.items:
                best = result.items[0]
                # 找对应的 short/long window
                sw, lw = 0, 0
                for s, s_w, l_w, lbl in BACKTEST_STRATEGIES:
                    if s == best.strategy and lbl == best.strategy_label:
                        sw, lw = s_w, l_w
                        break
                strategy_map[code] = {
                    "strategy": best.strategy,
                    "label": best.strategy_label,
                    "short_window": sw,
                    "long_window": lw,
                    "confidence": round(best.confidence_score, 1),
                    "train_return_pct": round(best.train_return_pct, 2),
                    "test_return_pct": round(best.actual_return_pct, 2),
                    "test_alpha_pct": round(best.test_alpha_pct, 2),
                    "train_period": f"{best.train_start}~{best.train_end}",
                    "test_period": f"{best.test_start}~{best.test_end}",
                }
            else:
                # 默认用 MACD
                strategy_map[code] = {
                    "strategy": "macd", "label": "MACD",
                    "short_window": 12, "long_window": 26,
                    "confidence": 0.0, "train_return_pct": 0.0,
                    "test_return_pct": 0.0, "test_alpha_pct": 0.0,
                    "train_period": "", "test_period": "",
                }
        return strategy_map

    def _build_regime_lut(
        self,
        kline: List[dict],
        sim_start: str,
        sim_end: str,
        ma_days: int = 20,
    ) -> Dict[str, bool]:
        """
        根据指数 K 线构建市场环境查询表：{日期: 是否高于N日均线}
        True = 允许开新多仓，False = 禁止开仓
        """
        if not kline or len(kline) < ma_days:
            return {}
        closes = [k["close"] for k in kline]
        dates = [k["date"][:10] for k in kline]
        result: Dict[str, bool] = {}
        for i in range(ma_days - 1, len(closes)):
            date = dates[i]
            if sim_start <= date <= sim_end:
                ma = sum(closes[i - ma_days + 1 : i + 1]) / ma_days
                result[date] = closes[i] >= ma
        return result

    def _precompute_signals(self, kline: List[dict], strategy_info: dict) -> Dict[str, str]:
        """
        在完整 K 线上跑一遍信号生成，返回 {日期: BUY/SELL}。
        只保留模拟期内的信号。
        """
        closes = [k["close"] for k in kline]
        ctx = {"closes": closes}
        strategy = strategy_info["strategy"]
        sw = strategy_info.get("short_window", 0)
        lw = strategy_info.get("long_window", 0)
        try:
            raw = self.backtest_svc._generate_signals(strategy, kline, ctx, sw, lw)
        except Exception as e:
            logger.warning(f"[OfflineSim] _precompute_signals {strategy}: {e}")
            raw = []
        return {kline[idx]["date"][:10]: action for idx, action in raw}

    async def _calc_benchmarks(
        self,
        benchmark_codes: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        needed_bars: int,
    ) -> List[BenchmarkResult]:
        results = []
        for raw_code in benchmark_codes:
            fetch_code, name = _resolve_benchmark(raw_code)
            try:
                kline = await self._fetch_kline(fetch_code, needed_bars)
                if not kline:
                    logger.warning(f"[OfflineSim] 基准 {name}({fetch_code}) 数据为空，跳过")
                    continue

                # 过滤到模拟期
                sim_bars = [k for k in kline if start_date <= k["date"][:10] <= end_date]
                if len(sim_bars) < 5:
                    logger.warning(f"[OfflineSim] 基准 {name} 模拟期数据不足")
                    continue

                start_price = sim_bars[0]["close"]
                end_price = sim_bars[-1]["close"]
                ret_pct = round((end_price - start_price) / start_price * 100, 2)

                # 权益曲线（等比例放大）
                curve = [
                    EquityPoint(
                        date=k["date"][:10],
                        value=round(initial_capital * k["close"] / start_price, 2),
                    )
                    for k in sim_bars
                ]
                results.append(BenchmarkResult(
                    code=fetch_code, name=name,
                    start_price=start_price, end_price=end_price,
                    total_return_pct=ret_pct,
                    curve=curve,
                ))
                logger.info(f"[OfflineSim] 基准 {name}: {ret_pct:+.2f}%")
            except Exception as e:
                logger.warning(f"[OfflineSim] 基准 {name} 计算失败: {e}")
        return results

    # ── 统计指标 ──────────────────────────────────────────

    @staticmethod
    def _max_drawdown(equity: List[float]) -> float:
        if not equity:
            return 0.0
        peak, max_dd = equity[0], 0.0
        for v in equity:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _sharpe(equity: List[float], rf_annual: float = 0.025) -> float:
        """年化 Sharpe（日频）"""
        if len(equity) < 10:
            return 0.0
        daily_ret = [
            (equity[i] - equity[i - 1]) / equity[i - 1]
            for i in range(1, len(equity))
            if equity[i - 1] > 0
        ]
        if len(daily_ret) < 5:
            return 0.0
        rf_daily = rf_annual / 252
        excess = [r - rf_daily for r in daily_ret]
        avg = sum(excess) / len(excess)
        std = (sum((r - avg) ** 2 for r in excess) / len(excess)) ** 0.5
        if std < 1e-10:
            return 0.0
        return round(avg / std * math.sqrt(252), 4)

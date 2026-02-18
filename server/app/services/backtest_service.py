"""
回测服务 v3
架构：信号生成 / 交易执行 完全分离
- 策略只输出原始 buy/sell 信号
- 统一执行引擎负责：仓位管理、趋势过滤、量能确认、止损/移动止盈、冷却期
- 指标在完整 K 线上计算（含 warmup），交易区间只在用户指定日期内
"""

import math
import uuid
from typing import List, Optional, Tuple, Dict
from loguru import logger

from app.schemas.backtest import BacktestParams, BacktestResult, BacktestTrade, PricePoint
from app.adapters.market.sina_adapter import SinaAdapter

# ==================== 全局参数 ====================
STOP_LOSS_PCT = 0.07
TRAILING_STOP_PCT = 0.18
COOLDOWN_BARS = 2
ATR_PERIOD = 14
ATR_STOP_MULT = 1.5
RISK_PER_TRADE = 0.04
MAX_POSITION_PCT = 0.95
TREND_MA_LEN = 40
VOLUME_MA_LEN = 20
LOT_SIZE = 100


class BacktestService:
    """回测服务"""

    def __init__(self):
        self.adapter = SinaAdapter()

    # ==================== 公开接口 ====================

    async def run_backtest(self, params: BacktestParams) -> Optional[BacktestResult]:
        """运行回测（自动获取数据）"""
        try:
            logger.info(f"Running backtest: {params.stock_code} / {params.strategy}")
            from datetime import datetime
            try:
                d_start = datetime.strptime(params.start_date, "%Y-%m-%d")
                d_end = datetime.strptime(params.end_date, "%Y-%m-%d")
                days_span = (d_end - d_start).days
            except ValueError:
                days_span = 600
            needed = max(400, int(days_span * 0.75) + TREND_MA_LEN + ATR_PERIOD + 50)

            kline_data = await self.adapter.get_kline_data(
                params.stock_code, scale=240, datalen=needed
            )
            if not kline_data:
                logger.warning(f"No kline data for {params.stock_code}, skip")
                return None

            return self._run_backtest_on_kline(params, kline_data)
        except Exception as e:
            logger.error(f"Run backtest error: {e}")
            raise

    def run_backtest_sync(
        self, params: BacktestParams, kline_data: List[dict]
    ) -> Optional[BacktestResult]:
        """使用已有 K 线数据运行回测（批量场景，无网络）"""
        if not kline_data:
            return None
        try:
            return self._run_backtest_on_kline(params, kline_data)
        except Exception as e:
            logger.warning(f"Backtest sync error {params.stock_code}/{params.strategy}: {e}")
            return None

    # ==================== 核心引擎 ====================

    def _run_backtest_on_kline(
        self, params: BacktestParams, kline_data: List[dict]
    ) -> Optional[BacktestResult]:
        # 用户参数覆盖默认值
        cfg = {
            "stop_loss_pct": params.stop_loss_pct if params.stop_loss_pct is not None else STOP_LOSS_PCT,
            "trailing_stop_pct": params.trailing_stop_pct if params.trailing_stop_pct is not None else TRAILING_STOP_PCT,
            "risk_per_trade": params.risk_per_trade if params.risk_per_trade is not None else RISK_PER_TRADE,
            "max_position_pct": params.max_position_pct if params.max_position_pct is not None else MAX_POSITION_PCT,
            "trend_ma_len": params.trend_ma_len if params.trend_ma_len is not None else TREND_MA_LEN,
            "cooldown_bars": params.cooldown_bars if params.cooldown_bars is not None else COOLDOWN_BARS,
            "atr_period": ATR_PERIOD,
            "atr_stop_mult": ATR_STOP_MULT,
            "volume_ma_len": VOLUME_MA_LEN,
        }

        # 找到交易区间起止 index（保留前面的 warmup 数据给指标计算用）
        trade_start = 0
        trade_end = len(kline_data) - 1
        for idx, k in enumerate(kline_data):
            d = k["date"][:10]
            if d >= params.start_date and trade_start == 0:
                trade_start = idx
            if d <= params.end_date:
                trade_end = idx

        warmup_needed = max(cfg["trend_ma_len"], cfg["atr_period"], cfg["volume_ma_len"],
                            params.long_window, params.short_window, 30) + 5
        if trade_start < warmup_needed:
            trade_start = warmup_needed
        if trade_end <= trade_start + 10:
            logger.warning(f"Insufficient trade range for {params.stock_code}")
            return None

        closes = [k["close"] for k in kline_data]
        highs = [k["high"] for k in kline_data]
        lows = [k["low"] for k in kline_data]
        volumes = [k["volume"] for k in kline_data]

        atr = self._compute_atr(highs, lows, closes, cfg["atr_period"])
        vol_ma = self._sma(volumes, cfg["volume_ma_len"])
        trend_ma = self._sma(closes, cfg["trend_ma_len"])

        ctx: Dict = {
            "closes": closes, "highs": highs, "lows": lows, "volumes": volumes,
            "atr": atr, "vol_ma": vol_ma, "trend_ma": trend_ma,
            "trade_start": trade_start, "trade_end": trade_end,
            "cfg": cfg,
        }

        raw_signals = self._generate_signals(
            params.strategy, kline_data, ctx, params.short_window, params.long_window
        )

        trades = self._execute(kline_data, raw_signals, ctx, params.initial_capital)

        return self._calculate_metrics(params, kline_data, trades, ctx)

    # ==================== 信号生成 ====================

    def _generate_signals(
        self, strategy: str, kline: List[dict], ctx: Dict,
        short_w: int, long_w: int
    ) -> List[Tuple[int, str]]:
        dispatch = {
            "ma_cross": lambda: self._sig_ma_cross(ctx["closes"], short_w, long_w),
            "macd": lambda: self._sig_macd(ctx["closes"]),
            "kdj": lambda: self._sig_kdj(kline),
            "rsi": lambda: self._sig_rsi(ctx["closes"], short_w or 14),
            "bollinger": lambda: self._sig_bollinger(ctx["closes"], long_w or 20),
        }
        fn = dispatch.get(strategy, lambda: self._sig_ma_cross(ctx["closes"], short_w, long_w))
        return fn()

    def _sig_ma_cross(self, closes: List[float], short: int, long: int) -> List[Tuple[int, str]]:
        signals: List[Tuple[int, str]] = []
        for i in range(long + 1, len(closes)):
            ma_s = sum(closes[i - short:i]) / short
            ma_l = sum(closes[i - long:i]) / long
            prev_s = sum(closes[i - short - 1:i - 1]) / short
            prev_l = sum(closes[i - long - 1:i - 1]) / long
            if prev_s <= prev_l and ma_s > ma_l:
                signals.append((i, "BUY"))
            elif prev_s >= prev_l and ma_s < ma_l:
                signals.append((i, "SELL"))
        return signals

    def _sig_macd(self, closes: List[float]) -> List[Tuple[int, str]]:
        signals: List[Tuple[int, str]] = []
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        dif = [ema12[i] - ema26[i] for i in range(len(closes))]
        dea = self._ema(dif, 9)
        hist = [dif[i] - dea[i] for i in range(len(closes))]
        for i in range(27, len(closes)):
            if hist[i] > 0 and hist[i - 1] <= 0:
                signals.append((i, "BUY"))
            elif hist[i] < 0 and hist[i - 1] >= 0:
                signals.append((i, "SELL"))
        return signals

    def _sig_kdj(self, kline: List[dict]) -> List[Tuple[int, str]]:
        """KDJ: K 上穿 D 且 J < 30 买入；K 下穿 D 且 J > 70 卖出"""
        signals: List[Tuple[int, str]] = []
        closes = [k["close"] for k in kline]
        highs = [k["high"] for k in kline]
        lows = [k["low"] for k in kline]
        n = 9
        k_val, d_val = 50.0, 50.0
        prev_k, prev_d = 50.0, 50.0

        for i in range(n, len(closes)):
            wh = max(highs[i - n + 1:i + 1])
            wl = min(lows[i - n + 1:i + 1])
            rsv = (closes[i] - wl) / (wh - wl) * 100 if wh != wl else 50
            k_val = 2 / 3 * k_val + 1 / 3 * rsv
            d_val = 2 / 3 * d_val + 1 / 3 * k_val
            j_val = 3 * k_val - 2 * d_val

            if prev_k <= prev_d and k_val > d_val and j_val < 40:
                signals.append((i, "BUY"))
            elif prev_k >= prev_d and k_val < d_val and j_val > 60:
                signals.append((i, "SELL"))

            prev_k, prev_d = k_val, d_val
        return signals

    def _sig_rsi(self, closes: List[float], period: int) -> List[Tuple[int, str]]:
        """RSI: Wilder 平滑法，超卖(<30)买入，超买(>70)卖出"""
        signals: List[Tuple[int, str]] = []
        if len(closes) < period + 2:
            return signals

        avg_gain = 0.0
        avg_loss = 0.0
        for j in range(1, period + 1):
            d = closes[j] - closes[j - 1]
            if d > 0:
                avg_gain += d
            else:
                avg_loss -= d
        avg_gain /= period
        avg_loss /= period

        prev_rsi = 50.0
        for i in range(period + 1, len(closes)):
            d = closes[i] - closes[i - 1]
            gain = d if d > 0 else 0
            loss = -d if d < 0 else 0
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - 100 / (1 + rs)

            if prev_rsi >= 35 and rsi < 35:
                signals.append((i, "BUY"))
            elif prev_rsi <= 65 and rsi > 65:
                signals.append((i, "SELL"))
            prev_rsi = rsi
        return signals

    def _sig_bollinger(self, closes: List[float], period: int) -> List[Tuple[int, str]]:
        """Bollinger: 收盘从下轨外回到下轨内买入，从上轨内突破上轨卖出"""
        signals: List[Tuple[int, str]] = []
        for i in range(period + 1, len(closes)):
            window = closes[i - period:i]
            ma = sum(window) / period
            std = (sum((c - ma) ** 2 for c in window) / period) ** 0.5
            upper = ma + 2 * std
            lower = ma - 2 * std

            prev_window = closes[i - period - 1:i - 1]
            prev_ma = sum(prev_window) / period
            prev_std = (sum((c - prev_ma) ** 2 for c in prev_window) / period) ** 0.5
            prev_lower = prev_ma - 2 * prev_std
            prev_upper = prev_ma + 2 * prev_std

            if closes[i - 1] <= prev_lower and closes[i] > lower:
                signals.append((i, "BUY"))
            elif closes[i - 1] < prev_upper and closes[i] >= upper:
                signals.append((i, "SELL"))
        return signals

    # ==================== 统一执行引擎 ====================

    def _execute(
        self, kline: List[dict], raw_signals: List[Tuple[int, str]],
        ctx: Dict, initial_capital: float,
    ) -> List[BacktestTrade]:
        closes = ctx["closes"]
        atr = ctx["atr"]
        vol_ma = ctx["vol_ma"]
        trend_ma = ctx["trend_ma"]
        trade_start = ctx["trade_start"]
        trade_end = ctx["trade_end"]
        cfg = ctx["cfg"]

        signal_map: Dict[int, str] = {}
        for idx, action in raw_signals:
            if trade_start <= idx <= trade_end:
                signal_map[idx] = action

        trades: List[BacktestTrade] = []
        avail_capital = initial_capital
        holding = False
        buy_price = 0.0
        peak_price = 0.0
        qty = 0
        cooldown = 0

        for i in range(trade_start, trade_end + 1):
            if cooldown > 0:
                cooldown -= 1

            if holding:
                peak_price = max(peak_price, closes[i])

                atr_stop = buy_price - atr[i] * cfg["atr_stop_mult"] if atr[i] > 0 else 0
                fixed_stop = buy_price * (1 - cfg["stop_loss_pct"])
                stop_price = max(atr_stop, fixed_stop)

                trailing_stop_price = peak_price * (1 - cfg["trailing_stop_pct"])

                if closes[i] <= stop_price:
                    profit = (closes[i] - buy_price) * qty
                    avail_capital += closes[i] * qty
                    trades.append(BacktestTrade(
                        date=kline[i]["date"][:10], action="SELL",
                        price=closes[i], quantity=qty, profit=round(profit, 2),
                    ))
                    holding = False
                    cooldown = cfg["cooldown_bars"]
                    continue
                elif closes[i] <= trailing_stop_price and closes[i] > buy_price:
                    profit = (closes[i] - buy_price) * qty
                    avail_capital += closes[i] * qty
                    trades.append(BacktestTrade(
                        date=kline[i]["date"][:10], action="SELL",
                        price=closes[i], quantity=qty, profit=round(profit, 2),
                    ))
                    holding = False
                    continue

            sig = signal_map.get(i)
            if not sig:
                continue

            if sig == "BUY" and not holding and cooldown <= 0:
                if trend_ma[i] > 0 and closes[i] < trend_ma[i]:
                    continue
                if vol_ma[i] > 0 and ctx["volumes"][i] < vol_ma[i] * 0.5:
                    continue

                qty = self._calc_qty(avail_capital, closes[i], atr[i], cfg)
                if qty <= 0:
                    continue

                avail_capital -= closes[i] * qty
                buy_price = closes[i]
                peak_price = closes[i]
                trades.append(BacktestTrade(
                    date=kline[i]["date"][:10], action="BUY",
                    price=closes[i], quantity=qty,
                ))
                holding = True

            elif sig == "SELL" and holding:
                profit = (closes[i] - buy_price) * qty
                avail_capital += closes[i] * qty
                trades.append(BacktestTrade(
                    date=kline[i]["date"][:10], action="SELL",
                    price=closes[i], quantity=qty, profit=round(profit, 2),
                ))
                holding = False

        return trades

    # ==================== 仓位管理 ====================

    @staticmethod
    def _calc_qty(capital: float, price: float, atr_val: float, cfg: Dict) -> int:
        """ATR 仓位管理：单笔风险 = risk_per_trade × 资金"""
        if price <= 0:
            return 0
        cap_limit = capital * cfg["max_position_pct"]

        if atr_val > 0:
            risk_amount = capital * cfg["risk_per_trade"]
            stop_dist = atr_val * cfg["atr_stop_mult"]
            risk_qty = int(risk_amount / stop_dist) if stop_dist > 0 else 0
            cap_qty = int(cap_limit / price)
            raw = min(risk_qty, cap_qty)
        else:
            raw = int(cap_limit / price)

        lots = raw // LOT_SIZE
        return lots * LOT_SIZE

    # ==================== 指标计算 ====================

    @staticmethod
    def _sma(data: List[float], period: int) -> List[float]:
        result = [0.0] * len(data)
        for i in range(period - 1, len(data)):
            result[i] = sum(data[i - period + 1:i + 1]) / period
        return result

    def _ema(self, data: List[float], period: int) -> List[float]:
        result = [0.0] * len(data)
        m = 2 / (period + 1)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = (data[i] - result[i - 1]) * m + result[i - 1]
        return result

    @staticmethod
    def _compute_atr(
        highs: List[float], lows: List[float], closes: List[float], period: int
    ) -> List[float]:
        n = len(closes)
        tr = [0.0] * n
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        atr = [0.0] * n
        if n >= period:
            atr[period - 1] = sum(tr[:period]) / period
            for i in range(period, n):
                atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        return atr

    # ==================== 指标 & 评估 ====================

    def _calculate_metrics(
        self, params: BacktestParams, kline: List[dict],
        trades: List[BacktestTrade], ctx: Dict,
    ) -> BacktestResult:
        trade_start = ctx["trade_start"]
        trade_end = ctx["trade_end"]
        closes = ctx["closes"]

        # 构建逐日权益曲线
        capital = params.initial_capital
        holding_qty = 0
        buy_price = 0.0
        trade_idx = 0
        wins = 0
        losses_cnt = 0

        equity_curve: List[float] = []

        for i in range(trade_start, trade_end + 1):
            while trade_idx < len(trades) and trades[trade_idx].date == kline[i]["date"][:10]:
                t = trades[trade_idx]
                if t.action == "BUY":
                    capital -= t.price * t.quantity
                    holding_qty += t.quantity
                    buy_price = t.price
                elif t.action == "SELL":
                    capital += t.price * t.quantity
                    holding_qty -= t.quantity
                    if t.profit is not None:
                        if t.profit > 0:
                            wins += 1
                        else:
                            losses_cnt += 1
                trade_idx += 1

            equity = capital + holding_qty * closes[i]
            equity_curve.append(equity)

        if not equity_curve:
            equity_curve = [params.initial_capital]

        # 最终权益
        final_equity = equity_curve[-1]
        total_return = final_equity - params.initial_capital
        total_return_pct = (total_return / params.initial_capital * 100) if params.initial_capital > 0 else 0

        # 最大回撤（逐日）
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        total_trades = sum(1 for t in trades if t.action == "SELL")
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # Sharpe（基于策略权益曲线日收益）
        sharpe = 0.0
        if len(equity_curve) > 2:
            daily_ret = [
                (equity_curve[j] - equity_curve[j - 1]) / equity_curve[j - 1]
                for j in range(1, len(equity_curve))
                if equity_curve[j - 1] > 0
            ]
            if len(daily_ret) > 5:
                avg_r = sum(daily_ret) / len(daily_ret)
                std_r = (sum((r - avg_r) ** 2 for r in daily_ret) / len(daily_ret)) ** 0.5
                sharpe = (avg_r / std_r * math.sqrt(252)) if std_r > 0 else 0

        # 每日收盘价序列（供前端画走势图），每 N 天取一个点控制数据量
        raw_count = trade_end - trade_start + 1
        sample_step = max(1, raw_count // 250)
        price_series: List[PricePoint] = []
        for i in range(trade_start, trade_end + 1, sample_step):
            price_series.append(PricePoint(date=kline[i]["date"][:10], close=closes[i]))
        if (trade_end - trade_start) % sample_step != 0:
            price_series.append(PricePoint(date=kline[trade_end]["date"][:10], close=closes[trade_end]))

        return BacktestResult(
            id=str(uuid.uuid4()),
            stock_code=params.stock_code,
            strategy=params.strategy,
            start_date=params.start_date,
            end_date=params.end_date,
            initial_capital=params.initial_capital,
            final_capital=round(final_equity, 2),
            total_return=round(total_return, 2),
            total_return_percent=round(total_return_pct, 2),
            max_drawdown=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 4),
            win_rate=round(win_rate, 2),
            total_trades=total_trades,
            trades=trades,
            price_series=price_series,
        )

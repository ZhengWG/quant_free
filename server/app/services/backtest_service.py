"""
回测服务
"""

import math
import uuid
from typing import List, Optional
from loguru import logger

from app.schemas.backtest import BacktestParams, BacktestResult, BacktestTrade
from app.adapters.market.sina_adapter import SinaAdapter


class BacktestService:
    """回测服务"""

    def __init__(self):
        self.adapter = SinaAdapter()

    async def run_backtest(self, params: BacktestParams) -> Optional[BacktestResult]:
        """运行回测，如果数据不足返回 None"""
        try:
            logger.info(f"Running backtest: {params.stock_code} / {params.strategy}")

            # 根据日期范围估算所需数据量
            from datetime import datetime, timedelta
            try:
                d_start = datetime.strptime(params.start_date, "%Y-%m-%d")
                d_end = datetime.strptime(params.end_date, "%Y-%m-%d")
                days_span = (d_end - d_start).days
            except ValueError:
                days_span = 600
            needed = max(300, int(days_span * 0.75) + params.long_window + 50)

            # 获取历史K线数据
            kline_data = await self.adapter.get_kline_data(
                params.stock_code, scale=240, datalen=needed
            )

            if not kline_data:
                logger.warning(f"No kline data for {params.stock_code}, skip backtest")
                return None

            # 过滤日期范围
            filtered = [
                k for k in kline_data
                if params.start_date <= k["date"][:10] <= params.end_date
            ]

            if len(filtered) < params.long_window + 1:
                logger.warning(
                    f"Insufficient data for {params.stock_code}: "
                    f"{len(filtered)} records, need at least {params.long_window + 1}"
                )
                return None

            # 运行策略
            if params.strategy == "ma_cross":
                trades = self._ma_cross_strategy(
                    filtered, params.short_window, params.long_window
                )
            elif params.strategy == "macd":
                trades = self._macd_strategy(filtered)
            else:
                trades = self._ma_cross_strategy(
                    filtered, params.short_window, params.long_window
                )

            # 计算回测指标
            result = self._calculate_metrics(
                params, filtered, trades
            )

            return result
        except Exception as e:
            logger.error(f"Run backtest error: {e}")
            raise

    def _ma_cross_strategy(
        self, kline: List[dict], short: int, long: int
    ) -> List[BacktestTrade]:
        """双均线交叉策略"""
        trades = []
        closes = [k["close"] for k in kline]
        holding = False

        for i in range(long, len(closes)):
            ma_short = sum(closes[i - short:i]) / short
            ma_long = sum(closes[i - long:i]) / long
            prev_ma_short = sum(closes[i - short - 1:i - 1]) / short
            prev_ma_long = sum(closes[i - long - 1:i - 1]) / long

            # 金叉买入
            if prev_ma_short <= prev_ma_long and ma_short > ma_long and not holding:
                trades.append(BacktestTrade(
                    date=kline[i]["date"][:10],
                    action="BUY",
                    price=closes[i],
                    quantity=100,
                ))
                holding = True
            # 死叉卖出
            elif prev_ma_short >= prev_ma_long and ma_short < ma_long and holding:
                buy_price = trades[-1].price if trades else closes[i]
                profit = (closes[i] - buy_price) * 100
                trades.append(BacktestTrade(
                    date=kline[i]["date"][:10],
                    action="SELL",
                    price=closes[i],
                    quantity=100,
                    profit=round(profit, 2),
                ))
                holding = False

        return trades

    def _macd_strategy(self, kline: List[dict]) -> List[BacktestTrade]:
        """MACD策略"""
        closes = [k["close"] for k in kline]
        trades = []
        holding = False

        # 计算EMA
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)

        # MACD = EMA12 - EMA26
        dif = [ema12[i] - ema26[i] for i in range(len(closes))]
        # Signal line (DEA) = EMA9 of DIF
        dea = self._ema(dif, 9)
        # MACD histogram
        macd = [dif[i] - dea[i] for i in range(len(closes))]

        for i in range(27, len(closes)):
            # MACD 金叉
            if macd[i] > 0 and macd[i - 1] <= 0 and not holding:
                trades.append(BacktestTrade(
                    date=kline[i]["date"][:10],
                    action="BUY",
                    price=closes[i],
                    quantity=100,
                ))
                holding = True
            # MACD 死叉
            elif macd[i] < 0 and macd[i - 1] >= 0 and holding:
                buy_price = trades[-1].price if trades else closes[i]
                profit = (closes[i] - buy_price) * 100
                trades.append(BacktestTrade(
                    date=kline[i]["date"][:10],
                    action="SELL",
                    price=closes[i],
                    quantity=100,
                    profit=round(profit, 2),
                ))
                holding = False

        return trades

    def _ema(self, data: List[float], period: int) -> List[float]:
        """计算指数移动平均"""
        result = [0.0] * len(data)
        multiplier = 2 / (period + 1)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    def _calculate_metrics(
        self,
        params: BacktestParams,
        kline: List[dict],
        trades: List[BacktestTrade],
    ) -> BacktestResult:
        """计算回测指标"""
        capital = params.initial_capital
        peak_capital = capital
        max_drawdown = 0.0
        wins = 0
        losses = 0
        daily_returns = []

        # 逐笔计算
        for t in trades:
            if t.action == "BUY":
                capital -= t.price * t.quantity
            elif t.action == "SELL":
                capital += t.price * t.quantity
                if t.profit and t.profit > 0:
                    wins += 1
                elif t.profit and t.profit <= 0:
                    losses += 1

            # 最大回撤
            if capital > peak_capital:
                peak_capital = capital
            drawdown = (peak_capital - capital) / peak_capital * 100 if peak_capital > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 如果还持有未平仓，用最后一日收盘价计算
        open_buys = sum(1 for t in trades if t.action == "BUY") - sum(1 for t in trades if t.action == "SELL")
        if open_buys > 0 and kline:
            last_close = kline[-1]["close"]
            capital += last_close * 100 * open_buys

        final_capital = capital
        total_return = final_capital - params.initial_capital
        total_return_pct = (total_return / params.initial_capital * 100) if params.initial_capital > 0 else 0
        total_trades = len([t for t in trades if t.action == "SELL"])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # 简化的夏普比率估算
        if total_trades > 0 and kline:
            closes = [k["close"] for k in kline]
            for i in range(1, len(closes)):
                daily_returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
            avg_ret = sum(daily_returns) / len(daily_returns) if daily_returns else 0
            std_ret = (
                math.sqrt(sum((r - avg_ret) ** 2 for r in daily_returns) / len(daily_returns))
                if daily_returns else 1
            )
            sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0
        else:
            sharpe = 0

        return BacktestResult(
            id=str(uuid.uuid4()),
            stock_code=params.stock_code,
            strategy=params.strategy,
            start_date=params.start_date,
            end_date=params.end_date,
            initial_capital=params.initial_capital,
            final_capital=round(final_capital, 2),
            total_return=round(total_return, 2),
            total_return_percent=round(total_return_pct, 2),
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=round(sharpe, 4),
            win_rate=round(win_rate, 2),
            total_trades=total_trades,
            trades=trades,
        )

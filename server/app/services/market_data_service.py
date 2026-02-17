"""
行情数据服务
"""

from typing import List
from datetime import datetime
from loguru import logger

from app.schemas.market import Stock, KLineData, HistoryData
from app.adapters.market.sina_adapter import SinaAdapter


class MarketDataService:
    """行情数据服务"""

    def __init__(self):
        self.adapter = SinaAdapter()

    async def get_realtime_data(self, codes: List[str]) -> List[Stock]:
        """获取实时行情数据"""
        try:
            logger.info(f"Getting realtime data for codes: {codes}")
            raw_data = await self.adapter.get_realtime_data(codes)

            stocks = []
            for item in raw_data:
                try:
                    ts = item.get("timestamp", "")
                    if isinstance(ts, str):
                        try:
                            timestamp = datetime.fromisoformat(ts)
                        except ValueError:
                            try:
                                timestamp = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()

                    stock = Stock(
                        code=item["code"],
                        name=item["name"],
                        market=item["market"],
                        price=item["price"],
                        change=item["change"],
                        change_percent=item["change_percent"],
                        volume=item["volume"],
                        amount=item["amount"],
                        high=item["high"],
                        low=item["low"],
                        open=item["open"],
                        pre_close=item["pre_close"],
                        timestamp=timestamp,
                    )
                    stocks.append(stock)
                except Exception as e:
                    logger.error(f"Parse stock item error: {e}, data: {item}")
                    continue

            return stocks
        except Exception as e:
            logger.error(f"Get realtime data error: {e}")
            raise

    async def get_history_data(self, code: str, period: str = "1d") -> List[HistoryData]:
        """获取历史数据"""
        try:
            raw_data = await self.adapter.get_history_data(code, period)
            return [HistoryData(**item) for item in raw_data]
        except Exception as e:
            logger.error(f"Get history data error: {e}")
            raise

    async def get_kline_data(self, code: str, type: str = "day") -> List[KLineData]:
        """获取K线数据"""
        try:
            scale_map = {"5min": 5, "15min": 15, "30min": 30, "60min": 60, "day": 240}
            scale = scale_map.get(type, 240)
            raw_data = await self.adapter.get_kline_data(code, scale=scale, datalen=100)
            return [KLineData(**item) for item in raw_data]
        except Exception as e:
            logger.error(f"Get kline data error: {e}")
            raise

"""
Tushare行情数据适配器
"""

from loguru import logger
from app.core.config import settings


class TushareAdapter:
    """Tushare适配器"""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        if not self.token:
            logger.warning("TUSHARE_TOKEN not set, using mock data")
    
    async def get_realtime_data(self, codes: list):
        """获取实时数据"""
        # TODO: 实现Tushare API调用
        logger.info(f"Getting realtime data from Tushare: {codes}")
        return []
    
    async def get_kline_data(self, code: str, type: str = "day"):
        """获取K线数据"""
        # TODO: 实现K线数据获取
        return []
    
    async def get_history_data(self, code: str, period: str = "1d"):
        """获取历史数据"""
        # TODO: 实现历史数据获取
        return []


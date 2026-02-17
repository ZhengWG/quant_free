"""
行情数据适配器
- 实时数据: 新浪财经API (免费，无需Token)
- K线/历史数据: 腾讯财经API (免费，无需Token)
支持A股、港股实时行情
"""

import re
import httpx
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger


class SinaAdapter:
    """行情数据适配器（新浪实时 + 腾讯K线）"""

    # 新浪行情API（实时数据）
    REALTIME_URL = "https://hq.sinajs.cn/list="
    # 腾讯K线API
    TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self):
        self.headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

    def _normalize_code(self, code: str) -> str:
        """
        将股票代码标准化为新浪/腾讯格式 (sh/sz前缀)
        """
        code = code.strip()

        if code.startswith(("sh", "sz")):
            return code.lower()

        if code.upper().startswith("HK"):
            return "hk" + code[2:]

        if code.isdigit() and len(code) == 6:
            if code.startswith(("6", "9")):
                return f"sh{code}"
            else:
                return f"sz{code}"

        if code.isalpha():
            return f"gb_{code.lower()}"

        return code.lower()

    def _detect_market(self, sina_code: str) -> str:
        if sina_code.startswith(("sh", "sz")):
            return "A股"
        elif sina_code.startswith("hk"):
            return "港股"
        elif sina_code.startswith("gb_"):
            return "美股"
        return "未知"

    def _parse_ashare_line(self, line: str) -> Optional[Dict]:
        """解析A股实时行情"""
        match = re.match(r'var hq_str_(\w+)="(.*)";', line)
        if not match:
            return None

        sina_code = match.group(1)
        data_str = match.group(2)
        if not data_str:
            return None

        parts = data_str.split(",")
        if len(parts) < 32:
            return None

        try:
            name = parts[0]
            open_price = float(parts[1])
            pre_close = float(parts[2])
            price = float(parts[3])
            high = float(parts[4])
            low = float(parts[5])
            volume = float(parts[8])
            amount = float(parts[9])
            date_str = parts[30]
            time_str = parts[31]

            change = round(price - pre_close, 2)
            change_pct = round(change / pre_close * 100, 2) if pre_close > 0 else 0.0

            raw_code = sina_code[2:] if sina_code.startswith(("sh", "sz")) else sina_code

            return {
                "code": raw_code,
                "name": name,
                "market": self._detect_market(sina_code),
                "price": price,
                "change": change,
                "change_percent": change_pct,
                "volume": volume,
                "amount": amount,
                "high": high,
                "low": low,
                "open": open_price,
                "pre_close": pre_close,
                "timestamp": f"{date_str} {time_str}" if date_str else datetime.now().isoformat(),
            }
        except (ValueError, IndexError) as e:
            logger.error(f"Parse A-share data error for {sina_code}: {e}")
            return None

    def _parse_hk_line(self, line: str) -> Optional[Dict]:
        """解析港股实时行情"""
        match = re.match(r'var hq_str_(\w+)="(.*)";', line)
        if not match:
            return None

        sina_code = match.group(1)
        data_str = match.group(2)
        if not data_str:
            return None

        parts = data_str.split(",")
        if len(parts) < 13:
            return None

        try:
            name_cn = parts[1]
            open_price = float(parts[2])
            pre_close = float(parts[3])
            high = float(parts[4])
            low = float(parts[5])
            price = float(parts[6])
            change = float(parts[7])
            change_pct = float(parts[8])
            volume = float(parts[12]) if len(parts) > 12 else 0
            amount = float(parts[11]) if len(parts) > 11 else 0

            raw_code = sina_code[2:]

            return {
                "code": raw_code,
                "name": name_cn,
                "market": "港股",
                "price": price,
                "change": change,
                "change_percent": change_pct,
                "volume": volume,
                "amount": amount,
                "high": high,
                "low": low,
                "open": open_price,
                "pre_close": pre_close,
                "timestamp": datetime.now().isoformat(),
            }
        except (ValueError, IndexError) as e:
            logger.error(f"Parse HK data error for {sina_code}: {e}")
            return None

    async def get_realtime_data(self, codes: List[str]) -> List[Dict]:
        """获取实时行情数据（新浪API）"""
        if not codes:
            return []

        sina_codes = [self._normalize_code(c) for c in codes]
        url = self.REALTIME_URL + ",".join(sina_codes)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                response.encoding = "gbk"
                text = response.text

            results = []
            for line in text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue

                if "hq_str_hk" in line:
                    data = self._parse_hk_line(line)
                else:
                    data = self._parse_ashare_line(line)

                if data:
                    results.append(data)

            logger.info(f"Sina realtime: fetched {len(results)}/{len(codes)} stocks")
            return results
        except Exception as e:
            logger.error(f"Sina get_realtime_data error: {e}")
            return []

    async def get_kline_data(self, code: str, scale: int = 240, datalen: int = 100) -> List[Dict]:
        """
        获取K线数据（腾讯财经API）
        :param code: 股票代码
        :param scale: 周期(分钟) 5/15/30/60/240(日K)
        :param datalen: 数据条数
        """
        tencent_code = self._normalize_code(code)

        # 周期映射
        period_map = {5: "m5", 15: "m15", 30: "m30", 60: "m60", 240: "day", 1200: "week", 7200: "month"}
        period = period_map.get(scale, "day")

        # 日期范围
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=datalen * 2)).strftime("%Y-%m-%d")

        url = f"{self.TENCENT_KLINE_URL}?param={tencent_code},{period},{start_date},{end_date},{datalen},qfq"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

            import json
            data = json.loads(response.text)

            if data.get("code") != 0:
                logger.warning(f"Tencent kline API error: {data}")
                return []

            stock_data = data.get("data", {}).get(tencent_code, {})
            # 腾讯API可能返回 "day" 或 "qfqday" (前复权)
            kline_list = stock_data.get(period, stock_data.get(f"qfq{period}", []))

            results = []
            for item in kline_list:
                # 格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
                if len(item) >= 6:
                    results.append({
                        "date": item[0],
                        "open": float(item[1]),
                        "high": float(item[3]),
                        "low": float(item[4]),
                        "close": float(item[2]),
                        "volume": float(item[5]),
                        "amount": 0.0,
                    })

            logger.info(f"Tencent kline: fetched {len(results)} records for {code} ({period})")
            return results
        except Exception as e:
            logger.error(f"Tencent get_kline_data error: {e}")
            return []

    async def get_history_data(self, code: str, period: str = "1d") -> List[Dict]:
        """获取历史数据 (使用日K线数据)"""
        scale_map = {"1d": 240, "1w": 1200, "1M": 7200}
        scale = scale_map.get(period, 240)

        kline = await self.get_kline_data(code, scale=scale, datalen=200)

        results = []
        for item in kline:
            results.append({
                "date": item["date"],
                "price": item["close"],
                "volume": item["volume"],
                "amount": item.get("amount", 0.0),
            })

        return results

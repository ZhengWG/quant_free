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

    # 数据源调度顺序
    _SOURCE_METHODS = {
        "sina": "_get_realtime_from_sina",
        "eastmoney": "_get_realtime_from_eastmoney",
        "tencent": "_get_realtime_from_tencent",
    }
    _AUTO_ORDER = ["sina", "tencent", "eastmoney"]

    async def get_realtime_data(self, codes: List[str], source: str = "auto") -> List[Dict]:
        """获取实时行情数据，支持手动选择数据源"""
        if not codes:
            return []

        if source != "auto" and source in self._SOURCE_METHODS:
            method = getattr(self, self._SOURCE_METHODS[source])
            results = await method(codes)
            if results:
                return results
            logger.warning(f"[{source}] returned empty")
            return []

        # auto 模式：依次尝试
        for src in self._AUTO_ORDER:
            method = getattr(self, self._SOURCE_METHODS[src])
            results = await method(codes)
            if results:
                return results
            logger.warning(f"[{src}] returned empty, trying next source...")

        logger.error("All realtime data sources failed")
        return []

    async def _get_realtime_from_sina(self, codes: List[str]) -> List[Dict]:
        """新浪财经实时行情"""
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

    def _code_to_eastmoney_secid(self, code: str) -> str:
        """将股票代码转换为东方财富 secid 格式 (market.code)"""
        code = code.strip()
        if code.startswith("sh"):
            return f"1.{code[2:]}"
        elif code.startswith("sz"):
            return f"0.{code[2:]}"
        elif code.isdigit() and len(code) == 6:
            if code.startswith(("6", "9")):
                return f"1.{code}"
            else:
                return f"0.{code}"
        return f"0.{code}"

    async def _get_realtime_from_tencent(self, codes: List[str]) -> List[Dict]:
        """腾讯财经实时行情"""
        tencent_codes = [self._normalize_code(c) for c in codes]
        url = "https://qt.gtimg.cn/q=" + ",".join(tencent_codes)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.encoding = "gbk"
                text = response.text

            results = []
            for line in text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                data = self._parse_tencent_line(line)
                if data:
                    results.append(data)

            logger.info(f"Tencent realtime: fetched {len(results)}/{len(codes)} stocks")
            return results
        except Exception as e:
            logger.error(f"Tencent get_realtime_data error: {e}")
            return []

    def _parse_tencent_line(self, line: str) -> Optional[Dict]:
        """解析腾讯实时行情"""
        match = re.match(r'v_(\w+)="(.*)";?', line)
        if not match:
            return None
        tencent_code = match.group(1)
        data_str = match.group(2)
        if not data_str:
            return None

        parts = data_str.split("~")
        if len(parts) < 45:
            return None

        try:
            name = parts[1]
            code = parts[2]
            price = float(parts[3])
            pre_close = float(parts[4])
            open_price = float(parts[5])
            volume_lots = float(parts[36]) if parts[36] else 0
            amount = float(parts[37]) if parts[37] else 0
            high = float(parts[33]) if parts[33] else price
            low = float(parts[34]) if parts[34] else price

            change = round(price - pre_close, 4)
            change_pct = float(parts[32]) if parts[32] else (
                round(change / pre_close * 100, 2) if pre_close > 0 else 0
            )

            return {
                "code": code,
                "name": name,
                "market": self._detect_market(tencent_code),
                "price": price,
                "change": change,
                "change_percent": change_pct,
                "volume": volume_lots * 100,
                "amount": amount * 10000,
                "high": high,
                "low": low,
                "open": open_price,
                "pre_close": pre_close,
                "timestamp": datetime.now().isoformat(),
            }
        except (ValueError, IndexError) as e:
            logger.error(f"Parse Tencent line error: {e}")
            return None

    async def _get_realtime_from_eastmoney(self, codes: List[str]) -> List[Dict]:
        """东方财富API实时行情"""
        secids = [self._code_to_eastmoney_secid(c) for c in codes]
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "fltt": "2",
            "fields": "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18",
            "secids": ",".join(secids),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                data = response.json()

            if data.get("rc") != 0:
                logger.warning(f"East Money API error: {data}")
                return []

            diff = data.get("data", {}).get("diff", [])
            results = []
            for item in diff:
                try:
                    code = str(item.get("f12", ""))
                    price = float(item.get("f2", 0))
                    if price <= 0:
                        continue

                    pre_close = float(item.get("f18", 0))
                    change = float(item.get("f4", 0))
                    change_pct = float(item.get("f3", 0))
                    volume_lots = float(item.get("f5", 0))

                    market = "A股"
                    if code.startswith(("6", "9")):
                        market = "A股"

                    results.append({
                        "code": code,
                        "name": item.get("f14", ""),
                        "market": market,
                        "price": price,
                        "change": change,
                        "change_percent": change_pct,
                        "volume": volume_lots * 100,
                        "amount": float(item.get("f6", 0)),
                        "high": float(item.get("f15", 0)),
                        "low": float(item.get("f16", 0)),
                        "open": float(item.get("f17", 0)),
                        "pre_close": pre_close,
                        "timestamp": datetime.now().isoformat(),
                    })
                except (ValueError, TypeError) as e:
                    logger.error(f"Parse East Money item error: {e}, item: {item}")
                    continue

            logger.info(f"East Money realtime: fetched {len(results)}/{len(codes)} stocks")
            return results
        except Exception as e:
            logger.error(f"East Money get_realtime_data error: {e}")
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
        start_date = (datetime.now() - timedelta(days=datalen * 3)).strftime("%Y-%m-%d")

        url = f"{self.TENCENT_KLINE_URL}?param={tencent_code},{period},{start_date},{end_date},{datalen},qfq"

        try:
            timeout = 15.0 if datalen <= 500 else 30.0
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)

            import json
            data = json.loads(response.text)

            if data.get("code") != 0:
                logger.warning(f"Tencent kline API error: {data}")
                return []

            stock_data = data.get("data", {}).get(tencent_code, {})
            # 腾讯API可能返回 "day" 或 "qfqday" (前复权)
            kline_list = stock_data.get(period) or stock_data.get(f"qfq{period}", [])

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

            logger.info(f"Tencent kline: fetched {len(results)} records for {code} ({period}), requested {datalen}")
            return results
        except Exception as e:
            logger.error(f"Tencent get_kline_data error for {code}: {e}")
            return []

    def _code_to_eastmoney_secid_ext(self, code: str) -> str:
        """股票代码 -> 东方财富 secid，支持 A 股和港股"""
        code = code.strip()
        if code.upper().startswith("HK"):
            return f"116.{code[2:]}"
        if code.startswith("sh"):
            return f"1.{code[2:]}"
        if code.startswith("sz"):
            return f"0.{code[2:]}"
        if code.isdigit() and len(code) == 6:
            return f"1.{code}" if code.startswith(("6", "9")) else f"0.{code}"
        return f"0.{code}"

    async def get_fundamental_data(self, codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取基本面数据 via 东方财富 ulist 接口（单次批量，更快更全）
        返回 {code: {pe, pb, roe, market_cap_yi, float_cap_yi,
                      revenue_growth, profit_growth, gross_margin}} 字典
        """
        if not codes:
            return {}

        def _sf(val):
            if val is None or val == "-" or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        result: Dict[str, Dict] = {}
        secids = ",".join(self._code_to_eastmoney_secid_ext(c) for c in codes)
        code_set = set(codes)

        BATCH = 50
        secid_list = secids.split(",")
        code_list = list(codes)

        for i in range(0, len(secid_list), BATCH):
            batch_secids = ",".join(secid_list[i: i + BATCH])
            batch_codes = code_list[i: i + BATCH]
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
            params = {
                "fltt": "2",
                "invt": "2",
                "fields": "f12,f14,f9,f23,f37,f20,f21,f41,f46,f49,f100,f115",
                "secids": batch_secids,
            }
            try:
                async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                    resp = await client.get(url, params=params)
                    body = resp.json()
                diffs = body.get("data", {}).get("diff", [])
                for item in diffs:
                    code = str(item.get("f12", ""))
                    if code not in code_set:
                        for bc in batch_codes:
                            if bc.endswith(code) or code.endswith(bc.lstrip("0")):
                                code = bc
                                break
                    if code not in code_set:
                        continue
                    pe = _sf(item.get("f9"))
                    pb = _sf(item.get("f23"))
                    roe = _sf(item.get("f37"))
                    mcap = _sf(item.get("f20"))
                    fcap = _sf(item.get("f21"))
                    rev_g = _sf(item.get("f41"))
                    prof_g = _sf(item.get("f46"))
                    gm = _sf(item.get("f49"))
                    pe_ttm = _sf(item.get("f115"))
                    industry_raw = item.get("f100", "")
                    industry = str(industry_raw) if industry_raw and industry_raw != "-" else None
                    result[code] = {
                        "pe": pe,
                        "pb": pb,
                        "roe": roe,
                        "market_cap_yi": round(mcap / 1e8, 2) if mcap else None,
                        "float_cap_yi": round(fcap / 1e8, 2) if fcap else None,
                        "revenue_growth": round(rev_g, 2) if rev_g is not None else None,
                        "profit_growth": round(prof_g, 2) if prof_g is not None else None,
                        "gross_margin": round(gm, 2) if gm is not None else None,
                        "pe_ttm": pe_ttm,
                        "industry": industry,
                    }
            except Exception as e:
                logger.warning(f"Fetch fundamental batch error: {e}")

        logger.info(f"Fundamental data fetched for {len(result)}/{len(codes)} stocks")
        return result

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

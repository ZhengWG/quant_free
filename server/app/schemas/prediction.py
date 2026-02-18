"""
预测分析模式
"""

from pydantic import BaseModel
from typing import Optional, List


class PredictionParams(BaseModel):
    """预测分析参数"""
    stock_pool: str = "hot_hs"
    custom_codes: Optional[str] = None
    prediction_months: int = 6          # 预测月份 3 / 6 / 12
    initial_capital: float = 100000.0
    top_n: int = 10


class FundamentalInfo(BaseModel):
    """基本面信息"""
    pe_dynamic: Optional[float] = None   # 动态市盈率
    pb: Optional[float] = None           # 市净率
    market_cap_yi: Optional[float] = None  # 总市值（亿元）


class ProjectedPoint(BaseModel):
    """投影价格/资金点"""
    date: str
    value: float


class PredictionItem(BaseModel):
    """单只股票预测结果"""
    rank: int
    stock_code: str
    stock_name: str
    # 基本面
    fundamental: FundamentalInfo
    # 各因子得分 (0-100)
    valuation_score: float
    trend_score: float
    momentum_score: float
    volatility_score: float
    volume_score: float
    composite_score: float
    # 预测
    predicted_return_pct: float       # 预测收益率%
    predicted_annual_return_pct: float  # 年化预测收益率%
    best_strategy: str
    best_strategy_label: str
    historical_return_pct: float      # 历史回测收益率%
    confidence: str                   # 高 / 中 / 低
    signal: str                       # 看涨 / 看跌 / 震荡
    # 拟合度 & 月度统计
    fit_score: float = 0.0            # R² 拟合度 (0-100)
    monthly_return_mean: float = 0.0  # 月均收益率%
    monthly_return_std: float = 0.0   # 月收益率标准差%
    # 图表数据
    historical_prices: List[ProjectedPoint] = []
    projected_prices: List[ProjectedPoint] = []
    projected_prices_optimistic: List[ProjectedPoint] = []   # 乐观 (mean+1σ)
    projected_prices_pessimistic: List[ProjectedPoint] = []  # 悲观 (mean-1σ)
    projected_equity: List[ProjectedPoint] = []
    projected_equity_optimistic: List[ProjectedPoint] = []
    projected_equity_pessimistic: List[ProjectedPoint] = []
    historical_equity: List[ProjectedPoint] = []             # 历史回测权益曲线


class PredictionResult(BaseModel):
    """预测分析结果"""
    pool_name: str
    prediction_months: int
    total_analyzed: int
    time_taken_seconds: float
    rankings: List[PredictionItem]

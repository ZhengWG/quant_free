"""
智能选股回测模式
"""

from pydantic import BaseModel
from typing import Optional, List

from app.schemas.backtest import BacktestResult


class SmartScreenParams(BaseModel):
    """智能选股参数"""
    stock_pool: str = "hot_hs"          # hot_hs | industry_leaders | custom
    custom_codes: Optional[str] = None   # 逗号分隔，pool=custom 时使用
    screening_strategy: str = "all"      # all | uptrend | momentum | volume_breakout
    start_date: str                      # YYYY-MM-DD
    end_date: str
    initial_capital: float = 100000.0
    top_n: int = 5
    # 模式：classic = 经典回测, smart_v2 = 综合智选
    mode: str = "classic"
    prediction_months: int = 6           # smart_v2 模式下的预测月数
    # 风控参数（None = 使用引擎默认值，会透传给每笔回测）
    stop_loss_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    risk_per_trade: Optional[float] = None
    max_position_pct: Optional[float] = None
    trend_ma_len: Optional[int] = None
    cooldown_bars: Optional[int] = None


class ScreenedStock(BaseModel):
    """筛选后的股票"""
    code: str
    name: str
    passed: bool
    reason: str


class RankedResult(BaseModel):
    """排名结果"""
    rank: int
    stock_code: str
    stock_name: str
    strategy: str
    strategy_label: str                  # "MA(5,20)" / "MA(10,30)" / "MACD"
    total_return_percent: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    score: float                         # 综合评分 0-100
    backtest_result: Optional[BacktestResult] = None
    # smart_v2 新增字段
    valuation_score: Optional[float] = None     # 估值评分 0-100
    confidence_score: Optional[float] = None    # 策略置信度 0-100
    predicted_return_pct: Optional[float] = None  # 预测收益率
    alpha_pct: Optional[float] = None           # 超额收益 vs 买入持有
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    industry: Optional[str] = None               # 所属行业
    revenue_growth: Optional[float] = None       # 营收同比增长%
    profit_growth: Optional[float] = None        # 净利润同比增长%
    gross_margin: Optional[float] = None         # 毛利率%
    signal: Optional[str] = None                # 看涨/看跌/震荡
    # AI 基本面分析
    ai_score: Optional[float] = None             # AI基本面评分 0-100
    ai_analysis: Optional[str] = None            # AI分析简述
    # smart_v2 图表数据
    equity_curve: Optional[List[dict]] = None        # [{date, value}] 历史权益曲线（训练+测试）
    projected_equity: Optional[List[dict]] = None    # [{date, value}] 未来预测权益曲线
    full_price_series: Optional[List[dict]] = None   # [{date, close}] 完整价格序列
    all_trades: Optional[List[dict]] = None          # 合并训练+测试交易记录
    split_date: Optional[str] = None                 # 训练/测试分割日期


class SmartScreenResult(BaseModel):
    """智能选股结果"""
    pool_name: str
    screening_strategy: str
    total_stocks: int
    screened_stocks: int
    total_backtests: int
    time_taken_seconds: float
    rankings: List[RankedResult]
    all_screened: List[ScreenedStock]
    # smart_v2 新增
    mode: str = "classic"
    test_bnh_pct: Optional[float] = None        # 测试期买入持有基准
    avg_confidence: Optional[float] = None
    avg_predicted_return: Optional[float] = None
"""
策略测试模式（Walk-Forward Validation）
前 80% 训练 + 后 20% 验证
"""

from pydantic import BaseModel
from typing import Optional, List


class StrategyTestParams(BaseModel):
    """策略测试参数"""
    stock_code: str
    start_date: str              # YYYY-MM-DD
    end_date: str
    initial_capital: float = 100000.0
    train_ratio: float = 0.8    # 训练集比例


class ProjectedPoint(BaseModel):
    date: str
    value: float


class StrategyTestItem(BaseModel):
    """单策略测试结果"""
    strategy: str
    strategy_label: str
    # 区间信息
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_bars: int             # 交易日数
    test_bars: int
    # 训练期指标
    train_return_pct: float
    train_sharpe: float
    train_max_drawdown: float
    train_win_rate: float
    train_trades: int
    # 买入持有基准
    train_bnh_pct: float        # 训练期买入持有收益
    test_bnh_pct: float         # 测试期买入持有收益
    # 预测（由训练期外推）
    predicted_return_pct: float
    predicted_direction: str       # 看涨 / 看跌 / 震荡
    # 验证期实际表现
    actual_return_pct: float
    actual_sharpe: float
    actual_max_drawdown: float
    actual_win_rate: float
    actual_trades: int
    actual_direction: str
    # Alpha (策略 vs 买入持有)
    train_alpha_pct: float      # 训练期超额收益
    test_alpha_pct: float       # 测试期超额收益
    # 准确度评估
    direction_correct: bool
    return_error_pct: float        # |predicted - actual|
    confidence_score: float        # 0-100
    test_has_trades: bool = True
    # 图表数据
    train_equity: List[ProjectedPoint] = []
    test_equity_predicted: List[ProjectedPoint] = []
    test_equity_actual: List[ProjectedPoint] = []
    test_equity_bnh: List[ProjectedPoint] = []     # 测试期买入持有权益
    full_price_series: List[ProjectedPoint] = []


class StrategyTestResult(BaseModel):
    """策略测试总结果"""
    stock_code: str
    stock_name: str
    full_start: str
    full_end: str
    train_ratio: float
    total_strategies: int
    avg_confidence: float
    best_strategy: str
    best_strategy_label: str
    # 买入持有基准
    full_bnh_pct: float = 0.0     # 全区间买入持有收益
    test_bnh_pct: float = 0.0     # 测试期买入持有收益
    time_taken_seconds: float
    items: List[StrategyTestItem]


# ---------- 单股策略分析（收敛接口：80/20 多策略评分 + TopK + 预测收益）----------

class StrategyAnalyzeParams(BaseModel):
    """单股策略分析参数"""
    stock_code: str
    start_date: str              # YYYY-MM-DD
    end_date: str
    initial_capital: float = 100000.0
    train_ratio: float = 0.8     # 训练/验证 划分比例
    top_k: int = 5               # 返回相对收益评分最高的前 K 个策略


class StrategyAnalyzeResult(BaseModel):
    """单股策略分析结果：按评分排序的 TopK 策略及未来收益预测"""
    stock_code: str
    stock_name: str
    full_start: str
    full_end: str
    train_ratio: float
    full_bnh_pct: float = 0.0     # 全区间买入持有收益
    test_bnh_pct: float = 0.0     # 验证期买入持有收益
    time_taken_seconds: float
    strategies: List[StrategyTestItem]   # 按 confidence_score 降序，取 top_k

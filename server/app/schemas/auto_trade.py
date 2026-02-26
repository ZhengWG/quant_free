"""
全自动交易系统 Pydantic Schemas
所有字段尽量设为可选并给默认值，方便 API 调用
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator
from datetime import datetime


# ──────────────────────────────────────────────────────────
# 策略预设
# ──────────────────────────────────────────────────────────

STRATEGY_PRESETS: Dict[str, Dict] = {
    "defensive": {
        "display_name": "防守型",
        "description": (
            "低回撤优先。严格市场环境过滤（CSI300 > MA20 才建仓），"
            "5% 止盈 / 6% 止损 / 持仓上限15天。"
            "适合震荡行情或熊市，可避免大亏但会错过急速拉升行情。"
        ),
        # 风控参数
        "stop_loss_pct": 0.06,
        "take_profit_pct": 0.05,
        "max_hold_days": 15,
        "max_position_pct": 0.3,
        "min_test_return_pct": -1.0,
        "market_regime_filter": True,
    },
    "aggressive": {
        "display_name": "激进型",
        "description": (
            "追求高收益。关闭市场环境过滤，可在行情刚启动时即时建仓；"
            "15% 止盈 / 10% 止损 / 持仓上限30天，单股仓位最高50%。"
            "适合牛市或政策刺激行情，回撤容忍度高。"
        ),
        # 风控参数
        "stop_loss_pct": 0.10,
        "take_profit_pct": 0.15,
        "max_hold_days": 30,
        "max_position_pct": 0.5,
        "min_test_return_pct": -5.0,
        "market_regime_filter": False,
    },
}

# preset 影响的风控字段列表
_PRESET_RISK_FIELDS = [
    "stop_loss_pct", "take_profit_pct", "max_hold_days",
    "max_position_pct", "min_test_return_pct", "market_regime_filter",
]


# ──────────────────────────────────────────────────────────
# 请求
# ──────────────────────────────────────────────────────────

class AutoTradeSessionCreate(BaseModel):
    """创建自动交易会话"""
    preset_name: Optional[str] = Field(
        default=None,
        description="策略预设名称（defensive / aggressive）。若提供，则覆盖对应风控参数默认值；显式传参优先。",
    )
    name: str = Field(default="", description="会话名称（可选）")
    stock_codes: List[str] = Field(
        default=["000001", "600519", "000858", "002594", "600036"],
        description="股票池，默认5只沪深热门",
    )
    initial_capital: float = Field(default=1_000_000.0, description="初始资金")
    cycle_days: int = Field(default=30, description="策略轮换周期（自然日）")
    validate_years: float = Field(default=5.0, description="历史验证年数，数据不足时取全量")
    train_ratio: float = Field(default=0.8, description="训练/测试集分割比例")
    max_position_pct: float = Field(default=0.3, description="单股最大仓位比例")
    stop_loss_pct: float = Field(default=0.06, description="止损比例，持仓亏损超过此值自动平仓，默认6%")
    take_profit_pct: float = Field(default=0.05, description="止盈比例，持仓盈利超过此值自动平仓，默认5%")
    max_hold_days: int = Field(default=15, description="最大持仓自然日，超过则强制平仓，默认15天")
    min_test_return_pct: float = Field(default=-1.0, description="策略验证期最低Alpha要求(%)，低于此值不开新仓，默认-1%")
    market_regime_filter: bool = Field(default=True, description="市场环境过滤：仅在沪深300高于20日均线时允许建新仓")
    skip_validate: bool = Field(default=False, description="跳过历史验证，直接运行")
    preset_strategy: Optional[str] = Field(default=None, description="若 skip_validate=True，指定统一策略名")

    @model_validator(mode="before")
    @classmethod
    def apply_preset(cls, data: Any) -> Any:
        """若指定 preset_name，将预设参数作为默认值（显式传参优先）"""
        if not isinstance(data, dict):
            return data
        preset_name = data.get("preset_name")
        if preset_name and preset_name in STRATEGY_PRESETS:
            preset = STRATEGY_PRESETS[preset_name]
            for field in _PRESET_RISK_FIELDS:
                if field not in data and field in preset:
                    data[field] = preset[field]
        return data


class ValidateOnlyRequest(BaseModel):
    """仅运行历史验证，不创建会话"""
    stock_codes: List[str] = Field(default=["000001", "600519"])
    validate_years: float = Field(default=5.0)
    train_ratio: float = Field(default=0.8)


# ──────────────────────────────────────────────────────────
# 响应
# ──────────────────────────────────────────────────────────

class StrategyInfo(BaseModel):
    """某股票的最优策略信息"""
    stock_code: str
    strategy: str
    strategy_label: str
    short_window: int
    long_window: int
    confidence: float
    train_return_pct: float = 0.0
    test_return_pct: float = 0.0
    test_alpha_pct: float = 0.0


class AutoTradeSessionOut(BaseModel):
    """会话概览"""
    id: str
    name: str
    status: str
    stock_codes: List[str]
    initial_capital: float
    available_cash: float
    cycle_days: int
    current_cycle: int
    cycle_start_date: str
    cycle_end_date: str
    validate_years: float
    max_position_pct: float
    strategy_map: Dict[str, Any]      # {code: StrategyInfo dict}
    last_run_date: str
    created_at: Optional[datetime] = None


class SignalOut(BaseModel):
    """单条信号记录"""
    id: str
    session_id: str
    date: str
    stock_code: str
    strategy: str
    strategy_label: str
    signal: str           # BUY / SELL / HOLD
    price: float
    quantity: int
    amount: float
    fees: float
    profit: float
    executed: bool
    notes: str
    created_at: Optional[datetime] = None


class PositionOut(BaseModel):
    """持仓记录"""
    session_id: str
    stock_code: str
    stock_name: str
    quantity: int
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_profit: float = 0.0
    unrealized_profit_pct: float = 0.0
    realized_profit: float = 0.0
    total_fees: float = 0.0


class PerformanceOut(BaseModel):
    """绩效报告"""
    session_id: str
    status: str
    current_cycle: int
    cycle_start_date: str
    cycle_end_date: str
    days_remaining: int

    initial_capital: float
    current_total_asset: float
    available_cash: float
    market_value: float
    total_return: float
    total_return_pct: float

    # 对比基准（简单买入持有）
    benchmark_return_pct: float = 0.0
    alpha_pct: float = 0.0

    total_trades: int
    win_trades: int
    win_rate: float
    total_fees: float
    realized_profit: float
    unrealized_profit: float

    per_stock: List[PositionOut] = []
    recent_signals: List[SignalOut] = []


class ValidateResult(BaseModel):
    """历史验证结果（不含会话）"""
    stock_code: str
    best_strategy: str
    best_strategy_label: str
    confidence: float
    train_return_pct: float
    test_return_pct: float
    test_alpha_pct: float
    train_period: str
    test_period: str
    total_strategies_tested: int
    data_bars: int
    error: Optional[str] = None


class ValidateOnlyResponse(BaseModel):
    results: List[ValidateResult]
    summary: str


# ──────────────────────────────────────────────────────────
# 离线历史模拟
# ──────────────────────────────────────────────────────────

# 可用基准别名（也接受 sh000300 等完整代码）
BENCHMARK_ALIASES = {
    "hs300":  ("sh000300", "沪深300"),
    "zz500":  ("sh000905", "中证500"),
    "hsi":    ("HKHSI",    "恒生指数"),
    "sz50":   ("sh000016", "上证50"),
    "cy":     ("sh399006", "创业板指"),
}


class OfflineSimConfig(BaseModel):
    """离线历史模拟配置"""
    preset_name: Optional[str] = Field(
        default=None,
        description="策略预设名称（defensive / aggressive）。若提供，则覆盖对应风控参数默认值；显式传参优先。",
    )
    stock_codes: List[str] = Field(
        default=["600519", "000001", "002594", "000858", "600036"],
        description="股票池",
    )
    start_date: str = Field(
        default="2023-01-01",
        description="模拟起始日（此前的数据用于策略训练）",
    )
    end_date: str = Field(
        default="2024-12-31",
        description="模拟结束日",
    )
    validate_months: int = Field(
        default=12,
        description="训练期月数（start_date 往前推多少个月用于选策略）",
    )
    initial_capital: float = Field(default=1_000_000.0, description="初始资金")
    max_position_pct: float = Field(default=0.3, description="单股最大仓位比例")
    train_ratio: float = Field(default=0.8, description="训练/验证集分割比（用于策略选择）")
    stop_loss_pct: float = Field(default=0.06, description="止损比例，持仓亏损超过此值自动平仓，默认6%")
    take_profit_pct: float = Field(default=0.05, description="止盈比例，持仓盈利超过此值自动平仓，默认5%")
    max_hold_days: int = Field(default=15, description="最大持仓自然日，超过则强制平仓，默认15天")
    min_test_return_pct: float = Field(default=-1.0, description="策略验证期最低Alpha要求(%)，低于此值不开新仓，默认-1%")
    market_regime_filter: bool = Field(default=True, description="市场环境过滤：仅在沪深300高于20日均线时允许建新仓")
    market_regime_code: str = Field(default="sh000300", description="市场环境判断用指数代码，默认沪深300")
    benchmarks: List[str] = Field(
        default=["hs300", "zz500"],
        description="基准指数别名或完整代码（如 hs300/zz500/hsi 或 sh000300）",
    )

    @model_validator(mode="before")
    @classmethod
    def apply_preset(cls, data: Any) -> Any:
        """若指定 preset_name，将预设参数作为默认值（显式传参优先）"""
        if not isinstance(data, dict):
            return data
        preset_name = data.get("preset_name")
        if preset_name and preset_name in STRATEGY_PRESETS:
            preset = STRATEGY_PRESETS[preset_name]
            for field in _PRESET_RISK_FIELDS:
                if field not in data and field in preset:
                    data[field] = preset[field]
        return data


class EquityPoint(BaseModel):
    date: str
    value: float


class BenchmarkResult(BaseModel):
    code: str
    name: str
    start_price: float
    end_price: float
    total_return_pct: float
    curve: List[EquityPoint] = []


class StockSimDetail(BaseModel):
    stock_code: str
    strategy: str
    strategy_label: str
    confidence: float
    total_trades: int
    win_trades: int
    win_rate: float
    total_fees: float
    realized_profit: float
    unrealized_profit: float
    final_qty: int
    final_price: float


class TradeRecord(BaseModel):
    date: str
    stock_code: str
    action: str          # BUY / SELL
    price: float
    quantity: int
    fees: float
    profit: float = 0.0  # 仅 SELL 时有效
    cash_after: float
    note: str = ""       # 附加信息，如"止损"


class OfflineSimResult(BaseModel):
    # 参数回显
    start_date: str
    end_date: str
    training_period: str
    initial_capital: float
    stock_codes: List[str]

    # 组合绩效
    final_capital: float
    total_return: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    win_trades: int
    total_fees: float

    # 基准对比
    benchmarks: List[BenchmarkResult]
    alpha_summary: Dict[str, float]   # {基准名: alpha}

    # 曲线
    portfolio_curve: List[EquityPoint]

    # 明细
    strategy_map: Dict[str, Any]      # {code: {strategy, label, confidence, ...}}
    per_stock: List[StockSimDetail]
    trades: List[TradeRecord] = []    # 所有成交记录（可选，数量多时截断）

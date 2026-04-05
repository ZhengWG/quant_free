"""
全自动交易系统 DB 模型
- AutoTradeSession : 一个30天交易会话
- AutoTradeSignal  : 每日信号记录
- AutoTradePosition: 独立持仓（与手动账户隔离）
"""

import json
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text
from app.models.base import Base


class AutoTradeSession(Base):
    __tablename__ = "auto_trade_sessions"

    id = Column(String, primary_key=True)
    name = Column(String, default="")

    # 股票池 & 策略映射（JSON 序列化存储）
    stock_codes_json = Column(Text, default="[]")          # List[str]
    strategy_map_json = Column(Text, default="{}")         # {code: {strategy,short_w,long_w,label,confidence}}

    # 账户
    initial_capital = Column(Float, default=1_000_000.0)
    available_cash = Column(Float, default=1_000_000.0)

    # 周期参数
    cycle_days = Column(Integer, default=30)               # 天数（自然日）
    current_cycle = Column(Integer, default=0)
    cycle_start_date = Column(String, default="")
    cycle_end_date = Column(String, default="")

    # 历史验证参数
    validate_years = Column(Float, default=5.0)            # 默认5年
    train_ratio = Column(Float, default=0.8)

    # 仓位参数
    max_position_pct = Column(Float, default=0.3)          # 单股最大30%

    # 风控参数
    stop_loss_pct = Column(Float, default=0.06)            # 止损比例（6%）
    take_profit_pct = Column(Float, default=0.05)          # 止盈比例（5%）
    max_hold_days = Column(Integer, default=15)            # 最大持仓自然日
    min_test_return_pct = Column(Float, default=-1.0)      # 策略验证期最低收益要求（%）
    market_regime_filter = Column(Boolean, default=True)   # 是否启用市场环境过滤

    # K线粒度（分钟）：240=日K，15=15分钟K
    data_scale = Column(Integer, default=240)
    # 执行模式：sim=会话内模拟成交；live=调用券商网关实盘下单
    execution_mode = Column(String, default="sim")

    # 前向测试分组（空串表示独立会话）
    group_id = Column(String, default="")

    # 状态: validating / running / paused / stopped
    status = Column(String, default="validating")
    last_run_date = Column(String, default="")             # 最近一次执行日期
    validate_summary_json = Column(Text, default="{}")     # 历史验证摘要

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # ── helpers ──────────────────────────────────────────
    @property
    def stock_codes(self):
        return json.loads(self.stock_codes_json or "[]")

    @stock_codes.setter
    def stock_codes(self, value):
        self.stock_codes_json = json.dumps(value, ensure_ascii=False)

    @property
    def strategy_map(self):
        return json.loads(self.strategy_map_json or "{}")

    @strategy_map.setter
    def strategy_map(self, value):
        self.strategy_map_json = json.dumps(value, ensure_ascii=False)

    @property
    def validate_summary(self):
        return json.loads(self.validate_summary_json or "{}")

    @validate_summary.setter
    def validate_summary(self, value):
        self.validate_summary_json = json.dumps(value, ensure_ascii=False)


class AutoTradeSignal(Base):
    __tablename__ = "auto_trade_signals"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)

    date = Column(String, nullable=False)           # YYYY-MM-DD
    stock_code = Column(String, nullable=False)
    strategy = Column(String, default="")
    strategy_label = Column(String, default="")

    signal = Column(String, default="HOLD")         # BUY / SELL / HOLD
    price = Column(Float, default=0.0)              # 收盘价
    quantity = Column(Integer, default=0)           # 模拟成交数量
    amount = Column(Float, default=0.0)             # 成交金额
    fees = Column(Float, default=0.0)               # 手续费
    profit = Column(Float, default=0.0)             # 本次卖出盈亏（SELL 时有效）

    executed = Column(Boolean, default=False)
    notes = Column(String, default="")

    created_at = Column(DateTime, default=datetime.now)


class AutoTradePosition(Base):
    __tablename__ = "auto_trade_positions"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    stock_code = Column(String, nullable=False)
    stock_name = Column(String, default="")

    quantity = Column(Integer, default=0)
    avg_cost = Column(Float, default=0.0)           # 含手续费的成本价
    entry_date = Column(String, default="")         # 建仓日期 YYYY-MM-DD
    total_fees = Column(Float, default=0.0)
    realized_profit = Column(Float, default=0.0)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

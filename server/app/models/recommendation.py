"""
每日交易建议 · 推荐记忆
────────────────────
RecommendationHistory: 每日推荐快照。每个交易日为每只"活跃/新增/退出"的股票写一行，
通过 first_recommended_date / entry_ref_price / miss_count 维持 day-to-day 延续性。
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from app.models.base import Base


class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    date = Column(String, index=True, default="")          # 本行所属交易日 YYYY-MM-DD
    market = Column(String, default="")                    # A股 / 港股 / 美股
    stock_code = Column(String, index=True, default="")
    stock_name = Column(String, default="")

    # 推荐当时的策略与信号
    strategy = Column(String, default="")
    strategy_label = Column(String, default="")
    signal = Column(String, default="")                    # 看涨/看跌/震荡

    # 价格锚点
    entry_ref_price = Column(Float, default=0.0)           # 首次推荐时的参考价（延续性锚）
    current_price = Column(Float, default=0.0)             # 本行日期的现价
    target_price = Column(Float, default=0.0)
    stop_loss = Column(Float, default=0.0)

    # 评分
    confidence = Column(Float, default=0.0)                # 策略置信度 0-100
    composite_score = Column(Float, default=0.0)           # 综合评分 0-100
    predicted_return_pct = Column(Float, default=0.0)      # 预测收益%

    # 基本面（美股可能为空 → 降级纯技术面）
    pe = Column(Float, nullable=True)
    pb = Column(Float, nullable=True)
    roe = Column(Float, nullable=True)
    ai_comment = Column(Text, default="")

    # 延续性状态
    status = Column(String, default="new")                 # new / holding / exit
    first_recommended_date = Column(String, default="")    # 首次进入推荐的日期
    days_held = Column(Integer, default=0)                 # 自首次推荐的自然日
    return_since_rec_pct = Column(Float, default=0.0)      # 自首推以来收益%
    miss_count = Column(Integer, default=0)                # 连续掉出 Top-N 计数（滞后阈值用）
    exit_reason = Column(String, default="")

    created_at = Column(DateTime, default=datetime.utcnow)

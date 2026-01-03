"""
策略生成服务
"""

import json
import re
import uuid
from datetime import datetime
from typing import Optional, List
from loguru import logger

from app.schemas.strategy import Strategy, StrategyParams, StrategyCreate
from app.adapters.ai.deepseek_service import DeepSeekService
from app.adapters.ai.openai_service import OpenAIService
from app.services.market_data_service import MarketDataService
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.strategy import Strategy as StrategyModel


class StrategyService:
    """策略生成服务"""
    
    def __init__(self):
        # 根据配置选择AI服务
        if settings.AI_PROVIDER == "deepseek":
            self.ai_service = DeepSeekService()
        else:
            self.ai_service = OpenAIService()
        
        self.market_service = MarketDataService()
        logger.info(f"Using AI provider: {settings.AI_PROVIDER}")
    
    async def generate_strategy(self, params: StrategyParams) -> Strategy:
        """生成策略"""
        try:
            # 获取市场数据
            market_data = await self.market_service.get_realtime_data([params.stock_code])
            if not market_data:
                raise ValueError("股票数据不存在")
            
            stock = market_data[0]
            
            # 调用AI生成策略
            strategy_text = await self.ai_service.generate_strategy({
                "stock_code": params.stock_code,
                "stock_name": stock.name,
                "current_price": stock.price,
                "change_percent": stock.change_percent,
                "risk_level": params.risk_level or "MEDIUM",
                "time_horizon": params.time_horizon or "短期"
            })
            
            # 解析策略结果
            strategy = self._parse_strategy(strategy_text, params.stock_code, stock.name)
            
            # 保存策略
            await self._save_strategy(strategy)
            
            return strategy
        except Exception as e:
            logger.error(f"Generate strategy error: {e}")
            raise
    
    async def get_strategy(self, id: str) -> Strategy:
        """获取策略详情"""
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            result = await session.get(StrategyModel, id)
            if not result:
                raise ValueError("策略不存在")
            return Strategy.model_validate(result)
    
    async def get_history_strategies(self, stock_code: Optional[str] = None) -> List[Strategy]:
        """获取历史策略"""
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            stmt = select(StrategyModel)
            if stock_code:
                stmt = stmt.where(StrategyModel.stock_code == stock_code)
            result = await session.execute(stmt)
            results = result.scalars().all()
            return [Strategy.model_validate(r) for r in results]
    
    def _parse_strategy(self, text: str, stock_code: str, stock_name: str) -> Strategy:
        """解析策略文本"""
        try:
            # 尝试解析JSON
            json_text = text
            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_object_match = re.search(r'\{[\s\S]*\}', text)
                if json_object_match:
                    json_text = json_object_match.group(0)
            
            parsed = json.loads(json_text)
            
            return Strategy(
                id=str(uuid.uuid4()),
                stock_code=stock_code,
                stock_name=stock_name,
                action=parsed.get("action", "HOLD"),
                target_price=parsed.get("target_price"),
                stop_loss=parsed.get("stop_loss"),
                confidence=min(max(parsed.get("confidence", 0.7), 0), 1),
                reasoning=parsed.get("reasoning", text),
                risk_level=parsed.get("risk_level", "MEDIUM"),
                time_horizon=parsed.get("time_horizon", "短期"),
                ai_model=settings.AI_PROVIDER,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        except Exception as e:
            logger.warning(f"Failed to parse strategy as JSON, using text parsing: {e}")
            
            # 简单文本解析
            action_match = re.search(r'(买入|卖出|持有|BUY|SELL|HOLD)', text, re.IGNORECASE)
            action = "HOLD"
            if action_match:
                action_str = action_match.group(0).upper()
                if "BUY" in action_str or "买入" in action_str:
                    action = "BUY"
                elif "SELL" in action_str or "卖出" in action_str:
                    action = "SELL"
            
            confidence_match = re.search(r'置信度[：:]\s*([0-9.]+)', text)
            confidence = 0.7
            if confidence_match:
                confidence = min(max(float(confidence_match.group(1)) / 100, 0), 1)
            
            return Strategy(
                id=str(uuid.uuid4()),
                stock_code=stock_code,
                stock_name=stock_name,
                action=action,
                target_price=None,
                stop_loss=None,
                confidence=confidence,
                reasoning=text,
                risk_level="MEDIUM",
                time_horizon="短期",
                ai_model=settings.AI_PROVIDER,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    async def _save_strategy(self, strategy: Strategy):
        """保存策略到数据库"""
        async with AsyncSessionLocal() as session:
            strategy_model = StrategyModel(
                id=strategy.id,
                stock_code=strategy.stock_code,
                stock_name=strategy.stock_name,
                action=strategy.action,
                target_price=strategy.target_price,
                stop_loss=strategy.stop_loss,
                confidence=strategy.confidence,
                reasoning=strategy.reasoning,
                risk_level=strategy.risk_level,
                time_horizon=strategy.time_horizon,
                ai_model=strategy.ai_model
            )
            session.add(strategy_model)
            await session.commit()
            await session.refresh(strategy_model)


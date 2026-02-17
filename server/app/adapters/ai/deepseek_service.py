"""
DeepSeek服务适配器
"""

from openai import OpenAI
from loguru import logger
from app.core.config import settings


class DeepSeekService:
    """DeepSeek AI服务"""
    
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        if self.api_key:
            # DeepSeek API兼容OpenAI SDK，只需要修改baseURL
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
        else:
            logger.warning("DEEPSEEK_API_KEY not set, strategy generation will use mock data")
            self.client = None
    
    async def generate_strategy(self, params: dict) -> str:
        """生成策略"""
        if not self.client:
            return f"基于当前市场数据，建议{params.get('risk_level', 'MEDIUM') == 'LOW' and '谨慎' or '积极'}操作。"
        
        try:
            prompt = self._build_prompt(params)
            model = settings.DEEPSEEK_MODEL or "deepseek-chat"
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的量化交易策略分析师。请基于市场数据生成交易策略建议。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content or "无法生成策略"
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise
    
    def _build_prompt(self, params: dict) -> str:
        """构建提示词"""
        return f"""
请基于以下市场数据，生成交易策略建议：

股票代码：{params.get('stock_code')}
股票名称：{params.get('stock_name')}
当前价格：{params.get('current_price')}
涨跌幅：{params.get('change_percent')}%
风险偏好：{params.get('risk_level')}
持仓周期：{params.get('time_horizon')}

请提供：
1. 买入/卖出/持有建议
2. 目标价位（如有）
3. 止损位（如有）
4. 持仓周期建议
5. 策略理由说明

请以JSON格式返回，包含以下字段：
- action: "BUY" | "SELL" | "HOLD"
- target_price: 目标价格（数字，可选）
- stop_loss: 止损价格（数字，可选）
- confidence: 置信度（0-1之间的数字）
- reasoning: 策略理由（字符串）
- risk_level: 风险等级（"LOW" | "MEDIUM" | "HIGH"）
- time_horizon: 持仓周期建议（字符串）
        """.strip()


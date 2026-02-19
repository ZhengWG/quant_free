# QuantFree 后端

Python FastAPI 服务，提供行情、交易、回测、智能选股、预测等 API。

## 环境与安装

- Python 3.10+
- `pip install -r requirements.txt`
- `cp .env.example .env`，按需填写（AI、交易模式等见注释）

## 运行

```bash
python main.py
# 或 uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

- API 文档：http://localhost:3000/docs  
- 健康检查：http://localhost:3000/health  

## 回测与选股：两个主接口

1. **单股策略分析** `POST /api/v1/backtest/analyze`  
   - 输入：单只股票代码、日期区间。  
   - 逻辑：80% 训练 + 20% 验证（Walk-Forward），对多策略回测，按相对收益/置信度评分排序。  
   - 输出：评分最高的 TopK 策略、每策略的未来收益预测（`predicted_return_pct`）及训练/验证指标。

2. **批量智能选股** `POST /api/v1/backtest/smart-screen`  
   - 在单股策略分析的基础上，增加股票池与选股逻辑。  
   - 对池内每只股票执行与「单股策略分析」相同的 80/20 多策略回测与评分，取该股最佳策略；再按综合评分（含估值、AI 基本面、置信度、预测收益等）对股票排序，返回 Top N 及每只的最佳策略与预测收益。  
   - 选股模式：`mode=classic` 为经典技术面筛选+回测；`mode=smart_v2` 为估值筛选 + 单股策略分析（复用 `StrategyTestService`）+ AI 基本面 + 复合排名。

## 结构

- `main.py` 入口；`app/core` 配置与数据库；`app/api/routes` 路由；`app/services` 业务；`app/adapters` 行情/AI/基本面等适配器。


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

## 结构

- `main.py` 入口；`app/core` 配置与数据库；`app/api/routes` 路由；`app/services` 业务；`app/adapters` 行情/AI/基本面等适配器。


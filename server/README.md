# QuantFree Server (Python)

Python后端服务

## 环境要求

- Python >= 3.10
- pip

## 安装

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入必要的API密钥
```

## 运行

```bash
# 开发模式（自动重载）
python main.py

# 或使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

## API文档

启动服务后，访问：
- Swagger UI: http://localhost:3000/docs
- ReDoc: http://localhost:3000/redoc
- 健康检查: http://localhost:3000/health

## 项目结构

```
server_py/
├── main.py                 # 服务入口
├── app/
│   ├── core/              # 核心配置
│   │   ├── config.py      # 配置管理
│   │   └── database.py    # 数据库
│   ├── models/             # 数据模型（SQLAlchemy）
│   ├── schemas/            # Pydantic模式
│   ├── api/                # API路由
│   │   └── routes/        # 路由定义
│   ├── services/           # 业务服务
│   └── adapters/           # 外部API适配器
│       ├── market/         # 行情数据适配器
│       └── ai/             # AI服务适配器
├── requirements.txt        # Python依赖
└── .env.example            # 环境变量模板
```

## 技术栈

- **FastAPI**: 现代Python Web框架，高性能，自动生成API文档
- **SQLAlchemy**: ORM框架，支持异步
- **Pydantic**: 数据验证和序列化
- **Loguru**: 日志库
- **OpenAI SDK**: 兼容DeepSeek API


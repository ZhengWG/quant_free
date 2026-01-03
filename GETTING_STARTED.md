# 快速开始指南

## 环境要求

- Node.js >= 18.0.0
- npm >= 9.0.0 或 yarn
- VSCode >= 1.70.0

## 安装步骤

### 1. 安装Python后端依赖

```bash
cd server_py

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 安装VSCode插件依赖

```bash
cd extension
npm install
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp server_py/.env.example server_py/.env

# 编辑 server_py/.env 文件，填入必要的API密钥：
# - DEEPSEEK_API_KEY: DeepSeek API Key（推荐，用于策略生成）
#   - 获取方式：访问 https://platform.deepseek.com/ 注册并获取API Key
#   - 设置 AI_PROVIDER=deepseek（默认）
# - TUSHARE_TOKEN: Tushare API Token（获取A股数据）
# - 其他可选配置
```

### 4. 启动后端服务

```bash
cd server_py
source venv/bin/activate  # 如果使用虚拟环境
python main.py

# 或使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

服务将在 `http://localhost:3000` 启动

访问API文档：
- Swagger UI: http://localhost:3000/docs
- ReDoc: http://localhost:3000/redoc

### 4. 运行VSCode插件

1. 在VSCode中打开项目根目录
2. 按 `F5` 启动调试，会打开一个新的VSCode窗口（Extension Development Host）
3. 在新窗口中，打开命令面板（Cmd+Shift+P / Ctrl+Shift+P）
4. 输入 `QuantFree` 查看可用命令

## 使用说明

### 添加自选股

1. 打开命令面板
2. 输入 `QuantFree: 添加自选股`
3. 输入股票代码（如：000001, 600519）
4. 在侧边栏的"实时行情"视图中查看

### 生成策略推荐

1. 打开命令面板
2. 输入 `QuantFree: 生成策略推荐`
3. 输入股票代码
4. 等待AI分析（需要配置OpenAI API Key）
5. 在输出面板查看策略详情

### 执行交易

1. 打开命令面板
2. 输入 `QuantFree: 下单`
3. 按照提示输入订单信息
4. 确认后提交订单

## 开发模式

### 后端开发

```bash
cd server
npm run dev  # 启动开发服务器（自动重启）
```

### 插件开发

```bash
cd extension
npm run watch  # 监听文件变化并自动编译
```

然后在VSCode中按 `F5` 启动调试。

## 常见问题

### 1. 后端服务无法启动

- 检查端口3000是否被占用
- 检查环境变量配置是否正确
- 查看 `server/logs/error.log` 日志文件

### 2. 插件无法连接后端

- 确认后端服务已启动
- 检查VSCode配置中的 `quantFree.serverUrl` 设置
- 默认地址为 `http://localhost:3000`

### 3. 策略生成失败

- 检查是否配置了 `DEEPSEEK_API_KEY`（推荐）或 `OPENAI_API_KEY`
- 确认 `AI_PROVIDER` 环境变量设置正确（默认使用 `deepseek`）
- 检查网络连接
- 查看输出面板的错误信息
- 参考 [DeepSeek配置指南](docs/DEEPSEEK_SETUP.md) 获取详细帮助

## 下一步

- 阅读 [README.md](README.md) 了解项目详情
- 查看 [docs/PRD.md](docs/PRD.md) 了解产品设计
- 查看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 了解架构设计

---

**注意**：本项目处于开发阶段，部分功能可能不完整。使用前请仔细阅读文档。


# QuantFree - VSCode股票交易助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue.svg)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![GitHub](https://img.shields.io/badge/GitHub-ZhengWG-181717?style=flat&logo=github)](https://github.com/ZhengWG)

> 一款集成在VSCode编辑器中的股票交易管理插件，为开发者提供实时行情查看、AI驱动的交易策略推荐和自动化交易执行功能。

**作者**：[Zheng Wengang](https://github.com/ZhengWG) | **个人网站**：[johneyzheng.top](https://johneyzheng.top/)

## ✨ 核心功能

### 📈 实时行情监控
- 在VSCode侧边栏实时查看股票、基金、期货数据
- 支持A股、港股、美股等多市场
- 价格提醒、涨跌幅颜色标识
- 快速查看K线图和技术指标

### 🤖 AI策略推荐
- 集成大模型（OpenAI/Claude/本地模型）
- 基于市场数据生成个性化交易策略
- 提供买入/卖出建议、目标价位、止损位
- 策略解释和风险评估

### 💼 交易执行
- 通过券商API执行实际交易
- 支持买入、卖出、撤单等操作
- 查看持仓、订单状态、交易记录
- 交易安全验证和风控

### 📊 数据可视化
- K线图展示（日K、周K、月K）
- 技术指标叠加（MA、MACD、KDJ等）
- 资金流向分析
- 策略回测结果可视化

### 🔄 策略回测
- 基于历史数据测试策略有效性
- 计算收益率、夏普比率等指标
- 生成详细回测报告

## 🚀 快速开始

### 环境要求
- VSCode 1.70+
- **Python 3.10+**（后端服务）
- **Node.js 18+**（VSCode插件前端）
- pip 和 npm

### 环境安装

#### 1. 安装 Python 环境（推荐使用 Conda）

**macOS/Linux:**
```bash
# 安装 Miniconda（如果未安装）
# 下载地址：https://docs.conda.io/en/latest/miniconda.html

# 创建并激活虚拟环境
conda create -n quant_free python=3.10 -y
conda activate quant_free
```

**Windows:**
```powershell
# 安装 Miniconda 后，打开 Anaconda Prompt
conda create -n quant_free python=3.10 -y
conda activate quant_free
```

**或者使用 venv（不使用 Conda 时）:**
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

#### 2. 安装 Node.js 和 npm（推荐使用 nvm）

**macOS/Linux:**
```bash
# 安装 nvm（如果未安装）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell 配置
source ~/.bashrc  # 或 source ~/.zshrc

# 安装 Node.js LTS 版本
nvm install --lts
nvm use --lts

# 验证安装
node --version
npm --version
```

**Windows:**
```powershell
# 使用 nvm-windows
# 下载地址：https://github.com/coreybutler/nvm-windows/releases

# 安装 Node.js LTS 版本
nvm install lts
nvm use lts

# 验证安装
node --version
npm --version
```

**或者直接安装 Node.js:**
- 访问 [Node.js 官网](https://nodejs.org/) 下载并安装 LTS 版本
- 安装完成后验证：`node --version` 和 `npm --version`

#### 3. 安装系统依赖（如需要）

**macOS:**
```bash
# 使用 Homebrew 安装（如需要）
brew install git
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-pip nodejs npm
```

**Windows:**
- 使用 [Git for Windows](https://git-scm.com/download/win) 安装 Git
- 使用上述方法安装 Python 和 Node.js

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/ZhengWG/quant_free.git
cd quant_free
```

2. **安装依赖**

**安装 Python 后端依赖:**
```bash
# 激活虚拟环境（如果使用 conda）
conda activate quant_free

# 或激活 venv（如果使用 venv）
# source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate      # Windows

# 进入后端目录
cd server

# 安装 Python 依赖
pip install -r requirements.txt
```

**安装 VSCode 插件依赖:**
```bash
# 进入插件目录
cd extension

# 如果使用 nvm，确保已加载 nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use node  # 或 nvm use --lts

# 安装 Node.js 依赖
npm install

# 编译 TypeScript（验证安装）
npm run compile
```

3. **配置环境变量**
```bash
# 复制配置文件
cp server/.env.example server/.env

# 编辑 server/.env 文件，填入API密钥：
# - DEEPSEEK_API_KEY: DeepSeek API Key（推荐，用于策略生成）
#   获取地址：https://platform.deepseek.com/
# - TUSHARE_TOKEN: Tushare API Token（获取A股数据，可选）
#   获取地址：https://tushare.pro/
# - AI_PROVIDER: 设置为 "deepseek"（默认）
# - 其他可选配置
```

4. **启动后端服务**
```bash
# 确保已激活虚拟环境
conda activate quant_free  # 或 source venv/bin/activate

# 进入后端目录
cd server

# 启动服务
python main.py

# 服务将在 http://localhost:3000 启动
# API 文档：http://localhost:3000/docs
```

5. **运行插件**
```bash
# 在VSCode中打开项目根目录
# 按 F5 启动调试，或使用命令面板：Run Extension

# 或者编译后打包
cd extension
npm run compile
npm run package  # 生成 .vsix 文件，可在VSCode中安装
```

### 验证安装

运行完整系统测试：
```bash
# 进入测试目录
cd tests

# 运行完整测试（需要后端服务运行）
bash test_full_system.sh

# 或运行所有测试
bash run_all_tests.sh
```

## 📖 使用指南

### 1. 添加自选股
- 使用命令面板：`QuantFree: 添加自选股`
- 或点击侧边栏的"+"按钮
- 输入股票代码（如：000001、600519）

### 2. 查看实时行情
- 在侧边栏查看自选股列表
- 实时显示价格、涨跌幅、成交量
- 点击股票查看详细信息

### 3. 生成策略推荐
- 选择股票，点击"策略推荐"按钮
- 等待AI分析（使用DeepSeek API，约3-5秒）
- 查看策略建议和理由说明
- **注意**：首次使用需要配置 `DEEPSEEK_API_KEY` 环境变量

### 4. 执行交易
- 在交易面板输入订单信息
- 选择市价单或限价单
- 确认后提交订单

### 5. 查看持仓和订单
- 在"持仓"标签查看当前持仓
- 在"订单"标签查看历史订单
- 支持订单状态筛选

## 🏗️ 项目结构

```
quant_free/
├── extension/              # VSCode插件前端（TypeScript）
│   ├── src/
│   │   ├── extension.ts   # 插件入口
│   │   ├── commands/      # 命令处理
│   │   ├── views/         # UI视图
│   │   ├── services/      # 前端服务
│   │   └── types/         # 类型定义
│   ├── package.json
│   └── tsconfig.json
│
├── server/                 # 后端服务（Python）
│   ├── app/
│   │   ├── core/          # 核心配置
│   │   ├── models/        # 数据模型（SQLAlchemy）
│   │   ├── schemas/       # Pydantic模式
│   │   ├── api/           # API路由
│   │   ├── services/      # 业务服务
│   │   └── adapters/      # 外部API适配器
│   ├── main.py            # 服务入口
│   ├── requirements.txt   # Python依赖
│   └── .env.example       # 环境变量模板
│
├── docs/                   # 文档
│   ├── PRD.md            # 产品设计文档
│   └── ARCHITECTURE.md   # 架构设计文档
│
├── README.md
└── .gitignore
```

## 🔧 配置说明

### 行情数据源配置
支持多个数据源，可在配置文件中切换：
- Tushare（推荐，A股数据丰富）
- Alpha Vantage（美股数据）
- 腾讯财经API
- 新浪财经API

### AI模型配置
支持多种AI模型：
- **DeepSeek Chat**（推荐，性价比高，国内访问稳定）
  - 获取API Key：https://platform.deepseek.com/
  - 设置环境变量：`DEEPSEEK_API_KEY=your_key` 和 `AI_PROVIDER=deepseek`
- OpenAI GPT-4（策略质量高，但成本较高）
- Anthropic Claude
- 本地模型（Ollama，免费但需本地部署）

### 券商API配置
支持多个券商API：
- 同花顺API
- 东方财富API
- 雪球API
- 自定义API接口

## 🛡️ 安全说明

- **数据加密**：所有敏感数据（API密钥、交易密码）均加密存储
- **传输安全**：所有API调用使用HTTPS/WSS加密传输
- **权限控制**：交易操作需要二次确认和密码验证
- **日志审计**：所有操作均有日志记录，便于审计

⚠️ **风险提示**：本插件仅提供工具功能，不构成投资建议。投资有风险，入市需谨慎。用户需自行承担交易风险。

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 开发计划

### 第一阶段（MVP）
- [x] 基础插件框架
- [x] 实时行情查看
- [ ] 基础策略推荐
- [ ] 模拟交易功能

### 第二阶段
- [ ] AI策略推荐集成
- [ ] 实盘交易API对接
- [ ] K线图可视化
- [ ] 策略回测功能

### 第三阶段
- [ ] 多市场支持
- [ ] 高级技术指标
- [ ] 策略优化
- [ ] 性能优化

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

本项目参考了以下优秀项目：
- [leek-fund](https://github.com/giscafer/leek-fund) - VSCode股票查看插件
- [FinRL](https://github.com/AI4Finance-Foundation/FinRL) - 强化学习量化交易框架

## 📮 联系方式

- 👤 **作者**：Zheng Wengang (ZhengWG)
- 🏠 **项目主页**：https://github.com/ZhengWG/quant_free
- 🐛 **问题反馈**：https://github.com/ZhengWG/quant_free/issues
- 👨‍💻 **个人主页**：https://github.com/ZhengWG
- 🌐 **个人网站**：https://johneyzheng.top/

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

**注意**：本项目处于开发阶段，功能可能不完整。使用前请仔细阅读文档和风险提示。

Made with ❤️ by [ZhengWG](https://github.com/ZhengWG)

</div>


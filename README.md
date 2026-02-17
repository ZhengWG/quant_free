# QuantFree - VSCode股票交易助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue.svg)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![GitHub](https://img.shields.io/badge/GitHub-ZhengWG-181717?style=flat&logo=github)](https://github.com/ZhengWG)

> 一款集成在VSCode编辑器中的股票交易管理插件，为开发者提供实时行情查看、AI驱动的交易策略推荐和自动化交易执行功能。

**作者**：[Zheng Wengang](https://github.com/ZhengWG) | **个人网站**：[johneyzheng.top](https://johneyzheng.top/)

## 核心功能

### 实时行情监控
- 在VSCode侧边栏实时查看A股行情（新浪财经API，无需Token）
- 支持沪深A股（如 000001 平安银行、600519 贵州茅台）
- 实时价格、涨跌幅、成交量自动刷新
- K线数据查看（腾讯财经API，日K/周K/月K）

### AI策略推荐
- 集成DeepSeek/OpenAI大模型，基于实时行情生成个性化策略
- 提供买入/卖出/持有建议、目标价位、止损位
- 风险评估与置信度评分

### 模拟交易
- 市价单自动获取实时价格成交
- 限价单指定价格成交
- 滑点模拟（0.1% +/- 随机浮动）
- A股手续费：佣金0.025%（最低5元）、印花税0.05%（仅卖出）、过户费0.001%
- 持仓跟踪、成本含费、实时盈亏估值
- 初始模拟资金100万元

### 策略回测
- 基于真实历史K线数据测试策略
- 支持均线交叉（MA Cross）和MACD两种策略
- 计算收益率、夏普比率、最大回撤、胜率等指标
- 返回每笔交易明细

## 快速开始

### 环境要求
- VSCode 1.70+
- Python 3.8+（后端服务）
- Node.js 18+（VSCode插件前端）

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/ZhengWG/quant_free.git
cd quant_free

# 2. 安装后端依赖
cd server
pip install -r requirements.txt

# 3. 配置环境变量（可选，行情数据无需配置）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（用于AI策略生成）

# 4. 启动后端服务
python main.py
# 服务启动在 http://localhost:3000
# API文档：http://localhost:3000/docs

# 5. 安装前端依赖并编译
cd ../extension
npm install
npm run compile
```

### 运行VSCode插件

在VSCode中打开项目根目录，按 `F5` 启动Extension Development Host。

## VSCode插件使用指南

插件启动后，所有功能通过**命令面板**（`Ctrl+Shift+P` / `Cmd+Shift+P`）调用：

### 1. 添加自选股

命令面板输入：`QuantFree: 添加自选股`

```
输入股票代码 → 000001
→ 侧边栏 "行情监控" 面板出现：
  平安银行  ¥10.91  -0.46%
```

支持的代码格式：
- A股：`000001`（平安银行）、`600519`（贵州茅台）
- 6开头自动识别为上交所，其他为深交所

### 2. 删除自选股

命令面板输入：`QuantFree: 删除自选股`

```
→ 弹出已添加的股票列表
→ 选择要删除的代码
→ "已删除 000001"
```

### 3. 查看K线数据

命令面板输入：`QuantFree: 打开K线图`

```
输入股票代码 → 600519
→ 输出面板显示K线数据表：

=== 600519 K线数据 ===

日期            开盘     最高     最低     收盘     成交量
──────────────────────────────────────────────────────────
2025-09-17     1487.00  1510.00  1481.00  1498.00     3218956
2025-09-18     1498.00  1502.00  1478.00  1480.00     4015823
...
共 100 条数据
```

### 4. AI策略推荐

命令面板输入：`QuantFree: 生成策略推荐`

```
输入股票代码 → 000001
→ 输出面板显示AI策略：

=== 策略推荐 ===
股票：000001 (平安银行)
操作建议：HOLD
目标价：¥12.50
止损价：¥9.80
置信度：0.7
风险等级：MEDIUM
AI模型：deepseek
分析理由：基于当前市场数据，建议...
```

> 需要在 `server/.env` 中配置 `DEEPSEEK_API_KEY` 才能获得真实AI分析

### 5. 下单交易

命令面板输入：`QuantFree: 下单`

```
步骤1: 输入股票代码 → 000001
步骤2: 选择操作类型 → 买入 / 卖出
步骤3: 选择价格类型 → 市价单 / 限价单
步骤4: (限价单) 输入价格 → 10.90
步骤5: 输入数量 → 100
步骤6: 确认弹窗 → "确认买入 000001 100股 @ ¥10.90？"

→ 输出面板显示成交结果：

订单成交！
订单号：a85e728f-f59f-4660-a729-14bb2af6e6ec
状态：FILLED
成交价：¥10.91 (滑点 0.092%)
─── 费用明细 ───
  佣金：¥5.00
  印花税：¥0.00
  过户费：¥0.01
  总费用：¥5.01
```

**市价单**会自动获取新浪实时行情价格成交，**限价单**以指定价格+滑点成交。

### 6. 查看持仓

命令面板输入：`QuantFree: 查看持仓`

```
→ 输出面板显示：

=== 当前持仓 ===
平安银行 (000001): 100股, 成本: ¥10.96, 现价: ¥10.91, 盈亏: -¥5.01 (-0.46%), 累计费用: ¥5.01
贵州茅台 (600519): 10股, 成本: ¥1502.26, 现价: ¥1485.30, 盈亏: -¥169.55 (-1.13%), 累计费用: ¥5.15
```

持仓的**现价**为实时行情价格，**成本价**已包含买入手续费。

### 7. 插件配置

命令面板输入：`QuantFree: 打开配置`

可配置项：
| 配置项 | 默认值 | 说明 |
|---|---|---|
| `quantFree.serverUrl` | `http://localhost:3000` | 后端服务地址 |
| `quantFree.refreshInterval` | `5000` | 行情刷新间隔（毫秒） |
| `quantFree.aiModel` | `deepseek` | AI模型选择 |

## API使用样例

后端服务启动后，也可以直接通过API调用。完整文档访问 http://localhost:3000/docs

### 获取实时行情

```bash
curl 'http://localhost:3000/api/v1/market/realtime?codes=000001,600519'
```

```json
{
  "success": true,
  "data": [
    {
      "code": "000001", "name": "平安银行", "market": "A股",
      "price": 10.91, "change": -0.05, "change_percent": -0.46,
      "volume": 55504736, "high": 10.99, "low": 10.90,
      "open": 10.96, "pre_close": 10.96
    }
  ]
}
```

### 获取K线数据

```bash
# 日K线
curl 'http://localhost:3000/api/v1/market/kline/600519?type=day'
# 周K线
curl 'http://localhost:3000/api/v1/market/kline/600519?type=week'
```

### 市价买入

```bash
curl -X POST http://localhost:3000/api/v1/trade/order \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"000001","type":"BUY","order_type":"MARKET","quantity":100}'
```

```json
{
  "success": true,
  "data": {
    "status": "FILLED", "filled_price": 10.92, "slippage": 0.081,
    "commission": 5.0, "stamp_tax": 0.0, "transfer_fee": 0.01, "total_fee": 5.01
  }
}
```

### 卖出（含印花税）

```bash
curl -X POST http://localhost:3000/api/v1/trade/order \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"000001","type":"SELL","order_type":"MARKET","quantity":50}'
```

### 查看持仓和账户

```bash
# 持仓（实时估值）
curl http://localhost:3000/api/v1/trade/positions
# 账户信息
curl http://localhost:3000/api/v1/trade/account
```

### 策略回测

```bash
curl -X POST http://localhost:3000/api/v1/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"000001","strategy":"ma_cross","start_date":"2025-06-01","end_date":"2026-02-17"}'
```

```json
{
  "success": true,
  "data": {
    "total_return_percent": -0.02, "sharpe_ratio": -0.1874,
    "max_drawdown": 0.51, "win_rate": 66.67, "total_trades": 3,
    "trades": [
      {"date": "2025-10-10", "action": "BUY", "price": 11.054, "quantity": 100},
      {"date": "2025-11-07", "action": "SELL", "price": 10.934, "quantity": 100, "profit": -12.0}
    ]
  }
}
```

支持的策略：`ma_cross`（均线交叉）、`macd`（MACD金叉死叉）

### AI策略生成

```bash
curl -X POST http://localhost:3000/api/v1/strategy/generate \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"000001","risk_level":"MEDIUM"}'
```

## 项目结构

```
quant_free/
├── extension/              # VSCode插件前端（TypeScript）
│   ├── src/
│   │   ├── extension.ts   # 插件入口，注册7个命令
│   │   ├── views/         # MarketDataView, StrategyView, TradeView
│   │   ├── services/      # ApiClient, WebSocketClient, StorageService
│   │   ├── types/         # TypeScript类型定义
│   │   └── utils/         # 格式化、验证工具
│   ├── package.json
│   └── tsconfig.json
│
├── server/                 # 后端服务（Python FastAPI）
│   ├── app/
│   │   ├── core/          # 配置、数据库
│   │   ├── models/        # SQLAlchemy模型（Order, Position, Strategy...）
│   │   ├── schemas/       # Pydantic请求/响应模式
│   │   ├── api/routes/    # market, strategy, trade, backtest 路由
│   │   ├── services/      # 业务逻辑（行情、交易、回测、WebSocket）
│   │   └── adapters/      # 新浪/腾讯行情API、DeepSeek/OpenAI AI服务
│   ├── main.py            # FastAPI入口
│   ├── requirements.txt
│   └── .env.example       # 环境变量模板
│
├── tests/                  # API测试、WebSocket测试
├── docs/                   # PRD、架构设计文档
└── README.md
```

## 配置说明

### 行情数据源（已接入，无需配置）
- **新浪财经API** — 实时行情（A股、港股）
- **腾讯财经API** — K线数据、历史数据

### AI模型配置（可选）
在 `server/.env` 中配置：
- **DeepSeek Chat**（推荐）：设置 `DEEPSEEK_API_KEY` 和 `AI_PROVIDER=deepseek`
- **OpenAI GPT-4**：设置 `OPENAI_API_KEY` 和 `AI_PROVIDER=openai`
- 未配置时策略生成返回模拟结果

### 交易费率（模拟交易）
| 费用项 | 费率 | 说明 |
|---|---|---|
| 佣金 | 0.025% | 双向收取，最低¥5 |
| 印花税 | 0.05% | 仅卖出收取 |
| 过户费 | 0.001% | 双向收取 |
| 滑点 | ~0.1% | 随机模拟 |

## 开发进度

### 第一阶段（MVP）-- 已完成
- [x] 基础插件框架（VSCode Extension + FastAPI后端）
- [x] 实时行情查看（新浪API，A股实时数据）
- [x] K线数据和历史行情（腾讯API，日K/周K/月K）
- [x] AI策略推荐（DeepSeek/OpenAI集成）
- [x] 模拟交易（市价/限价单、滑点、手续费、持仓管理）
- [x] 策略回测（MA交叉、MACD策略，计算夏普比率等）
- [x] 自选股管理（添加/删除）
- [x] WebSocket实时推送架构

### 第二阶段（计划中）
- [ ] 实盘交易API对接（券商API）
- [ ] K线图可视化（WebView图表）
- [ ] 更多回测策略（KDJ、布林带等）
- [ ] 交易记录导出

### 第三阶段
- [ ] 多市场支持（港股、美股实时行情）
- [ ] 高级技术指标
- [ ] 策略优化与参数调优
- [ ] 性能优化

## 安全说明

- 所有敏感数据（API密钥）通过 `.env` 管理，不进入版本控制
- 当前为**模拟交易模式**，不涉及真实资金
- 交易操作有二次确认弹窗

> **风险提示**：本插件仅提供工具功能，不构成投资建议。投资有风险，入市需谨慎。

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 致谢

本项目参考了以下优秀项目：
- [leek-fund](https://github.com/giscafer/leek-fund) - VSCode股票查看插件
- [FinRL](https://github.com/AI4Finance-Foundation/FinRL) - 强化学习量化交易框架

## 联系方式

- **作者**：Zheng Wengang (ZhengWG)
- **项目主页**：https://github.com/ZhengWG/quant_free
- **问题反馈**：https://github.com/ZhengWG/quant_free/issues
- **个人网站**：https://johneyzheng.top/

---

<div align="center">

**如果这个项目对你有帮助，请给个 Star！**

Made with by [ZhengWG](https://github.com/ZhengWG)

</div>

# 项目架构设计文档

## 1. 架构概述

### 1.1 架构原则
- **模块化设计**：各功能模块独立，便于维护和扩展
- **前后端分离**：VSCode插件作为前端，Node.js服务作为后端
- **可扩展性**：支持多数据源、多券商API、多AI模型
- **安全性优先**：数据加密、权限控制、审计日志

### 1.2 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      VSCode插件层 (Frontend)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 行情监控UI   │  │ 策略推荐UI   │  │ 交易执行UI   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 数据可视化   │  │ 配置管理UI   │  │ 通知提醒UI   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          VSCode Extension API (TypeScript)            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ IPC / HTTP
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端服务层 (Backend Service)              │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API Gateway / Router                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 行情数据服务 │  │ 策略生成服务 │  │ 交易执行服务 │      │
│  │ MarketData   │  │ StrategyGen  │  │ TradeExec    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 数据缓存服务 │  │ 回测引擎     │  │ 通知服务     │      │
│  │ CacheService │  │ Backtest     │  │ Notification │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              数据访问层 (Data Access Layer)            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ SQLite     │  │ Redis    │  │ File     │         │  │
│  │  │ (本地DB)   │  │ (缓存)   │  │ (日志)   │         │  │
│  │  └──────────┘  └──────────┘  └──────────┘         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   外部服务层 (External Services)             │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 行情数据API  │  │ 大模型API    │  │ 券商交易API  │      │
│  │              │  │              │  │              │      │
│  │ • Tushare    │  │ • OpenAI     │  │ • 同花顺API  │      │
│  │ • Alpha      │  │ • Claude     │  │ • 东方财富   │      │
│  │   Vantage    │  │ • Ollama     │  │ • 雪球API    │      │
│  │ • 腾讯财经   │  │ • 本地模型   │  │ • 自定义API  │      │
│  │ • 新浪财经   │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 2. 详细架构设计

### 2.1 VSCode插件层架构

#### 2.1.1 目录结构
```
src/
├── extension.ts              # 插件入口文件
├── commands/                 # 命令处理
│   ├── marketData.ts
│   ├── strategy.ts
│   └── trade.ts
├── views/                    # UI视图
│   ├── MarketDataView.tsx
│   ├── StrategyView.tsx
│   ├── TradeView.tsx
│   └── ChartView.tsx
├── services/                 # 前端服务
│   ├── apiClient.ts         # API客户端
│   ├── websocketClient.ts   # WebSocket客户端
│   └── storage.ts           # 本地存储
├── utils/                    # 工具函数
│   ├── formatters.ts
│   └── validators.ts
└── types/                    # TypeScript类型定义
    ├── market.ts
    ├── strategy.ts
    └── trade.ts
```

#### 2.1.2 核心模块

**Extension.ts (插件入口)**
```typescript
// 职责：
// 1. 插件激活和注销
// 2. 注册命令和视图
// 3. 初始化服务
// 4. 管理生命周期
```

**API Client (API客户端)**
```typescript
// 职责：
// 1. 与后端服务通信
// 2. 请求封装和错误处理
// 3. 数据格式转换
// 4. 请求重试机制
```

**WebSocket Client (实时数据)**
```typescript
// 职责：
// 1. 建立WebSocket连接
// 2. 接收实时行情数据
// 3. 处理连接断开和重连
```

### 2.2 后端服务层架构

#### 2.2.1 目录结构
```
server/
├── src/
│   ├── index.ts              # 服务入口
│   ├── routes/               # 路由定义
│   │   ├── market.ts
│   │   ├── strategy.ts
│   │   └── trade.ts
│   ├── services/             # 业务服务
│   │   ├── MarketDataService.ts
│   │   ├── StrategyService.ts
│   │   ├── TradeService.ts
│   │   ├── BacktestService.ts
│   │   └── NotificationService.ts
│   ├── adapters/             # 外部API适配器
│   │   ├── market/
│   │   │   ├── TushareAdapter.ts
│   │   │   ├── AlphaVantageAdapter.ts
│   │   │   └── TencentAdapter.ts
│   │   ├── ai/
│   │   │   ├── OpenAIService.ts
│   │   │   ├── ClaudeService.ts
│   │   │   └── OllamaService.ts
│   │   └── broker/
│   │       ├── TonghuashunAdapter.ts
│   │       └── EastMoneyAdapter.ts
│   ├── models/               # 数据模型
│   │   ├── Stock.ts
│   │   ├── Strategy.ts
│   │   └── Order.ts
│   ├── database/             # 数据库操作
│   │   ├── db.ts
│   │   └── repositories/
│   ├── cache/                # 缓存服务
│   │   └── CacheManager.ts
│   ├── utils/                # 工具函数
│   │   ├── logger.ts
│   │   ├── encrypt.ts
│   │   └── validators.ts
│   └── config/               # 配置文件
│       └── config.ts
├── tests/                    # 测试文件
└── package.json
```

#### 2.2.2 核心服务模块

**MarketDataService (行情数据服务)**
```typescript
// 职责：
// 1. 获取实时行情数据
// 2. 数据缓存管理
// 3. 多数据源切换
// 4. 数据格式统一

// 接口：
interface MarketDataService {
  getRealTimeData(codes: string[]): Promise<StockData[]>
  getHistoryData(code: string, period: string): Promise<HistoryData[]>
  getKLineData(code: string, type: string): Promise<KLineData[]>
  subscribeRealTime(codes: string[]): void
}
```

**StrategyService (策略生成服务)**
```typescript
// 职责：
// 1. 调用AI模型生成策略
// 2. 策略数据准备
// 3. 策略结果解析
// 4. 策略缓存

// 接口：
interface StrategyService {
  generateStrategy(params: StrategyParams): Promise<Strategy>
  explainStrategy(strategy: Strategy): Promise<string>
  evaluateStrategy(strategy: Strategy): Promise<StrategyScore>
}
```

**TradeService (交易执行服务)**
```typescript
// 职责：
// 1. 订单提交
// 2. 订单查询
// 3. 持仓查询
// 4. 账户信息查询
// 5. 交易风控

// 接口：
interface TradeService {
  placeOrder(order: Order): Promise<OrderResult>
  cancelOrder(orderId: string): Promise<boolean>
  getPositions(): Promise<Position[]>
  getAccountInfo(): Promise<AccountInfo>
  getOrders(status?: string): Promise<Order[]>
}
```

**BacktestService (回测服务)**
```typescript
// 职责：
// 1. 策略回测执行
// 2. 回测指标计算
// 3. 回测报告生成

// 接口：
interface BacktestService {
  runBacktest(strategy: Strategy, period: string): Promise<BacktestResult>
  calculateMetrics(result: BacktestResult): Promise<Metrics>
  generateReport(result: BacktestResult): Promise<Report>
}
```

### 2.3 数据流设计

#### 2.3.1 实时行情数据流
```
行情数据源 → MarketDataService → Cache → WebSocket → VSCode插件 → UI更新
                ↓
            SQLite (历史数据存储)
```

#### 2.3.2 策略生成数据流
```
用户请求 → StrategyService → 收集市场数据 → AI模型API → 策略解析 → 返回结果
                ↓                                    ↓
            Cache (策略缓存)                    Cache (请求缓存)
```

#### 2.3.3 交易执行数据流
```
用户下单 → TradeService → 风控检查 → 券商API → 订单确认 → 结果返回
                ↓              ↓
            日志记录      异常处理
```

### 2.4 数据模型设计

#### 2.4.1 核心数据模型

**Stock (股票)**
```typescript
interface Stock {
  code: string              // 股票代码
  name: string              // 股票名称
  market: string            // 市场（A股/港股/美股）
  price: number             // 当前价格
  change: number            // 涨跌额
  changePercent: number     // 涨跌幅
  volume: number            // 成交量
  amount: number            // 成交额
  high: number              // 最高价
  low: number               // 最低价
  open: number              // 开盘价
  preClose: number          // 昨收价
  timestamp: Date           // 时间戳
}
```

**Strategy (策略)**
```typescript
interface Strategy {
  id: string
  stockCode: string
  action: 'BUY' | 'SELL' | 'HOLD'
  targetPrice: number
  stopLoss: number
  confidence: number        // 置信度 0-1
  reasoning: string         // 策略理由
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH'
  timeHorizon: string       // 持仓周期
  createdAt: Date
  aiModel: string           // 使用的AI模型
}
```

**Order (订单)**
```typescript
interface Order {
  id: string
  stockCode: string
  stockName: string
  type: 'BUY' | 'SELL'
  orderType: 'MARKET' | 'LIMIT'  // 市价单/限价单
  price?: number            // 限价单价格
  quantity: number          // 数量
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED'
  filledQuantity: number
  filledPrice: number
  createdAt: Date
  updatedAt: Date
}
```

**Position (持仓)**
```typescript
interface Position {
  stockCode: string
  stockName: string
  quantity: number          // 持仓数量
  costPrice: number         // 成本价
  currentPrice: number      // 当前价
  marketValue: number       // 市值
  profit: number            // 盈亏
  profitPercent: number     // 盈亏比例
}
```

### 2.5 数据库设计

#### 2.5.1 SQLite表结构

**stocks (自选股表)**
```sql
CREATE TABLE stocks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  name TEXT,
  market TEXT,
  group_name TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(code, market)
);
```

**strategies (策略表)**
```sql
CREATE TABLE strategies (
  id TEXT PRIMARY KEY,
  stock_code TEXT NOT NULL,
  action TEXT NOT NULL,
  target_price REAL,
  stop_loss REAL,
  confidence REAL,
  reasoning TEXT,
  risk_level TEXT,
  time_horizon TEXT,
  ai_model TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**orders (订单表)**
```sql
CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  stock_code TEXT NOT NULL,
  stock_name TEXT,
  type TEXT NOT NULL,
  order_type TEXT NOT NULL,
  price REAL,
  quantity INTEGER NOT NULL,
  status TEXT NOT NULL,
  filled_quantity INTEGER DEFAULT 0,
  filled_price REAL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**positions (持仓表)**
```sql
CREATE TABLE positions (
  stock_code TEXT PRIMARY KEY,
  stock_name TEXT,
  quantity INTEGER NOT NULL,
  cost_price REAL NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**market_data_cache (行情缓存表)**
```sql
CREATE TABLE market_data_cache (
  code TEXT PRIMARY KEY,
  data TEXT NOT NULL,        -- JSON格式
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.6 安全架构

#### 2.6.1 认证与授权
```
用户 → VSCode插件 → 后端服务 → 券商API
        ↓            ↓
    本地存储      JWT Token
    (加密)        (API密钥)
```

#### 2.6.2 数据加密
- **存储加密**：使用VSCode的`SecretStorage` API
- **传输加密**：HTTPS/WSS
- **敏感数据**：API密钥、交易密码使用AES-256加密

#### 2.6.3 权限控制
- **只读权限**：行情查看、策略查看
- **交易权限**：下单、撤单（需要额外验证）
- **配置权限**：账户配置、API配置

### 2.7 性能优化

#### 2.7.1 缓存策略
- **行情数据缓存**：Redis + 内存缓存，TTL=5秒
- **策略结果缓存**：相同参数策略缓存1小时
- **历史数据缓存**：SQLite本地存储

#### 2.7.2 请求优化
- **批量请求**：多个股票数据合并请求
- **请求去重**：相同请求合并处理
- **限流控制**：API调用频率限制

#### 2.7.3 数据更新策略
- **实时数据**：WebSocket推送
- **历史数据**：定时拉取
- **增量更新**：只更新变化的数据

## 3. 技术选型详细说明

### 3.1 前端技术栈

| 技术 | 版本 | 用途 | 理由 |
|------|------|------|------|
| TypeScript | 5.x | 开发语言 | 类型安全，VSCode官方推荐 |
| React | 18.x | UI框架 | 组件化开发，生态丰富 |
| VSCode API | Latest | 插件API | 官方API，功能完善 |
| ECharts | 5.x | 图表库 | 功能强大，支持K线图 |
| WebSocket | Native | 实时通信 | 低延迟，双向通信 |

### 3.2 后端技术栈

| 技术 | 版本 | 用途 | 理由 |
|------|------|------|------|
| Node.js | 18+ | 运行时 | 与前端技术栈统一 |
| Express | 4.x | Web框架 | 轻量级，生态丰富 |
| TypeScript | 5.x | 开发语言 | 类型安全 |
| SQLite | 3.x | 数据库 | 轻量级，无需额外服务 |
| Redis | 7.x | 缓存 | 高性能，可选 |

### 3.3 外部服务

| 服务 | 用途 | 备选方案 |
|------|------|----------|
| Tushare | A股数据 | 腾讯财经、新浪财经 |
| Alpha Vantage | 美股数据 | Yahoo Finance |
| OpenAI | AI策略 | Claude、本地模型 |
| 同花顺API | 交易执行 | 东方财富、雪球 |

## 4. 部署架构

### 4.1 开发环境
```
本地开发：
VSCode插件 (本地) ←→ 后端服务 (localhost:3000) ←→ 外部API
```

### 4.2 生产环境（可选）
```
用户环境：
VSCode插件 (用户本地) ←→ 后端服务 (用户本地/云服务) ←→ 外部API
```

## 5. 扩展性设计

### 5.1 插件化架构
- **数据源插件**：支持自定义数据源
- **AI模型插件**：支持自定义AI模型
- **交易接口插件**：支持自定义券商API

### 5.2 配置化设计
- 所有外部服务通过配置文件管理
- 支持多环境配置（开发/测试/生产）
- 支持用户自定义配置

## 6. 监控与日志

### 6.1 日志系统
- **前端日志**：VSCode Output Channel
- **后端日志**：Winston日志库
- **日志级别**：DEBUG/INFO/WARN/ERROR
- **日志存储**：本地文件 + 可选云存储

### 6.2 监控指标
- API响应时间
- 错误率
- 缓存命中率
- 交易成功率

---

**文档版本**：v1.0  
**最后更新**：2025年  
**维护者**：ZhengWG


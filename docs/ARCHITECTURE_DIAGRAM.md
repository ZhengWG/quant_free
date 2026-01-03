# 架构设计图（详细版）

## 1. 系统整体架构图

### 1.1 三层架构图

```mermaid
graph TB
    subgraph "VSCode插件层 (Frontend)"
        A[Extension入口] --> B[命令处理器]
        A --> C[视图管理器]
        B --> D[行情监控UI]
        B --> E[策略推荐UI]
        B --> F[交易执行UI]
        C --> G[数据可视化]
        C --> H[配置管理]
    end
    
    subgraph "后端服务层 (Backend)"
        I[API Gateway] --> J[行情数据服务]
        I --> K[策略生成服务]
        I --> L[交易执行服务]
        J --> M[数据缓存]
        K --> N[AI模型适配器]
        L --> O[券商API适配器]
        M --> P[(SQLite数据库)]
    end
    
    subgraph "外部服务层 (External)"
        Q[行情数据API<br/>Tushare/Alpha Vantage]
        R[大模型API<br/>OpenAI/Claude]
        S[券商交易API<br/>同花顺/东方财富]
    end
    
    D --> I
    E --> I
    F --> I
    J --> Q
    K --> R
    L --> S
```

### 1.2 数据流架构图

```mermaid
sequenceDiagram
    participant User as 用户
    participant UI as VSCode插件UI
    participant API as 后端API
    participant Cache as 缓存层
    participant External as 外部API
    
    User->>UI: 查看行情
    UI->>API: 请求行情数据
    API->>Cache: 检查缓存
    alt 缓存命中
        Cache-->>API: 返回缓存数据
    else 缓存未命中
        API->>External: 请求外部API
        External-->>API: 返回数据
        API->>Cache: 更新缓存
    end
    API-->>UI: 返回数据
    UI-->>User: 显示行情
    
    User->>UI: 生成策略
    UI->>API: 请求策略推荐
    API->>External: 调用AI模型
    External-->>API: 返回策略
    API-->>UI: 返回策略
    UI-->>User: 显示策略
    
    User->>UI: 执行交易
    UI->>API: 提交订单
    API->>External: 调用券商API
    External-->>API: 返回结果
    API-->>UI: 返回结果
    UI-->>User: 显示结果
```

## 2. 模块详细设计

### 2.1 VSCode插件模块架构

```
┌─────────────────────────────────────────────────────────┐
│                  VSCode Extension                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │            Extension.ts (入口文件)                │  │
│  │  • activate() - 插件激活                          │  │
│  │  • deactivate() - 插件注销                        │  │
│  │  • 注册命令和视图                                  │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                               │
│        ┌─────────────────┼─────────────────┐            │
│        │                 │                 │            │
│        ▼                 ▼                 ▼            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │ Commands │    │  Views   │    │ Services │         │
│  │          │    │          │    │          │         │
│  │ • Market │    │ • Market │    │ • API    │         │
│  │ • Strategy│   │ • Strategy│   │ • WebSocket│        │
│  │ • Trade  │    │ • Trade  │    │ • Storage│         │
│  └──────────┘    └──────────┘    └──────────┘         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 后端服务模块架构

```
┌─────────────────────────────────────────────────────────┐
│                  Backend Service                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Express Server                       │  │
│  │  • HTTP API路由                                   │  │
│  │  • WebSocket服务                                  │  │
│  │  • 中间件（认证、日志、错误处理）                  │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                               │
│        ┌─────────────────┼─────────────────┐            │
│        │                 │                 │            │
│        ▼                 ▼                 ▼            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │ Services │    │ Adapters │    │ Database │         │
│  │          │    │          │    │          │         │
│  │ • Market │    │ • Market │    │ • SQLite │         │
│  │ • Strategy│   │ • AI     │    │ • Redis  │         │
│  │ • Trade  │    │ • Broker │    │ • Files  │         │
│  │ • Backtest│   │          │    │          │         │
│  └──────────┘    └──────────┘    └──────────┘         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 3. 核心服务详细设计

### 3.1 行情数据服务架构

```mermaid
graph LR
    A[MarketDataService] --> B[数据源管理器]
    B --> C[Tushare适配器]
    B --> D[Alpha Vantage适配器]
    B --> E[腾讯财经适配器]
    A --> F[缓存管理器]
    F --> G[Redis缓存]
    F --> H[内存缓存]
    A --> I[数据转换器]
    I --> J[统一数据格式]
    A --> K[WebSocket推送]
```

### 3.2 策略生成服务架构

```mermaid
graph TB
    A[StrategyService] --> B[数据收集器]
    B --> C[市场数据]
    B --> D[技术指标]
    B --> E[历史数据]
    A --> F[提示词构建器]
    F --> G[策略模板]
    A --> H[AI模型适配器]
    H --> I[OpenAI服务]
    H --> J[Claude服务]
    H --> K[Ollama服务]
    A --> L[结果解析器]
    L --> M[策略对象]
    A --> N[策略评估器]
    N --> O[风险评估]
    N --> P[收益预测]
```

### 3.3 交易执行服务架构

```mermaid
graph TB
    A[TradeService] --> B[订单管理器]
    B --> C[订单验证]
    B --> D[风控检查]
    A --> E[券商适配器]
    E --> F[同花顺适配器]
    E --> G[东方财富适配器]
    E --> H[雪球适配器]
    A --> I[状态管理器]
    I --> J[订单状态跟踪]
    A --> K[日志记录器]
    K --> L[交易日志]
```

## 4. 数据库ER图

```mermaid
erDiagram
    STOCKS ||--o{ STRATEGIES : "has"
    STOCKS ||--o{ ORDERS : "has"
    STOCKS ||--o{ POSITIONS : "has"
    ORDERS ||--o{ ORDER_HISTORY : "has"
    
    STOCKS {
        string code PK
        string name
        string market
        string group_name
        datetime created_at
    }
    
    STRATEGIES {
        string id PK
        string stock_code FK
        string action
        float target_price
        float stop_loss
        float confidence
        text reasoning
        string risk_level
        datetime created_at
    }
    
    ORDERS {
        string id PK
        string stock_code FK
        string type
        string order_type
        float price
        int quantity
        string status
        datetime created_at
    }
    
    POSITIONS {
        string stock_code PK
        string stock_name
        int quantity
        float cost_price
        datetime updated_at
    }
```

## 5. API接口设计

### 5.1 RESTful API结构

```
/api/v1/
├── market/
│   ├── GET /realtime/:codes      # 获取实时行情
│   ├── GET /history/:code        # 获取历史数据
│   ├── GET /kline/:code          # 获取K线数据
│   └── POST /subscribe           # 订阅实时数据
│
├── strategy/
│   ├── POST /generate            # 生成策略
│   ├── GET /:id                  # 获取策略详情
│   ├── GET /history              # 获取历史策略
│   └── POST /evaluate            # 评估策略
│
├── trade/
│   ├── POST /order               # 提交订单
│   ├── DELETE /order/:id         # 撤销订单
│   ├── GET /orders               # 查询订单
│   ├── GET /positions            # 查询持仓
│   └── GET /account              # 查询账户
│
└── backtest/
    ├── POST /run                 # 运行回测
    ├── GET /:id                  # 获取回测结果
    └── GET /report/:id           # 获取回测报告
```

### 5.2 WebSocket事件

```typescript
// 客户端 → 服务端
{
  "type": "subscribe",
  "data": { "codes": ["000001", "600519"] }
}

{
  "type": "unsubscribe",
  "data": { "codes": ["000001"] }
}

// 服务端 → 客户端
{
  "type": "market_data",
  "data": {
    "code": "000001",
    "price": 12.50,
    "change": 0.30,
    "timestamp": "2024-01-01T10:00:00Z"
  }
}

{
  "type": "order_update",
  "data": {
    "orderId": "12345",
    "status": "FILLED",
    "filledPrice": 12.50
  }
}
```

## 6. 部署架构图

### 6.1 开发环境

```
┌─────────────────┐
│  开发者机器      │
│                 │
│  ┌───────────┐  │
│  │ VSCode    │  │
│  │ Extension │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ Backend   │  │
│  │ Service   │  │
│  │ localhost │  │
│  └─────┬─────┘  │
└────────┼────────┘
         │
         ▼
┌─────────────────┐
│   外部API        │
│  • 行情数据      │
│  • AI模型        │
│  • 券商API       │
└─────────────────┘
```

### 6.2 生产环境（可选云部署）

```
┌─────────────────┐
│   用户机器       │
│  ┌───────────┐  │
│  │ VSCode    │  │
│  │ Extension │  │
│  └─────┬─────┘  │
└────────┼────────┘
         │ HTTPS/WSS
         ▼
┌─────────────────┐
│   云服务器       │
│  ┌───────────┐  │
│  │ Backend   │  │
│  │ Service   │  │
│  └─────┬─────┘  │
│  ┌─────▼─────┐  │
│  │ Database  │  │
│  │ (SQLite)  │  │
│  └───────────┘  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   外部API        │
└─────────────────┘
```

## 7. 安全架构图

```
┌─────────────────────────────────────────┐
│           安全层架构                     │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  传输层安全                       │  │
│  │  • HTTPS (TLS 1.3)               │  │
│  │  • WSS (WebSocket Secure)        │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  认证授权层                       │  │
│  │  • JWT Token                      │  │
│  │  • API Key验证                    │  │
│  │  • 交易密码验证                   │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  数据加密层                       │  │
│  │  • AES-256加密存储               │  │
│  │  • VSCode SecretStorage          │  │
│  │  • 敏感数据脱敏                   │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  审计日志层                       │  │
│  │  • 操作日志记录                   │  │
│  │  • 交易日志记录                   │  │
│  │  • 异常日志记录                   │  │
│  └──────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

## 8. 性能优化架构

```
┌─────────────────────────────────────────┐
│           性能优化策略                   │
├─────────────────────────────────────────┤
│                                         │
│  1. 缓存策略                            │
│     • Redis缓存 (热点数据)              │
│     • 内存缓存 (实时数据)               │
│     • SQLite缓存 (历史数据)             │
│                                         │
│  2. 请求优化                            │
│     • 批量请求合并                      │
│     • 请求去重                          │
│     • 限流控制                          │
│                                         │
│  3. 数据更新策略                        │
│     • WebSocket推送 (实时数据)          │
│     • 定时拉取 (历史数据)               │
│     • 增量更新 (只更新变化)             │
│                                         │
│  4. 异步处理                            │
│     • 策略生成异步化                    │
│     • 回测任务队列化                    │
│     • 日志写入异步化                    │
│                                         │
└─────────────────────────────────────────┘
```

---

**文档版本**：v1.0  
**最后更新**：2025年  
**维护者**：ZhengWG


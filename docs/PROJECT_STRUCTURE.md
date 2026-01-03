# 项目结构说明

## 完整项目结构

```
quant_free/
├── extension/                    # VSCode插件前端
│   ├── src/
│   │   ├── extension.ts         # 插件入口文件
│   │   ├── commands/            # 命令处理模块
│   │   │   ├── marketData.ts    # 行情数据命令
│   │   │   ├── strategy.ts      # 策略相关命令
│   │   │   └── trade.ts         # 交易相关命令
│   │   ├── views/               # UI视图组件
│   │   │   ├── MarketDataView.tsx    # 行情监控视图
│   │   │   ├── StrategyView.tsx      # 策略推荐视图
│   │   │   ├── TradeView.tsx         # 交易执行视图
│   │   │   ├── ChartView.tsx         # K线图视图
│   │   │   └── ConfigView.tsx        # 配置管理视图
│   │   ├── services/            # 前端服务
│   │   │   ├── apiClient.ts     # API客户端
│   │   │   ├── websocketClient.ts  # WebSocket客户端
│   │   │   └── storage.ts       # 本地存储服务
│   │   ├── utils/               # 工具函数
│   │   │   ├── formatters.ts    # 数据格式化
│   │   │   └── validators.ts    # 数据验证
│   │   └── types/               # TypeScript类型定义
│   │       ├── market.ts        # 行情数据类型
│   │       ├── strategy.ts      # 策略类型
│   │       ├── trade.ts         # 交易类型
│   │       └── common.ts        # 通用类型
│   ├── package.json             # 插件配置文件
│   ├── tsconfig.json            # TypeScript配置
│   ├── webpack.config.js        # Webpack配置
│   └── .vscodeignore            # VSCode发布忽略文件
│
├── server/                       # 后端服务
│   ├── src/
│   │   ├── index.ts             # 服务入口文件
│   │   ├── routes/              # 路由定义
│   │   │   ├── market.ts        # 行情数据路由
│   │   │   ├── strategy.ts      # 策略路由
│   │   │   ├── trade.ts         # 交易路由
│   │   │   └── backtest.ts      # 回测路由
│   │   ├── services/            # 业务服务层
│   │   │   ├── MarketDataService.ts      # 行情数据服务
│   │   │   ├── StrategyService.ts        # 策略生成服务
│   │   │   ├── TradeService.ts           # 交易执行服务
│   │   │   ├── BacktestService.ts        # 回测服务
│   │   │   └── NotificationService.ts    # 通知服务
│   │   ├── adapters/            # 外部API适配器
│   │   │   ├── market/          # 行情数据适配器
│   │   │   │   ├── TushareAdapter.ts
│   │   │   │   ├── AlphaVantageAdapter.ts
│   │   │   │   └── TencentAdapter.ts
│   │   │   ├── ai/              # AI模型适配器
│   │   │   │   ├── OpenAIService.ts
│   │   │   │   ├── ClaudeService.ts
│   │   │   │   └── OllamaService.ts
│   │   │   └── broker/          # 券商API适配器
│   │   │       ├── TonghuashunAdapter.ts
│   │   │       ├── EastMoneyAdapter.ts
│   │   │       └── BaseBrokerAdapter.ts
│   │   ├── models/              # 数据模型
│   │   │   ├── Stock.ts
│   │   │   ├── Strategy.ts
│   │   │   ├── Order.ts
│   │   │   └── Position.ts
│   │   ├── database/            # 数据库操作
│   │   │   ├── db.ts            # 数据库连接
│   │   │   └── repositories/    # 数据仓库
│   │   │       ├── StockRepository.ts
│   │   │       ├── StrategyRepository.ts
│   │   │       └── OrderRepository.ts
│   │   ├── cache/               # 缓存服务
│   │   │   └── CacheManager.ts
│   │   ├── utils/               # 工具函数
│   │   │   ├── logger.ts        # 日志工具
│   │   │   ├── encrypt.ts       # 加密工具
│   │   │   ├── validators.ts    # 验证工具
│   │   │   └── formatters.ts    # 格式化工具
│   │   └── config/              # 配置文件
│   │       ├── config.ts        # 配置管理
│   │       └── constants.ts     # 常量定义
│   ├── tests/                   # 测试文件
│   │   ├── unit/                # 单元测试
│   │   └── integration/         # 集成测试
│   ├── package.json             # 后端依赖配置
│   ├── tsconfig.json            # TypeScript配置
│   ├── .env.example             # 环境变量示例
│   └── jest.config.js           # Jest测试配置
│
├── docs/                        # 文档目录
│   ├── PRD.md                   # 产品设计文档
│   ├── ARCHITECTURE.md          # 架构设计文档
│   ├── ARCHITECTURE_DIAGRAM.md  # 架构图文档
│   ├── API.md                   # API接口文档
│   └── DEVELOPMENT.md           # 开发指南
│
├── scripts/                     # 脚本文件
│   ├── setup.sh                 # 项目初始化脚本
│   ├── build.sh                 # 构建脚本
│   └── deploy.sh                # 部署脚本
│
├── .gitignore                   # Git忽略文件
├── README.md                     # 项目说明
├── LICENSE                       # 许可证
└── package.json                  # 根目录package.json（工作区配置）
```

## 目录说明

### extension/ - VSCode插件
- **src/extension.ts**: 插件主入口，负责激活和注册功能
- **commands/**: 处理VSCode命令（如添加自选股、生成策略等）
- **views/**: React组件，构建插件UI界面
- **services/**: 前端服务层，处理与后端的通信
- **utils/**: 工具函数
- **types/**: TypeScript类型定义

### server/ - 后端服务
- **src/index.ts**: Express服务器入口
- **routes/**: API路由定义
- **services/**: 业务逻辑服务
- **adapters/**: 外部API适配器（行情、AI、券商）
- **models/**: 数据模型定义
- **database/**: 数据库操作和仓库模式
- **cache/**: 缓存管理
- **utils/**: 工具函数

### docs/ - 文档
- 产品设计、架构设计、API文档等

### scripts/ - 脚本
- 项目初始化、构建、部署等自动化脚本

## 开发工作流

1. **前端开发**: 在 `extension/` 目录下开发VSCode插件
2. **后端开发**: 在 `server/` 目录下开发Node.js服务
3. **测试**: 在各自的 `tests/` 目录下编写测试
4. **文档**: 在 `docs/` 目录下维护文档

## 下一步

1. 初始化项目结构（运行 `scripts/setup.sh`）
2. 安装依赖（`npm install`）
3. 配置环境变量（复制 `.env.example` 到 `.env`）
4. 开始开发！

---

**文档版本**：v1.0  
**最后更新**：2025年  
**维护者**：ZhengWG  
**GitHub**：https://github.com/ZhengWG


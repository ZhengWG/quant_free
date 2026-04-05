## [Proposal | 提案] Workflow-Native Decision Layer (MVP) / 工作流原生决策层（MVP）

---

## 中文版

### 背景
QuantFree 已经打通了行情、AI 分析、选股、回测和交易执行。  
当前缺口是：从 idea 到 outcome 的全链路可追踪性仍不足。

目前我们仍难以清晰回答：
- 哪些 AI 推荐最终变成了真实交易？
- 哪些筛选标的实际跑赢了基准？
- 信号质量在哪个环节衰减（推荐 / 审批 / 执行 / 结果）？

### 问题定义
缺少统一的工作流决策层，会导致 QuantFree 虽然是一个强工具箱，但缺乏可量化反馈闭环，难以持续优化策略质量。

### 提案
构建一个 MVP 级别的 **workflow-native decision layer（工作流原生决策层）**，包括：
1. 统一事件模型：`idea -> recommendation -> approval -> execution -> outcome`
2. recommendation 到 trade 的链路追踪
3. 核心转化与质量指标
4. 通过 feature flag 灰度发布，避免影响现有流程

### MVP 范围
#### 包含（In scope）
- recommendation -> trade 的关联追踪（`recommendation_id` 可映射一个或多个 `order_id`）
- 转化指标：
  - Recommendation -> Approval (R->A)
  - Approval -> Execution (A->E)
  - Recommendation -> Execution (R->E)
- 质量指标：
  - Hit Rate（如 T+1 / T+5 观察窗）
  - Excess Return（相对基准超额收益）
- 最小查询与展示能力（API + 基础面板/日志输出）

#### 不包含（Out of scope）
- 复杂组合级归因
- 多账户风险归因
- 自动模型再训练闭环

### 事件模型（MVP）
必需追踪键：
- `trace_id`
- `idea_id`
- `recommendation_id`
- `approval_id`
- `order_id`

事件示例：
- `decision.idea.created`
- `decision.recommendation.generated`
- `decision.approval.accepted|rejected|expired`
- `trade.order.submitted|filled|cancelled|rejected`
- `decision.outcome.evaluated`

公共必填字段：
- `timestamp`
- `actor`
- `source`
- `symbol`

### 指标定义
1. **R->A Conversion** = `accepted_recommendations / total_recommendations`
2. **A->E Conversion** = `executed_approvals / accepted_approvals`
3. **R->E Conversion** = `recommendations_with_any_fill / total_recommendations`
4. **Hit Rate** = 在指定观察窗内，推荐方向与收益方向一致的比例
5. **Excess Return** = `strategy_return - benchmark_return`

### Feature Flag
- `quantfree.decisionLayer.enabled`（默认：`false`）
- 灰度路径：开发环境可选开启 -> 社区用户可选开启 -> 指标与数据质量稳定后逐步扩大
- 回滚方式：关闭 flag 后停止新增事件写入，不影响现有交易流程

### 建议实施步骤
1. 对齐事件 schema 与指标口径
2. 增加事件存储与 trace 查询接口
3. 增加指标聚合任务/服务
4. 在 recommendation/approval/order 关键路径接入事件追踪
5. 提供最小化 decision insights 展示并基于真实数据迭代

### 验收标准
- 至少可查询一条完整 recommendation -> order(s) 链路
- R->A、A->E、R->E 指标可查询
- 至少一个观察窗（如 T+5）可提供 Hit Rate 和 Excess Return
- flag 关闭时，现有功能与性能无明显回归

### 待讨论问题
1. approval 是否必须显式存在，还是允许部分流程自动 accepted？
2. benchmark 默认选择应为何（指数 / 行业 / 无基准）？
3. outcome 观察窗是否按策略类型配置（T+1/T+5/T+20）？
4. 是否需要隐私分级（仅摘要 vs 本地完整明细）？

### 参考
- RFC 文档：`docs/RFC_WORKFLOW_DECISION_LAYER.md`

---

## English Version

### Background
QuantFree already integrates market data, AI analysis, screening, backtesting, and execution.  
The current gap is end-to-end traceability from idea to outcome.

Today we still cannot clearly answer:
- Which AI recommendations became real trades?
- Which screened symbols actually outperformed?
- Where signal quality decayed (recommendation / approval / execution / outcome)?

### Problem Statement
Without a unified workflow decision layer, QuantFree is a strong toolbox but lacks measurable feedback loops for continuous strategy improvement.

### Proposal
Build an MVP **workflow-native decision layer** with:
1. Unified event model for `idea -> recommendation -> approval -> execution -> outcome`
2. Recommendation-to-trade traceability
3. Core conversion and quality metrics
4. Feature-flagged rollout to avoid risk to existing flows

### MVP Scope
#### In scope
- Recommendation -> Trade trace linking (`recommendation_id` to one or many `order_id`)
- Conversion metrics:
  - Recommendation -> Approval (R->A)
  - Approval -> Execution (A->E)
  - Recommendation -> Execution (R->E)
- Quality metrics:
  - Hit Rate (e.g. T+1 / T+5 window)
  - Excess Return vs benchmark
- Minimal query/display path (API + basic panel/log output)

#### Out of scope
- Complex portfolio-level attribution
- Multi-account risk attribution
- Automatic model retraining loop

### Event Model (MVP)
Required trace keys:
- `trace_id`
- `idea_id`
- `recommendation_id`
- `approval_id`
- `order_id`

Event examples:
- `decision.idea.created`
- `decision.recommendation.generated`
- `decision.approval.accepted|rejected|expired`
- `trade.order.submitted|filled|cancelled|rejected`
- `decision.outcome.evaluated`

Common required fields:
- `timestamp`
- `actor`
- `source`
- `symbol`

### Metrics Definition
1. **R->A Conversion** = `accepted_recommendations / total_recommendations`
2. **A->E Conversion** = `executed_approvals / accepted_approvals`
3. **R->E Conversion** = `recommendations_with_any_fill / total_recommendations`
4. **Hit Rate** = recommendation direction matches return direction in a defined horizon
5. **Excess Return** = `strategy_return - benchmark_return`

### Feature Flag
- `quantfree.decisionLayer.enabled` (default: `false`)
- Rollout: dev opt-in -> community opt-in -> broader enablement after metric/data quality validation
- Rollback: disabling the flag stops new event writes without impacting existing trading flow

### Suggested Implementation Steps
1. Finalize event schema and metric semantics
2. Add event store + trace query endpoints
3. Add metric aggregation job/service
4. Inject event tracking at recommendation/approval/order critical points
5. Add minimal decision insights view and iterate with real usage data

### Acceptance Criteria
- At least one full recommendation-to-order(s) trace can be queried
- R->A, A->E, R->E metrics are queryable
- Hit Rate and Excess Return available for at least one observation window (e.g. T+5)
- With flag off, no functional or performance regression on existing behavior

### Open Questions
1. Should approval always be explicit, or can it be auto-accepted in some flows?
2. What should be the default benchmark (index / sector / none)?
3. Should outcome horizon be configurable by strategy type (T+1/T+5/T+20)?
4. Do we need privacy levels (summary-only vs full local detail)?

### Reference
- RFC doc: `docs/RFC_WORKFLOW_DECISION_LAYER.md`

# RFC: Workflow-Native Decision Layer（工作流原生决策层）

- **Status**: Draft
- **Owner**: QuantFree Core Team
- **Reviewers**: Community Contributors
- **Created**: 2026-04-05
- **Related**: `docs/PRD.md`, `docs/ARCHITECTURE.md`

---

## 1. 背景与动机

QuantFree 当前已经具备行情监控、AI 分析、K 线可视化、模拟交易、选股与交易执行能力，但在“从想法到结果”的闭环追踪上仍不完整。

当前痛点：

1. 无法系统回答“哪些 AI 推荐最终变成了交易”；
2. 无法量化“筛出的标的是否真的跑赢”；
3. 无法定位信号质量在推荐、审批、执行、持有哪个环节衰减。

本 RFC 提出一个 **Workflow-Native Decision Layer**，将 QuantFree 从“工具集合”升级为“可度量、可迭代的交易协作副驾（copilot）”。

---

## 2. 目标与非目标

### 2.1 目标（Goals）

1. 定义统一事件模型，覆盖 `idea -> recommendation -> approval -> execution -> outcome` 全链路；
2. 定义首批核心指标，优先支持转化率和质量评估；
3. 提供可灰度发布的 MVP（feature flag 控制）；
4. 在不破坏现有交易路径的前提下最小侵入接入。

### 2.2 非目标（Non-Goals）

1. 本 RFC 不引入全新的策略生成模型；
2. 本 RFC 不改造券商适配器交易语义；
3. 本 RFC 不承诺在第一阶段提供完整归因（如复杂多因子 attribution）；
4. 本 RFC 不改变用户已有下单流程。

---

## 3. 核心概念与实体

### 3.1 概念定义

- **Idea（想法）**：用户发起的研究意图（手工输入或从 watchlist/筛选触发）。
- **Recommendation（推荐）**：AI 或规则引擎输出的动作建议（BUY/SELL/HOLD）。
- **Approval（审批）**：用户或策略规则对 recommendation 的确认、拒绝或过期处理。
- **Execution（执行）**：进入订单生命周期后的动作（下单、部分成交、成交、撤单、拒单）。
- **Outcome（结果）**：在观察窗内对 recommendation/execution 的绩效评估结果。

### 3.2 追踪主键

为保证跨模块可追踪，定义如下 ID：

- `trace_id`: 一次完整决策流主键（从 idea 开始）
- `idea_id`: 想法节点 ID
- `recommendation_id`: 推荐节点 ID
- `approval_id`: 审批节点 ID
- `order_id`: 券商/系统订单 ID（已有）
- `position_snapshot_id`: 结果评估快照 ID

要求：

1. 同一 `trace_id` 下可以存在多个 `recommendation_id`（多轮建议）；
2. 一个 `recommendation_id` 可以映射多个 `order_id`（分批执行）；
3. 所有事件必须带 `timestamp`, `actor`, `source`, `symbol`。

---

## 4. 事件模型（Event Model）

事件采用 append-only 设计，支持重建状态和离线分析。

### 4.1 事件命名规范

`<domain>.<entity>.<action>`

示例：

- `decision.idea.created`
- `decision.recommendation.generated`
- `decision.approval.accepted`
- `trade.order.submitted`
- `trade.order.filled`
- `decision.outcome.evaluated`

### 4.2 统一事件结构（建议）

```json
{
  "event_id": "evt_01H...",
  "event_name": "decision.recommendation.generated",
  "trace_id": "trc_01H...",
  "entity_id": "rec_01H...",
  "entity_type": "recommendation",
  "symbol": "600519.SH",
  "market": "CN-A",
  "timestamp": "2026-04-05T13:00:00.000Z",
  "actor": {
    "type": "system|user|agent",
    "id": "user_123"
  },
  "source": {
    "module": "StrategyService",
    "model": "gpt-4.x",
    "version": "1.0.0"
  },
  "payload": {},
  "metadata": {
    "workspace_id": "local",
    "feature_flags": ["decision_layer_v1"]
  }
}
```

### 4.3 MVP 事件清单

| 阶段 | 事件 | 必填字段 |
|---|---|---|
| Idea | `decision.idea.created` | `trace_id, idea_id, symbol, trigger_type` |
| Recommendation | `decision.recommendation.generated` | `recommendation_id, action, confidence, rationale` |
| Approval | `decision.approval.accepted/rejected/expired` | `approval_id, recommendation_id, reason` |
| Execution | `trade.order.submitted/filled/cancelled/rejected` | `order_id, recommendation_id, qty, price, status` |
| Outcome | `decision.outcome.evaluated` | `recommendation_id, horizon, return_pct, benchmark_return_pct` |

---

## 5. 关键指标定义（Metrics）

本 RFC 聚焦两类指标：**转化类** 与 **质量类**。

### 5.1 转化类指标

1. **Recommendation-to-Approval Conversion**
   - 定义：`accepted_recommendations / total_recommendations`
2. **Approval-to-Execution Conversion**
   - 定义：`executed_approvals / accepted_approvals`
3. **Recommendation-to-Execution End-to-End Conversion**
   - 定义：`recommendations_with_any_fill / total_recommendations`

### 5.2 质量类指标

1. **Hit Rate（命中率）**
   - 定义：在观察窗（如 T+1/T+5）内，推荐方向与实际收益方向一致的比例。
2. **Excess Return（超额收益）**
   - 定义：`strategy_return - benchmark_return`
3. **Signal Decay（信号衰减）**
   - 定义：按阶段比较预期收益与实际收益差值（生成 -> 审批 -> 执行 -> 结果）。
4. **Slippage Impact（滑点影响）**
   - 定义：`(executed_price - reference_price) / reference_price`（按买卖方向归一化）。

### 5.3 指标分组维度

- `symbol / market`
- `strategy_type`
- `model_provider / model_name`
- `user_profile`（若可用）
- `time_bucket`（日/周/月）

---

## 6. MVP 范围（第一切片）

### 6.1 In Scope

1. recommendation -> trade trace 打通；
2. 转化率（R->A, A->E, R->E）；
3. 基础质量指标（Hit Rate, Excess Return）；
4. 简单查询接口与最小 UI 展示（先可在日志/面板输出）。

### 6.2 Out of Scope

1. 复杂组合级归因；
2. 多账户统一风险归因；
3. 自动策略再训练闭环。

---

## 7. 架构与数据落地建议

### 7.1 服务侧

在 `server` 中新增（或扩展）：

1. `DecisionTraceService`: 负责 ID 生成、事件写入、trace 聚合；
2. `MetricsService`: 基于事件流计算聚合指标；
3. `DecisionRoutes`: 提供 trace 与 metrics 查询接口。

### 7.2 存储侧（SQLite，MVP）

建议新增表：

1. `decision_events`
   - `event_id (PK)`, `trace_id`, `event_name`, `entity_id`, `symbol`, `timestamp`, `payload_json`
2. `decision_metrics_daily`
   - `metric_date`, `metric_name`, `group_key`, `metric_value`

索引建议：

- `idx_decision_events_trace_time(trace_id, timestamp)`
- `idx_decision_events_symbol_time(symbol, timestamp)`
- `idx_decision_events_name_time(event_name, timestamp)`

### 7.3 插件侧（VSCode Extension）

1. 保持现有命令与 UI 路径不变；
2. 在关键动作（生成建议、用户确认、下单）注入事件上报；
3. 对外展示可先采用 “Decision Insights（实验）” 面板或命令输出。

---

## 8. Feature Flag 与发布策略

### 8.1 Flag 定义

- `quantfree.decisionLayer.enabled`（默认 `false`）

### 8.2 灰度策略

1. 开发环境默认可开；
2. 社区用户通过配置显式开启；
3. 线上默认关闭，直到指标稳定与数据完整性达标。

### 8.3 回滚策略

关闭 feature flag 后：

1. 停止写入 decision 事件；
2. 不影响现有策略推荐与交易执行；
3. 历史事件保留用于后续分析，不做删除。

---

## 9. API 草案（MVP）

1. `GET /decision/traces/:traceId`
   - 返回某条 trace 的完整事件序列与状态摘要。
2. `GET /decision/recommendations/:recommendationId`
   - 返回 recommendation 与关联审批、订单、结果。
3. `GET /decision/metrics?from=...&to=...&groupBy=symbol`
   - 返回转化与质量指标聚合结果。

---

## 10. 风险与应对

1. **事件丢失/重复**
   - 方案：事件写入幂等键（`event_id`）+ 重试去重。
2. **模块耦合上升**
   - 方案：通过统一事件 SDK/接口隔离，不在业务模块中嵌入复杂聚合逻辑。
3. **指标解释偏差**
   - 方案：在文档中明确观察窗、基准、成交口径，避免误读。
4. **性能影响**
   - 方案：事件写入轻量化；聚合任务异步化（可批处理）。

---

## 11. 验收标准（MVP）

1. 至少支持 1 条 recommendation 到 1+ order 的完整链路追踪；
2. 可查询并展示 R->A、A->E、R->E 三个转化指标；
3. 可输出至少一个观察窗（例如 T+5）的 Hit Rate 与 Excess Return；
4. 在关闭 flag 时，原有功能行为与性能无明显回归。

---

## 12. 实施步骤（建议）

1. **Step 1: RFC/Issue 定稿**
   - 对齐事件字段、口径与 MVP 边界。
2. **Step 2: 服务端事件骨架**
   - 建表、写入接口、trace 查询。
3. **Step 3: 指标计算**
   - 先离线聚合，再逐步实时化。
4. **Step 4: 插件接入 + Feature Flag**
   - 在关键节点埋点并提供最小可视化。
5. **Step 5: 评估与迭代**
   - 根据真实使用数据扩展指标和归因能力。

---

## 13. Open Questions

1. `approval` 是否必须显式步骤，还是允许“自动视作 accepted”？
2. benchmark 默认选择（指数 / 行业 / 无基准）如何配置？
3. outcome 观察窗是否支持按策略类型自定义（T+1/T+5/T+20）？
4. 是否需要多级隐私脱敏（本地仅保存摘要，明细可选）？

---

## 14. 结论

该 RFC 以最小可落地路径，将 QuantFree 从“功能完整”推进到“流程可观测 + 质量可评估”。  
建议先按 MVP 实现 recommendation-to-trade trace 与核心指标，再逐步扩展到更深层的归因和自动优化闭环。


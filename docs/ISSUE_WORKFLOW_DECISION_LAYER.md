## [Proposal] Workflow-Native Decision Layer (MVP)

### Background
QuantFree already connects market data, AI analysis, screening, backtesting, and execution.  
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
- Rollback: disable flag stops new event writes without impacting existing trading flow

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

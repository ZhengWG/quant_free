# 多市场数据源 + 策略扩展 · 实施方案

> 目标：① 打通美股数据（免费源，与 A股/港股 同一套）；② 扩展策略池 + 智能推荐引擎 + 多市场适配。
> 现状基线（实测）：A股 全通；港股 realtime+kline 已通；美股 realtime/kline 均返回空。

---

## Part A — 美股数据打通（免费源：新浪 + 腾讯）

### A0. 根因（已定位到函数）
| 能力 | 现状 | 根因 |
|------|------|------|
| 实时 | 空 | `_get_realtime_from_sina`（sina_adapter:209）只分 `hq_str_hk` / A股两支，美股 `gb_` 行落进 `_parse_ashare_line`（要求 ≥32 段）→ 返回 None |
| K线 | 空 | `get_kline_data`（:381）用 `_normalize_code` 得 `gb_aapl`，但腾讯 K线要 `usAAPL.OQ` 格式 → 符号不认 |
| 基本面 | 不支持 | `_code_to_eastmoney_secid_ext`（:429）仅 A/港，美股需 `105.AAPL`(NASDAQ)/`106.AAPL`(NYSE) |

实测两个免费源均有数据：
- 新浪实时：`https://hq.sinajs.cn/list=gb_aapl` → `var hq_str_gb_aapl="AAPL,315.32,-0.28,...";`（GBK 编码）
- 腾讯K线：`.../fqkline/get?param=usAAPL.OQ,day,,,30,qfq` → 正常返回

### A1. 统一代码规范（新增 `_market_of` 辅助）
在 `SinaAdapter` 增加市场判定，作为所有分支的单一入口：
- A股：6位数字（`6/9→sh`，其余→sz）或 `sh/sz` 前缀
- 港股：`hk`/`HK` 前缀 或 5位数字
- 美股：`us` 前缀（推荐显式写法 `usAAPL`）、`gb_` 前缀、或纯字母
- 返回 `("A股"|"港股"|"美股", 归一化代码)`，消除现有靠 `isalpha()` 的隐式判断歧义

### A2. 美股实时 `_parse_us_line`（新增）
- 在 `_get_realtime_from_sina` 分支加 `elif "hq_str_gb_" in line: self._parse_us_line(line)`
- 新浪 `gb_` 字段序（**需按实测样本逐段核对**，初版映射）：
  `[0]名称 [1]现价 [2]涨跌幅% [3]时间 [4]涨跌额 [5]开 [6]高 [7]低 ... [10]成交量 ... 昨收`
- 名称 GBK 已由 `response.encoding="gbk"` 处理（:200）
- 输出结构与 A股/港股 一致（`market="美股"`）

### A3. 美股K线（腾讯 `us` 符号 + 交易所后缀解析）
难点：美股腾讯符号带交易所后缀（NASDAQ=`.OQ`，NYSE=`.N`），不能只靠代码推断。
- 新增 `_tencent_symbol(code, market)`：A/港沿用 `_normalize_code`；美股先查缓存的后缀映射，否则**依次尝试 `.OQ`/`.N`** 取第一个非空结果，成功后写入进程内缓存 `{AAPL: usAAPL.OQ}`
- `get_kline_data` 改用 `_tencent_symbol` 而非 `_normalize_code`
- 复权：美股用 `qfq` 同样可用

### A4. 美股基本面（可选，本轮低优先）
- `_code_to_eastmoney_secid_ext` 增美股分支（`105.`/`106.`），东方财富美股基本面字段有限
- 若字段缺失，推荐引擎里美股自动降级为"仅技术面评分"（见 B2）

### A5. 影响面 / 回归
- 仅改 `sina_adapter.py`（新增方法 + 3 处分支），`market_data_service` / 路由不动
- 港股/A股 路径不受影响（分支互斥）
- 验收：`realtime?codes=usAAPL,usTSLA` 有数据；`kline/usAAPL` 有数据；`hk00700`、`600519` 回归正常

---

## Part B — 策略扩展

### B1. 更多技术策略（插件式，改动集中）
架构已是干净的 dispatch 表（`backtest_service._generate_signals:250`）+ 常量表（`strategy_constants.BACKTEST_STRATEGIES`）。新增一个策略 = 写 `_sig_xxx` + 注册 dispatch + 加常量行。

拟新增（按性价比排序）：
| 策略 | 类型 | 说明 |
|------|------|------|
| `supertrend` | 趋势 | ATR 通道翻转，趋势市表现好、噪音低 |
| `donchian` | 突破 | N日高低通道突破（海龟经典），与现有 `breakout` 互补 |
| `cci` | 摆动 | CCI 超买超卖，适合震荡市 |
| `williams_r` | 摆动 | Williams %R，与 KDJ/RSI 形成摆动族 |
| `stoch_rsi` | 摆动 | RSI 的随机化，信号更灵敏 |
| `vwap_rev` | 均值回归 | 偏离 VWAP 回归（日内/短线友好） |

- 需要的指标计算：ATR、CCI、Williams%R、StochRSI —— 与现有 `calc_adx`/`calc_obv` 放同一 indicators 模块，纯函数、可单测
- 每个策略补一条最小单测（给定构造K线→期望信号点），避免回归

### B2. 更智能的推荐引擎（在 smart_v2 之上增强）
现状：`screening_service._run_smart_v2` = 估值筛选 → AI基本面 → 多策略回测 → 复合排名（v_score/ai_score/confidence/预测收益 加权归一，:391-419）。缺市场状态感知。

增强三点：
1. **市场状态识别**（新增 `market_regime.py`）
   - 用对应指数（A股:上证 / 港股:恒指 / 美股:标普）的 MA 斜率 + ADX 判 `bull/bear/range`
   - 缓存当日结果，避免重复拉取
2. **状态自适应选/加权策略**
   - 趋势市（bull/bear）抬高趋势族权重（ma_cross/triple_ema/supertrend/adx_trend）
   - 震荡市（range）抬高均值回归/摆动族（bollinger/rsi/cci/williams_r）
   - 落地为 `_build_strategy_candidates` 的 regime 加权，而非硬过滤
3. **AI 对推荐结果做自然语言点评**
   - 复用 `strategy_service` 的 AI 通道，对 Top-N 生成"为何推荐这只+这个策略"的解释（含风险提示）
   - 美股基本面缺失时自动降级为纯技术面点评

### B3. 多市场策略适配（新增 `MarketProfile`）
不同市场交易规则不同，需参数化而非硬编码 A股规则：
| 维度 | A股 | 港股 | 美股 |
|------|-----|------|------|
| 结算 | T+1 | T+0 | T+0 |
| 涨跌停 | ±10%/20% | 无 | 无 |
| 最小交易单位 | 100股 | 每手不定 | 1股 |
| 费用 | 佣金+印花税0.05%(卖) | 印花税0.1%+交易费 | 佣金+SEC费 |

- 新增 `app/services/market_profile.py`：按市场返回 `{settlement, price_limit, lot_size, fee_fn, session_hours}`
- 接入点：
  - `trade_service` 费用计算 → 改为 `profile.fee_fn`
  - `backtest_service`/`auto_trade_service` 回测撮合 → T+1 冻结、涨跌停撮合仅对 A股生效
  - 风控默认（止损/止盈/持仓天数）可按市场给不同默认值

---

---

## Part C — 实时提醒 + 每日交易建议（本轮提醒通道：邮件优先）

### C1. 信号即时提醒（邮件）
- 现状：`auto_scheduler` 只在**止损止盈**和**EOD 汇总**推送；BUY 信号无即时提醒。短信默认关闭。
- 改法：在 `auto_trade_service` 生成 BUY/SELL 信号的**当下**，走邮件即时提醒（复用 `email_service` 的 SMTP 通道，新增 `send_signal_alert()`），不依赖短信配置。
- 频控：盘中调度 5min→1min（见 Q1）；同一信号去重，避免重复轰炸。
- 通道抽象：`send_signal_alert` 预留 channel 参数（email 先行，后续可挂桌面/短信）。

### C2. 每日交易建议邮件（全市场 smart-screen + 推荐记忆）
收盘后自动跑 `smart-screen`，把 Top-N 组织成完整梳理邮件：
- 技术面：命中策略信号 + 关键指标状态（含所属市场 A/港/美）
- 基本面：PE/PB/ROE + AI 点评（美股基本面缺失时降级为纯技术面）
- 操作建议：买入区间 / 目标价 / 止损位 / 置信度

### C3. 推荐记忆（延续性核心）★
> 目标：系统"记住"历史推荐，保证 day-to-day 延续，而非每天重新洗牌。

**新增持久化表 `recommendation_history`**（`app/models` + 迁移）：
```
id, date, market, stock_code, stock_name,
strategy, signal, entry_ref_price,     -- 推荐当时的策略/信号/参考价
target_price, stop_loss, confidence,
composite_score, ai_comment,
status,                                 -- new / holding / exit
first_recommended_date,                 -- 首次进入推荐的日期（延续性锚点）
return_since_rec_pct,                   -- 自首次推荐以来的收益
created_at
```

**每日生成逻辑（`daily_advice_service.py` 新增）**：
1. 拉昨日（及更早仍 holding）的推荐集合
2. 跑今日 smart-screen 得新候选 Top-N
3. **对账 / 延续性判定**：
   - 昨日推荐今日仍在 Top-N 且信号未反转 → `holding`，累计 `return_since_rec_pct`，保留 `first_recommended_date`
   - 昨日推荐今日跌出 或 信号反转/触及止损 → `exit`，给出退出理由
   - 今日新进 Top-N → `new`
4. 写回 `recommendation_history`，并渲染邮件三段：**延续持有 / 新增推荐 / 建议退出**
5. 延续性护栏：进出榜加**滞后阈值**（如需连续掉出2日或跌破止损才 exit），避免边界抖动导致频繁翻牌

**邮件呈现**：每只标注「首次推荐日 / 已持 N 天 / 推荐以来 +X%」，让延续性一眼可见。

---

## 推进顺序（重排后）
1. **Phase 1｜美股数据打通**（A1–A3）：realtime + kline 跑通，最小改动、独立可验收 —— 完成即可实际用美股行情
2. **Phase 2｜每日交易建议 + 推荐记忆**（C2+C3）：`recommendation_history` 表 + `daily_advice_service` + 每日建议邮件（先复用现有 smart-screen，即使策略池未扩充也能出建议）
3. **Phase 3｜信号即时提醒**（C1）：BUY/SELL 即时邮件 + 盘中调度提频 + 去重
4. **Phase 4｜策略池扩展**（B1）：加 4–6 个策略 + 指标helper + 单测（喂给推荐引擎，提升建议质量）
5. **Phase 5｜智能推荐引擎**（B2）：市场状态识别 + 自适应加权 + AI 点评强化
6. **Phase 6｜多市场适配**（B3）：MarketProfile 抽象 + 费用/撮合接入
7. 可选：A4 美股基本面、WebSocket 秒级推送

> 说明：应用户优先级，**每日建议+推荐记忆（Phase 2）前移**到数据打通之后，先让"每天一封带延续性的交易建议邮件"跑起来；策略/引擎增强（Phase 4–5）持续提升建议质量。每个 Phase 独立可验收。

---
doc_type: decision
status: active
created_at: 2026-09-18
slug: dispatch-rule-working-hour-slack-and-priority-weight
tags: [scheduler, sgs, dispatch-rule, calendar, priority, python38]
---

# 派工规则的工作小时余量与优先级权重

用户在 2026-09-18 的最优算法只读审计后明确要求“全修，按你的意见来办”，并保留“不跑全门禁”。审计确认两处派工语义缺口：slack / CR / ATC 的交期余量按墙钟小时计算（`due_exclusive − 预计完工`），而加工时长按工作小时计算，周末与夜间会把余量放大、把 ATC 的指数项压平；slack / CR 的主键完全不看优先级，`pr_rank` 只在换型代价之后做平手裁决，紧急批次会排在余量略小的普通批次之后。本决定只改派工键的输入口径与权重，不改键元组形状、图键、`due_exclusive`、batch_order 模式与 ATC 的 k 梯子。

1. 日历层新增 `CalendarEngine.working_hours_between(start, end, priority, operator_id)`：返回带符号的允许工作小时（终点早于起点为负），口径与 `add_working_hours` 相同——按日策略取工作窗口，优先级不允许或班次为零的日子不计入，跨午夜班次归属开班日，人员覆盖日历按人员解析。实现是按（人员，优先级类）缓存的前缀和，随策略缓存一并清空；跨度超过 36500 天或参数不是 datetime 时抛 `ValidationError`，不静默截断。`CalendarService` 委托同名方法，`ExecutionResourceCalendar` 靠现有转发暴露，proof 的连续日历返回墙钟小时。该方法列入 `NATIVE_TIMING_METHODS`，子类覆盖会破坏原生时序证书；解码内经 `MemoizedTimingCalendar` 按 (start, end, priority, operator) 备忘。
2. 评分层由 `sgs_due_span.due_span_inputs` 统一折算：`slack_hours = W(预计完工 → 交期截止)`，`time_left_hours = W(预计开工 → 交期截止)`，优先级取批次优先级，人员取候选机人组合的人员；内部候选、外协候选、窗口受阻候选走同一口径。工作小时只在排产视野内计：视野是本次排产的排他截止时刻 `end_dt_exclusive`，没有截止日期时取预计开工后 366 天（`sgs_due_span.FAR_DUE_LOOKAHEAD`）；视野之外（无交期的 `datetime.max` 哨兵、2099-12-31 一类远交期）按墙钟延续，只表达“非常远”，日历不会逐日游走到远交期，超过百年的交期也不再在评分里抛错（2026-09-18 盲审后补）。没有 `working_hours_between` 的日历对象按协议视为连续日历（测试替身与连续基准日历），保留墙钟跨度，不计数、不记回退；生产日历类型全部暴露该方法由合同测试锁住。
3. 合同层 `DispatchInputs` 新增 `slack_hours` / `time_left_hours`，两项必须同时给或同时缺；缺省时按 `due_exclusive` 的墙钟跨度计算，供纯合同调用与连续日历使用；非有限数、布尔或字符串一律 `ValueError`。ATC 指数项用工作小时余量 `exp(−max(slack_w, 0) / (k · avg_p))`，CR 用 `time_left_w / p`，SLACK 用 `slack_w`；显式传入墙钟跨度时三条规则与全部 k 梯子的键值与历史逐位相同。
4. slack / CR 的主键按优先级权重做保序缩放：余量 ≥ 0 时除以权重，余量 < 0 时乘以权重，越重的批次在“还有余量”和“已经迟到”两个方向都显得更紧。普通优先级权重为 1，键值不变；同一优先级内部顺序不变；ATC 自带 `w / p` 权重，不再叠加；`pr_rank` 平手键保留。
5. 边界：不改 `build_dispatch_key` 返回元组的长度与位置，不改图键、`batch_order` 模式、候选去重键与 ATC k 梯子；不引入运行库依赖，产品仍面向 Win7 x64 / Python 3.8 / 单机离线。

验收数据（单机、`.venv` Python 3.8.10，工作树 `fix/dispatch-semantics`）：

- 新增合同测试：`tests/calendar_maintenance/test_calendar_working_hours_between.py`（周末间隔只计工作班次、带符号、300 组随机跨度与逐日裁剪基线相等、夜班归属开班日、前缀随策略缓存清空、跨度上限、备忘命中、生产日历类型暴露方法）；`tests/resource_dispatch/test_dispatch_rules_working_hour_priority_contract.py`（显式墙钟跨度逐位复现历史键、跨周末翻转、优先级缩放与保序、ATC 不变、两项同给、非法值拒绝）；`tests/algorithm/test_sgs_working_hour_slack_dispatch.py`（周五开工 A 6h 交期周一、周一开工 B 4h 交期周二：工作小时口径先派 A，连续口径先派 B）。
- 单次 SGS 解码迷你矩阵（FIFO 顺序，五个端到端场景 × slack / cr / atc，逐项开关归因）：24 小时日历与全普通优先级的场景全部不变；`shift_pool`（8 小时日历，含 critical / urgent）上 atc 由工作小时余量改善——加权拖期 3216 → 2740、拖期 1714.5 → 1444.5、工期 290 → 270.5、换型 2 → 0；slack 由优先级权重改善加权拖期 3136.5 → 2972.5、工期 288.5 → 268，普通拖期 1489.5 → 1544 变差；cr 两项叠加后加权拖期 3040.5 → 3156.5、拖期 1482.5 → 1608、工期 266 → 296 变差。三条规则同属优化器规则池，逐目标择优；`shift_pool` 的 slack 黄金指纹随之更新并注明归因。
- SMTWT 局搜基准（连续日历、同优先级）改前改后逐行相同：sgs 250 实例改进 211 个、gap 16.16 → 4.13；batch_order 改进 161 个、gap 15.40 → 10.78。
- 质量矩阵（`benchmark_optimizer_quality_matrix.py`，8 例）：最终 improved 结果 7 例持平、`medium_shift_pool/min_changeover` 换型 11 → 8 改善，无一例最终结果变差；单次 baseline 解码 `tiny` 四个目标全部改善（迟到批次 4 → 3），`medium_shift_pool` 三个目标的 baseline 变差（拖期 1031 → 1044、换型 25 → 23），`min_changeover` 的 baseline 改善。
- 端到端矩阵（`benchmark_optimizer_end_to_end.py`，20 例）：最终 selected 结果 19 例持平，`shift_pool/min_tardiness` 变差（拖期 1419.5 → 1444.5，+1.8%）——该例的三个图档候选改前改后分数逐位相同（1495.5 / 1506.0 / 1495.5），两次都选中外层 baseline 候选（1 秒预算的基线优化跑），变差完全来自这一候选；逐项开关归因显示只关闭优先级权重仍是 1444.5，只关闭工作小时口径即回到 1419.5，即由第 1–3 条（工作小时余量）造成：在这套 8 小时日历夹具上 cr 规则按工作小时算余量后变差、atc 明显改善，规则池择优后 min_tardiness 的最好单解仍比原来差 25 小时。baseline 改善的有 `shift_pool/min_overdue`（迟到批次 12 → 11）、`shift_pool/min_weighted_tardiness`（2267.5 → 2237.5）、`shift_pool/min_changeover`、`frozen_ready_external/min_overdue` 与 `min_weighted_tardiness`（加权拖期 394 → 366）；其余持平。
- 集成后复核（2026-09-18，HEAD+本决定文件的覆盖树）：tiny/min_changeover 的三份剖面精英与 HEAD 逐位相同，但在工作小时口径下修补邻域对它们的决策解码后不再严格改进（HEAD 修补第一轮 2 次改进），终值 `[0, 2, 2, 15.5, 35.5, 26]` 改由迭代贪心达到、与 HEAD 相同；`tests/algorithm/test_graph_repair_multiround.py` 的 tiny 合同据此改为锁"修补跑过有界轮次且图阶段优于剖面精英"。
- 以上对照都是单机诊断对照，不是干净工作区门禁证明；未跑全量门禁。

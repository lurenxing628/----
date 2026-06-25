---
doc_type: audit-verification-recheck
audit: 2026-06-24-core-algorithm-deep-review
verifies: verification-reconciliation.md
status: completed
created: 2026-06-25
method: one-subagent-per-correction-item + main-thread-reconciliation
---

# verification-reconciliation 二次核实报告

## 大白话总裁定

- 这轮不是重新扫全仓，而是专门核 `verification-reconciliation.md` 里指出“原报告要改口”的 8 个订正点。
- 8 个点分别派了 8 个 sub agent，每个 sub agent 只查一个问题，并要求从入口一路下钻到最后落点。
- 总体结论：`verification-reconciliation.md` 大方向成立。原报告不是整份被推翻，而是有几处说重了、说宽了、或者函数归属写得不够准。
- 真正还应保留为 P1 的，是 F-04。其余几个降级点大多是：代码机制确实存在，但后面有校验挡住、当前生产入口不可达，或者已经有测试/产品合同把行为锁住了。
- F-10 需要比 `verification-reconciliation.md` 再说细一点：OR-Tools 失败不是“缺结构化根因”的主问题，它已经有 `ortools_warmstart_failed` 事件；真正缺结构化根因的是未知 batch_order / SGS 派工异常这类 catch-all 路径。

## Sub Agent 分工

| 条目 | sub agent | 核实目标 |
|---|---|---|
| F-01 | `019efa78-dd93-7f41-ac88-4979d00fc87c` | partial 写正式版本、跳甘特图、是否假成功、测试是否真冲突 |
| F-03 | `019efa78-f962-76b2-86a8-8f069c5eade0` | 坏工时 fallback 0.0 后是否会写入零时长 Schedule |
| F-04 | `019efa79-125e-7d90-aba2-3ffb9eba91f1` | 候选对比是否强制 greedy、是否绕过 improve、触发开关到底是什么 |
| F-05 | `019efa79-2c4d-7c81-937a-8d04c555228f` | balanced 是否完全不看目标，还是只在覆盖判定时不看目标主维 |
| F-06 | `019efa79-45a4-70b0-a542-698f0af413ba` | 摘要计数字符串风险当前是否可达，还是未来防御债 |
| F-08 | `019efa79-5e0b-7501-9595-0d85c754a6bc` | `simulate=True` 服务层和底层语义是否相反，生产是否会触发底层模拟写库 |
| F-10 | `019efa79-794e-76b1-a441-19d562f8fd4e` | OR-Tools、batch_order、SGS 异常到底哪里缺结构化根因 |
| F-11 | `019efa79-986f-7791-b6cd-d4fa1a947d1b` | `enforce_ready` 未知字符串风险是否有真实生产入口 |

## 逐条复核结论

### F-01：部分失败写正式版本

- 二次核实结果：`verification-reconciliation.md` 成立。
- 原报告应改：保留“partial 会写正式版本并跳甘特图”，但删掉“假装成功”和“两测试口径冲突”的味道。
- 大白话：系统确实会把“部分排成、部分失败”的结果写成可打开版本，也会跳甘特图；但它不是偷偷说“全成功”，而是一路标成 partial/warning。测试也锁了这个行为。
- 关键证据：
  - `web/routes/domains/scheduler/scheduler_run.py:60`：`success` 和 `partial` 都跳甘特图。
  - `web/viewmodels/scheduler_run_view_result.py:44`：partial 的提示分类是 warning，不是 success。
  - `tests/schedule/route_view/test_scheduler_run_view_result_contract.py:693`：测试明确 partial 会跳甘特图。
  - `tests/schedule/route_view/test_scheduler_run_surfaces_resource_pool_warning.py:560`：这份测试真实断言是不闪 success、要 warning；文件头的“不跳甘特图”说明文字是陈旧注释。
- 严重度：P1 -> P2 / 产品确认项。

### F-03：坏工时 fallback 0.0

- 二次核实结果：`verification-reconciliation.md` 成立，但措辞要加边界。
- 原报告应改：坏工时进入算法属实；但在正式排产写 Schedule 这条链路里，零时长结果会被 `start_time < end_time` 拦住，不会落库。
- 大白话：坏工时现在不是一进门就被拦，而是先被当成 0 小时拿去算；算出来如果是开始时间等于结束时间，后面写库前会拦住。问题是“晚失败、报错位置不友好”，不是“已经会污染正式排程表”。
- 关键证据：
  - `core/services/scheduler/run/schedule_input_builder.py:234`：非 strict 下工时解析有 `fallback=0.0`。
  - `core/shared/field_parse.py:82`：解析失败后走兼容 fallback。
  - `core/services/scheduler/run/schedule_payload_contract.py:169`：payload 校验读取 `start_time/end_time`。
  - `core/services/scheduler/run/schedule_payload_contract.py:174`：要求 `start_time < end_time`。
  - `core/services/scheduler/run/schedule_orchestrator.py:295`：正式链路先构建 validated payload，再进入 summary/version/persist。
- 边界说明：不能写成“数据库层永远不可能写零时长”。仓库层 `bulk_create` 本身不负责这个校验；准确说法是“正式排产服务链路不会写入零时长 Schedule”。
- 严重度：P1 -> P2。

### F-04：候选对比绕开 improve

- 二次核实结果：原报告成立，P1 维持。
- 原报告应改：触发条件要写成 `graph_analysis_mode="on"`，不是暗示还有一个独立的“候选对比开关”。
- 大白话：用户选了更精细的 improve，但只要图分析参与排产开着，候选试算会被强制改成 greedy。最后系统还可能把这个 greedy 候选当正式方案保存，所以这是实打实的高优先级问题。
- 关键证据：
  - `core/services/scheduler/run/schedule_orchestrator.py:118`：候选对比的开关就是 `graph_analysis_mode == "on"`。
  - `core/services/scheduler/run/schedule_candidate_runtime_helpers.py:33`：候选 cfg 无条件 `algo_mode="greedy"`。
  - `core/services/scheduler/run/schedule_candidate_runner.py:97`：候选运行时 `VALID_ALGO_MODES=("greedy",)`。
  - `core/services/scheduler/run/schedule_optimizer_steps.py:215`：不是 improve 就不跑 OR-Tools。
  - `core/services/scheduler/run/optimizer_local_search.py:246`：不是 improve 就不跑本地搜索。
  - `core/services/scheduler/run/schedule_orchestrator.py:254`：采用 `selection.selected_plan` 作为正式 optimizer outcome。
- 严重度：维持 P1。

### F-05：balanced 偏离当前目标

- 二次核实结果：`verification-reconciliation.md` 成立。
- 原报告应改：不要写成“系统完全不看目标”。更准确是：raw_score_best 本来是按当前目标选的，问题只出在 balanced 覆盖那一步。
- 大白话：系统先按用户目标挑一个分数最好的方案，这一步没问题。但后面 balanced 可能觉得“关键链健康更好”，就把另一个方案盖上去。盖上去时只看失败数、超期数、总拖期，没有检查“用户这次最在意的指标有没有变差”。
- 关键证据：
  - `core/models/objective.py:18`：不同 objective 对应不同指标顺序。
  - `core/services/scheduler/run/schedule_candidate_selection.py:56`：`raw_score_best` 按候选 score 选。
  - `core/services/scheduler/run/schedule_candidate_selection.py:72`：balanced 下关键链候选可覆盖 raw_score_best。
  - `core/services/scheduler/run/schedule_candidate_selection.py:156`：覆盖条件只看 failed/overdue/tardiness，不看当前 objective 主维。
- 严重度：P1 -> P2。

### F-06：摘要计数裸 int

- 二次核实结果：`verification-reconciliation.md` 成立。
- 原报告应改：裸 `int()` 和测试盲区属实，但当前生产主链里坏字符串进不到 `ScheduleSummary` 三个计数字段，所以是防御债，不是现实 P1。
- 大白话：这里确实有“以后别人把上游改坏会炸”的点，但现在正常排产链路里，这几个数是算法自己算出来的整数，不是用户输入的字符串。所以它值得收口，但不该排在第一优先级。
- 关键证据：
  - `core/algorithms/greedy/scheduler.py:463`：业务代码里唯一 `ScheduleSummary(...)` 构造点。
  - `core/algorithms/greedy/scheduler.py:461`：`total_ops` 来自 `len(...) + state.seed_count`。
  - `core/algorithms/greedy/run_state.py:73`：`scheduled_count` 来自整数和 `len(results)`。
  - `core/algorithms/greedy/run_state.py:98`：失败计数用整数累加。
  - `core/services/scheduler/summary/schedule_summary_freeze.py:72`：完成态判断还在裸 `int()`。
  - `core/services/scheduler/run/schedule_persistence.py:123`、`core/services/scheduler/run/schedule_persistence.py:152`：历史和 OperationLogs 仍直接读原始 summary count。
- 测试盲区修正：现有测试用 `total_ops=True` 不够，因为 `int(True)` 不会抛错。要测字符串坏值，才真的覆盖裸 `int()` 崩溃分支。
- 严重度：P1 -> P3。

### F-08：simulate 同名不同义

- 二次核实结果：`verification-reconciliation.md` 成立。
- 原报告应改：函数归属要改准；风险口径要写成命名/边界债，不要写成当前数据安全风险。
- 大白话：服务层的 `simulate=True` 是“只试算，不写库”；底层持久化的 `simulate=True` 是“可以写模拟版本，但不改正式状态”。名字一样，意思相反，确实容易坑后人。但当前生产模拟入口不会走到底层写库，所以不是现在会污染数据。
- 关键证据：
  - `core/services/scheduler/schedule_service.py:273`：服务层把 simulate 变成 `simulation_validated_only`。
  - `core/services/scheduler/schedule_service.py:327`：simulate 时不分配版本。
  - `core/services/scheduler/schedule_service.py:329`：simulate 时 `persist_schedule_fn=None`。
  - `core/services/scheduler/run/schedule_orchestrator.py:389`：只有有 persist 回调且分配版本时才写。
  - `core/services/scheduler/run/schedule_persistence.py:249`：`287-317` 这段属于 `persist_schedule_core_in_tx`。
  - `core/services/scheduler/run/schedule_persistence.py:320`：外层 `persist_schedule` 从这里才开始。
- 严重度：维持 P2，但标明无当前数据安全风险。

### F-10：异常根因泛化

- 二次核实结果：`verification-reconciliation.md` 大方向成立，但需要再收窄。
- 原报告应改：不要把 OR-Tools 和未知派工/SGS 异常混成一类。
- 大白话：OR-Tools 失败不是完全没线索，它有 warning、有计数、有 `ortools_warmstart_failed` 这类结构化事件，日志里还带异常信息/堆栈。真正麻烦的是未知 batch_order/SGS 派工异常：用户和历史里只看到“工序 X 排产异常，请看日志”，OperationLogs 也没有更细的根因字段。
- 关键证据：
  - `core/services/scheduler/run/schedule_optimizer_steps.py:171`：OR-Tools 失败会计数。
  - `core/services/scheduler/run/schedule_optimizer_steps.py:175`：fallback logger 会带 `traceback.format_exc(limit=10)`。
  - `core/services/scheduler/summary/schedule_summary_degradation.py:286`：OR-Tools 降级事件有 `code/scope/field`。
  - `core/algorithms/greedy/dispatch/batch_order.py:149`：batch_order 普通异常 catch-all。
  - `core/algorithms/greedy/dispatch/batch_order.py:209`：只写泛化错误并打 logger。
  - `core/algorithms/greedy/dispatch/sgs.py:404`：SGS 普通异常 catch-all。
  - `core/services/scheduler/run/schedule_persistence.py:152`：OperationLogs 写的是压缩 detail，缺顶层 degradation_events/errors/public_error_details。
- 建议改写：F-10 应聚焦“未知 batch_order/SGS 执行派工异常缺结构化根因”；OR-Tools 只能作为 OperationLogs 没保留降级事件的次级问题。
- 严重度：整体维持 P2（偏 P3）。

### F-11：enforce_ready 未知字符串

- 二次核实结果：`verification-reconciliation.md` 成立。
- 原报告应改：未知字符串会被归成 no 属实；但当前没有真实生产入口这样传，Web 入口已经挡住，所以这是未来防御债。
- 大白话：如果有人绕过页面，直接写代码传 `enforce_ready="随便"`，服务层会当成 no，于是齐套检查被放宽。但页面不会这么传，页面遇到非法值会直接报错，不会继续调服务。
- 关键证据：
  - `core/services/scheduler/schedule_service.py:197`：公开签名是 `Optional[bool]`。
  - `core/services/scheduler/run/schedule_input_collector.py:128`：内部解析 `enforce_ready`。
  - `core/services/scheduler/run/schedule_input_collector.py:131`：字符串会走 `to_yes_no(... default=no)`。
  - `web/routes/domains/scheduler/scheduler_run.py:48`：正式排产 Web 入口先用 `form_optional_toggle_bool`。
  - `web/routes/domains/scheduler/scheduler_week_plan.py:445`：模拟排产 Web 入口也先用 `form_optional_toggle_bool`。
  - `web/routes/form_values.py:25`：非法表单值会抛 ValidationError。
  - `tests/schedule/route_view/test_scheduler_route_enforce_ready_tristate.py:350`：run/simulate 的 None/True/False/非法值都有测试。
- 准确风险：不是“误锁”，而是“放宽排产”，让未齐套批次绕过本该执行的阻断。
- 严重度：P2 -> P3。

## 没有单独派 sub agent 的条目

- F-02、F-07、F-09、F-12 没有进入本轮 sub agent 分派。
- 原因：本轮按 `verification-reconciliation.md` 的“报告自身建议订正项”拆分，那张表只要求修正 F-01、F-03、F-04/F-05、F-06、F-08、F-10、F-11。
- 这些未分派条目不是说不重要，而是本次没有“原报告必须改口”的同等级差异：
  - F-02 仍维持 P1。
  - F-07 仍维持 P2。
  - F-09 仍维持 P2（偏 P3）。
  - F-12 仍维持 P2。

## 最终建议

- 先改原报告文字，不急着动业务代码。
- 原报告最终严重度建议改成：
  - P1：F-02、F-04。
  - P2：F-01、F-03、F-05、F-07、F-08、F-10、F-12。
  - P3：F-06、F-09、F-11。
- F-10 如果要更严格拆分，可以把 OR-Tools 从 F-10 主问题里摘出去，保留“未知 batch_order/SGS 异常缺根因”作为主问题。
- 本轮只读核实，未修改业务代码，未运行测试；只新增本报告作为二次核实记录。

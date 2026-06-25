---
doc_type: audit-stage
audit: 2026-06-24-core-algorithm-deep-review
stage: phase-2-main-verification
status: completed
created: 2026-06-24
---

# Phase 2：主线程复核

本阶段只保留能回到源码行号的问题。子代理提出但有反证的内容，会在“降级或不报”里说明。

## F-01 P1：部分失败会生成可打开正式版本

### 证据

- `core/algorithms/greedy/dispatch/batch_order.py:145-148`：普通派工遇到某个工序失败时，记录失败并阻断批次，但不一定中断整次排产。
- `core/algorithms/greedy/dispatch/sgs.py:399-403`：SGS 也会把当前失败和后续失败计入 `failed_count`。
- `core/services/scheduler/summary/schedule_summary_freeze.py:72-79`：只要 `success=False` 且 `scheduled_ops > 0`，状态就是 `partial`。
- `core/services/scheduler/run/schedule_payload_contract.py:217-260`：`schedule_errors` 只在没有任何可落库排程行时参与 `no_actionable` 错误；如果有合法 `schedule_rows`，普通失败错误不会阻止 payload 返回。
- `core/services/scheduler/run/schedule_persistence.py:287-317`：payload 合法后会写 `Schedule` 和 `ScheduleHistory`。
- `core/services/scheduler/schedule_service.py:345-349`：非模拟运行返回 `result_persisted=True`、`can_open_result_version=True`。
- `web/routes/domains/scheduler/scheduler_run.py:60-64`：路由把 `partial` 和 `success` 一样跳到甘特图结果页。
- `tests/schedule/route_view/test_scheduler_run_view_result_contract.py:693-740`：测试明确锁定 partial 跳甘特图并给 warning。
- `tests/schedule/route_view/test_scheduler_run_surfaces_resource_pool_warning.py:1`：另一个测试文件头部仍写着 partial 不跳甘特图，和当前代码/合同测试存在口径冲突。

### 判断

- 这不是隐藏行为：系统会标成 `partial`，也会给 warning，不是“假装成功”。
- 但它确实把带失败的结果写成可打开正式版本，并自动进入甘特图。
- 如果业务口径是“部分成功可作为正式版本查看”，这是产品决策；但按本轮“失败不应继续产出正式可用结果”的审查口径，它是 P1 合同风险。

### 建议

- 明确产品合同：partial 是“可正式使用的版本”，还是“待确认的临时结果”。
- 如果不是可正式使用，应不要自动跳甘特图，至少要进入确认页。
- 如果继续允许 partial 正式版本，应在结果页、历史页、导出入口都强提示失败工序数量和失败范围。

## F-02 P1：停机约束失败后继续正式排产

### 证据

- `core/services/scheduler/resource_pool_builder.py:225-236`：停机加载前置步骤异常时，代码返回空 `downtime_map`，只追加 warning。
- `core/services/scheduler/resource_pool_builder.py:246-255`：部分设备停机加载失败时，只记录部分失败和 warning，健康设备继续，失败设备不再使用停机约束。
- `core/services/scheduler/resource_pool_builder.py:351-361`：自动安排设备的停机扩展失败时，返回旧 `downtime_map`，继续排产。
- `core/algorithms/greedy/internal_slot.py:287-313`：算法只有拿到 `machine_downtimes` 时才会推迟避让停机段。
- `core/services/scheduler/summary/schedule_summary_degradation.py:303-310`：最终摘要会写 `downtime_avoid_degraded`，说明这不是完全静默。
- `tests/schedule/summary/test_schedule_summary_v11_contract.py:172-187`：测试明确锁定“部分停机失败会继续，但不再宣称停机避让是完整硬约束”。

### 判断

- 这不是“完全看不见”的吞错；用户摘要里能看到停机避让降级。
- 但停机表是排产正确性的输入。失败设备继续排，可能把任务排到真实停机时间段里。
- 因此问题核心是：硬约束数据不可用时没有阻断正式排产。

### 建议

- 总加载失败：正式排产 fail-loud；模拟或诊断模式才允许继续。
- 部分设备失败：至少阻断受影响设备，或者把涉及这些设备的工序标成不可排，不要只降级提示。

## F-03 P1：非 strict 坏内部工时 fallback 成 0.0

### 证据

- `core/services/scheduler/schedule_service.py:204-205`：`strict_mode` 默认是 `False`。
- `core/services/scheduler/run/schedule_input_builder.py:234-253`：`setup_hours` 和 `unit_hours` 用 `fallback=0.0`。
- `core/shared/field_parse.py:82-93`：非 strict 模式下解析失败时走兼容 fallback。
- `core/algorithms/greedy/internal_slot.py:176-180`：算法只拒绝非有限数和负数，0 可以通过。
- `core/algorithms/greedy/internal_slot.py:220-226`：0 小时会算出开始等于结束的时间段。
- `core/algorithms/greedy/internal_operation.py:87-91`：估算通过后会占用资源并返回算法结果。
- `core/services/scheduler/run/schedule_payload_contract.py:169-176`：持久化前要求 `start_time < end_time`，所以不能证明零时长结果会落库成正式 `Schedule`。
- `core/services/scheduler/run/schedule_payload_contract.py:250-257`：如果零时长结果进入 payload 校验，会导致 invalid row 或 no actionable 错误。
- `tests/schedule/summary/test_schedule_summary_input_fallback_contract.py:73-82`：摘要会写 `input_fallback`，说明这也不是完全静默。

### 判断

- 这不是“无痕吞错”，因为摘要会有降级事件。
- 也不能说“零时长正式排程一定会落库”，因为持久化前有时间段校验。
- 真正问题是：坏工时先被正式排产入口降级成 0.0，进入算法层，错误被推迟到后面的排程结果校验或 partial/failure 口径里。
- 用户本来应该看到“工时坏了，不能正式排”，而不是让算法继续跑一圈。

### 建议

- 正式排产入口应拒绝坏 `setup_hours` / `unit_hours`。
- 如果要保留兼容，只应限制在导入预览、修复建议或模拟诊断流程里。

## F-04 P1：候选对比强制 greedy，绕开 improve 优化链

### 证据

- `core/services/scheduler/run/schedule_orchestrator.py:235-256`：候选对比开启后，编排层跑 `run_candidate_comparison()`，并把选中候选作为最终方案。
- `core/services/scheduler/run/schedule_candidate_runtime_helpers.py:33-42`：每个候选配置被 `replace(..., algo_mode="greedy", ...)` 强制改成 greedy。
- `core/services/scheduler/run/schedule_candidate_runner.py:97-104`：候选试算配置服务只允许 `VALID_ALGO_MODES=("greedy",)`。
- `core/services/scheduler/run/schedule_candidate_runner.py:323-344`：候选用这个配置调用 `optimize_schedule_fn()`。
- `core/services/scheduler/run/schedule_optimizer_steps.py:215-216`：OR-Tools 预热只在 `algo_mode == "improve"` 时执行。
- `core/services/scheduler/run/optimizer_local_search.py:246-247`：本地搜索也只在 `algo_mode == "improve"` 时执行。
- `core/services/scheduler/run/schedule_optimizer.py:187-214`：本地搜索是优化链的一部分，但候选 greedy 路径不会走到有效搜索。

### 判断

- 如果用户原本选择了 improve，开启候选对比后，最终采用候选不是按 improve 链算出来的。
- 这会让“候选对比”这个局部功能覆盖用户对整体优化质量的期待。

### 建议

- 候选试跑应继承原始 `algo_mode`，预算按候选拆分。
- 如果必须只用 greedy 试算，应在配置和摘要中明确写出“候选对比只跑快速贪心试算，不代表 improve 最优结果”。

## F-05 P1：默认 balanced 可能偏离当前优化目标

### 证据

- `core/services/scheduler/run/schedule_candidate_runner.py:118`：候选选择默认 `selection_policy="balanced"`。
- `core/services/scheduler/run/schedule_orchestrator.py:127-128`：编排层默认也读 `balanced`。
- `core/services/scheduler/run/schedule_candidate_selection.py:56`：先计算原始总分最佳 `raw_score_best`。
- `core/services/scheduler/run/schedule_candidate_selection.py:72-90`：`balanced` 允许 `critical_health_best` 覆盖原始总分最佳。
- `core/services/scheduler/run/schedule_candidate_selection.py:156-169`：覆盖条件只看失败数、超期数、总拖期小时，没有校验当前优化目标完整 score。
- `core/models/objective.py:18-45`：当前目标可能是 `min_changeover`、`min_weighted_tardiness` 等，并不只等于超期数和总拖期小时。
- `core/algorithms/evaluation.py:345-346`：真实 score 由目标字段决定。

### 判断

- 如果目标是“最少换型”或“最少加权拖期”，`balanced` 仍可能选择关键链健康更好的候选。
- 这不一定是代码 bug，也可能是产品策略；但默认行为和“按当前目标做整体最优”不一致。

### 建议

- 默认改为 `score_only`，或让 `balanced` 覆盖时要求当前目标 score 不差于 `raw_score_best`。
- 摘要里除 reason_code 外，还应展示“为了重点工序，牺牲了哪些主目标指标”。

## F-06 P1：摘要计数解析没有单源收口

### 证据

- `core/services/scheduler/summary/schedule_summary.py:138-139`：先算 `result_status` 和 `completion_status`。
- `core/services/scheduler/summary/schedule_summary_freeze.py:72-79`：`success=False` 时直接 `int(summary.scheduled_ops)`。
- `core/services/scheduler/summary/summary_count_parse.py:31-56`：项目已有安全解析函数 `parse_summary_count()`。
- `core/services/scheduler/summary/schedule_summary_assembly.py:316-325`：后续 `summary_counts_with_errors()` 会把坏 count 转成 `summary_count_parse_failed`。
- `tests/schedule/summary/test_schedule_summary_v11_contract.py:445-463`：现有测试覆盖 `success=True` 且 count 坏值；这不会触发 `_compute_completion_status` 的裸 `int()` 分支。
- `core/services/scheduler/run/schedule_persistence.py:123-130`：`ScheduleHistory.op_count` 仍裸 `int(summary.total_ops)`。
- `core/services/scheduler/run/schedule_persistence.py:152-163`：OperationLogs 仍裸 `int(summary.total_ops/scheduled_ops/failed_ops)`。

### 判断

- 坏计数的安全降级链路已经存在，但不是所有路径都用它。
- 在 `success=False, scheduled_ops="bad"` 时，可能先抛异常，看不到 `summary_count_parse_failed`。
- 在摘要已经降级的情况下，持久化和日志仍可能因为原始 count 抛错，或和用户可见 `counts` 不一致。

### 建议

- `_compute_completion_status()`、`ScheduleHistory`、OperationLogs 全部改用同一套 count 解析结果。
- 持久化和日志不要再读取原始 `summary.*_ops`。

## F-07 P2：图有环降级的顶层状态容易弱化告警

### 证据

- `.codestable/architecture/ARCHITECTURE.md:87`：架构文档明确允许 `on + 有环 + graph_block_on_cycle=no` 继续旧 SGS 逻辑，并写 public 摘要。
- `core/services/scheduler/run/schedule_graph_report.py:285-310`：只有 `status != available` 或 `graph_block_on_cycle == yes` 才报错。
- `core/services/scheduler/run/schedule_graph_report.py:395-405`：有环时顶层仍写 `status="available"`。
- `core/services/scheduler/run/schedule_graph_dispatch_context.py:96-103`：public 字段会写 `effective_mode="sgs_without_graph_ready_queue"` 和“继续按普通排法处理”。
- `core/services/scheduler/summary/summary_visible_degradation.py:145-155`：顶层 `status=="available"` 时不会追加图分析 warning。
- `tests/scheduler_graph/test_scheduler_graph_cycle_policy_contract.py:261-266`：测试锁定该降级摘要字段。

### 判断

- 这不违反现有架构文档，所以不能报 P1。
- 但用户选择的是“参与排产/on”，实际降级为普通 SGS。顶层 `available` 容易让页面或日志读者以为图增强完整启用。

### 建议

- 保持可降级也可以，但顶层状态建议标成 `degraded`，或增加专门 warning。

## F-08 P2：`simulate=True` 上下层含义相反

### 证据

- `core/services/scheduler/schedule_service.py:244-246`：服务入口文档说模拟不写 `Schedule`、`ScheduleHistory` 或正式状态。
- `core/services/scheduler/schedule_service.py:327-330`：服务入口模拟时不传持久化函数。
- `core/services/scheduler/schedule_service.py:345-358`：返回 `version=None`、`result_persisted=False` 和用户提示。
- `core/services/scheduler/run/schedule_persistence.py:287-295`：底层持久化无论 `simulate` 都会写 `Schedule`。
- `core/services/scheduler/run/schedule_persistence.py:296-317`：`simulate=True` 只跳过正式状态更新，但仍写 `ScheduleHistory`。
- `core/services/scheduler/run/schedule_candidate_persistence_helpers.py:85-100`：候选持久化也不看 `simulate`，会写候选表。
- `tests/algorithm/test_schedule_persistence_auto_assign_contract.py:322-341`：测试明确断言底层 `simulate=True` 会写 Schedule 和 ScheduleHistory。
- `tests/candidate/test_scheduler_candidate_persistence_contract.py:214-241`：候选持久化测试也覆盖 `simulate=True` 写候选相关表。

### 判断

- 当前 `ScheduleService.run_schedule(simulate=True)` 是安全的，不会落库。
- 风险在底层 API 命名：同一个 `simulate=True`，服务层意思是“只试算不落库”，持久化层意思是“写模拟版本但不改正式状态”。

### 建议

- 底层参数改名，例如 `persist_as_simulation_version`。
- 或把服务层和持久化层的模拟含义写进架构文档，防后续误用。

## F-09 P2：同批次后续跳过缺错误明细

### 证据

- `core/algorithms/greedy/dispatch/batch_order.py:145-148`：失败时只调用 `record_dispatch_failure(batch_id, block=True)`。
- `core/algorithms/greedy/dispatch/batch_order.py:160-162`：后续同批次命中 blocked batch 时，只 `failed_count += 1`，不追加 `state.errors`。
- `core/algorithms/greedy/run_state.py:98-101`：`record_dispatch_failure()` 只改计数和 blocked batch。
- `core/algorithms/greedy/dispatch/sgs.py:399-403`：SGS 用 `remaining_failed` 一次性累计后续失败数量。
- `core/algorithms/greedy/dispatch/sgs.py:424-426`：`_remaining_failed()` 只返回数量。
- `core/algorithms/greedy/dispatch/sgs_graph.py:337-354`：图依赖阻断会补错误明细，但同批次剩余工序没有同等明细。
- `core/algorithms/greedy/scheduler.py:461-468`：最终 success 仍由 `failed_count == 0` 判断，所以不会假成功。

### 判断

- 这不是“失败装成功”，因为 `failed_ops` 会增加。
- 问题是错误明细不完整，用户只能看到数量，看不到后续哪些工序被连带跳过。

### 建议

- 对同批次后续跳过补一条聚合错误，例如“批次 B 后续 N 道工序因前序失败跳过”。
- SGS 和 batch_order 两条路径保持一致。

## F-10 P2：异常根因被压成泛化文案

### 证据

- `core/algorithms/greedy/dispatch/batch_order.py:209-213`：普通派工捕获未知异常后，用户可见错误只写“排产异常，请查看系统日志”。
- `core/algorithms/greedy/dispatch/sgs.py:404-408`：SGS 捕获未知异常后也只写泛化错误。
- `core/services/scheduler/summary/schedule_summary_assembly.py:344-345`：摘要只消费已经泛化后的 `summary.errors`。
- `core/services/scheduler/run/schedule_persistence.py:152-166`：操作日志记录数量、状态、耗时等，不记录派工异常类型或失败阶段。
- `core/services/scheduler/run/schedule_optimizer_steps.py:171-180`：OR-Tools 失败只累加 `ortools_warmstart_failed_count` 并写 logger。
- `core/services/scheduler/summary/summary_runtime_state.py:276-283`：用户可见 warning 是通用文案。
- `core/services/scheduler/summary/schedule_summary_degradation.py:286-293`：降级事件也是通用文案。
- `tests/algorithm/test_warmstart_failure_surfaces_degradation.py:123-127`：测试锁定会出现通用 warning 和降级计数。

### 判断

- 不能报“静默吞错”，因为 warning、错误明细或降级计数存在。
- 但历史摘要和操作日志里缺少结构化根因。用户或后续审计如果没有运行日志，只能看到泛化文案。

### 建议

- 在 diagnostics、`algo_stats` 或内部操作日志字段中加入脱敏后的异常类型、失败阶段和短消息。

## F-11 P2：服务层直接调用时 `enforce_ready` 未知字符串会变 no

### 证据

- `core/services/scheduler/run/schedule_input_collector.py:128-133`：服务层如果收到字符串 `enforce_ready`，直接调用 `to_yes_no(... default=no)`。
- `core/services/scheduler/number_utils.py:9-17`：`to_yes_no()` 使用 `unknown_policy="no"`。
- `core/shared/boolean_normalize.py:58-65`：未知值最终返回 `no`。
- `core/services/scheduler/run/schedule_input_collector.py:297-298`：只有解析为真才会执行 `_ensure_ready_batches()`。
- `tests/schedule/route_view/test_scheduler_route_enforce_ready_tristate.py:377-413`：Web 表单入口对非法值有保护，会闪错且不调用服务。

### 判断

- Web 路由入口已经挡住了非法值，所以这不是页面用户的直接漏洞。
- 但服务层公开函数仍接受字符串，直接调用或未来新入口传入拼错值时，会静默关掉齐套门禁。

### 建议

- 服务层只接受 `None`、`bool` 和明确 yes/no 字符串；未知字符串直接抛 `ValidationError`。

## F-12 P2：关键测试没有全部进入 required 强保护

### 证据

- `tools/quality_gate_shared.py:700-710`：门禁会跑 full-test-debt 相关链路。
- `tools/verify_required_regressions_from_full_test_debt.py:167-198`：required 核销只认 required 列表里的路径。
- `tools/test_registry_data.py:169-170`：required 中已有 `test_scheduler_graph_auto_selection_contract.py` 和 `test_scheduler_graph_report_mode_service_contract.py`。
- 子代理搜索未在 registry 中找到若干关键合同：`test_scheduler_graph_on_mode_contract.py`、`test_sgs_scoring_fallback_unscorable.py`、`test_scheduler_candidate_runner_contract.py`、`test_scheduler_candidate_persistence_contract.py` 等。

### 判断

- full pytest 正常时仍会覆盖这些测试。
- 风险是 required 强保护没钉住它们；未来 full-test-debt、skip、xfail 或分组变化时，核心合同可能没被单独拦住。

### 建议

- 把少量代表测试加入 `QUALITY_GATE_GUARD_TESTS` 或对应 scheduler group。

## 降级或不报的线索

- “OR-Tools 失败完全静默”：不报。已有 warning、降级事件和测试。
- “图有环降级违反架构”：不报。架构明确允许 `graph_block_on_cycle=no` 继续旧 SGS。
- “资源匹配诊断影响算法选择”：不报。当前证据显示 resource matching 只进 public/diagnostics，没有参与候选选择。
- “SGS ready queue 漏排”：不报。`core/algorithms/greedy/dispatch/sgs_graph.py:271-280` 对无候选但仍有未完成工序会抛错。
- “服务入口 simulate=True 会落库”：不报。服务入口模拟分支没有传持久化函数。
- “停机和坏工时完全无提示”：不报。停机会进入 `downtime_avoid_degraded`，坏工时会进入 `input_fallback`；真正问题是提示后仍允许正式排产。
- “多个 rejected attempts 截断”暂不作为正式发现。当前只能证明 public attempts 有 12 条上限，还没有证明关键 rejected 根因在正式诊断链里必然丢失。

## 本阶段未做

- 未修改业务代码。
- 未跑全量测试；本阶段是静态源码复核。
- 未证明某个真实生产数据已经触发 F-03/F-04 的更差结果；结论是源码规则允许发生。

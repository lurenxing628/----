---
doc_type: refactor-design
refactor: 2026-09-14-scheduler-decode-speed-and-candidate-dedup
status: approved
scope: SGS 候选评分见证缓存、自动派工机人对试算备忘与再验证、评分结果交接正式放置、解码内日历纯函数备忘、忙块跳过认证税、外层候选同输入去重与预算按需分配
summary: 行为等价地砍掉 SGS 解码里的重复试算、重复日历问答和逐跳反射开销，并让工作台外层图权重档在优化器输入完全相同时复用兄弟方案，把预算留给真正需要搜索的候选。
---

# 排产解码提速与外层候选去重

来源：`.codestable/audits/2026-09-14-scheduler-algorithm-optimization-space/`（finding-01/04/05/06）。用户授权“有优化空间就去优化，压榨优化空间，按照你自己的想法来”。

## 1. SGS 见证缓存（finding-01）

- 新模块 `core/algorithms/greedy/dispatch/sgs_score_cache.py`。每一步派工只改动：被派批次的进度、被占用的一台机台和一位人员的时间线、该机台的工种邻居记录与忙时、资源需求窗口。一个候选如果读到的格子都没变，派工键必然相同。
- 不追踪写路径，而是每步从活状态重算一个 O(1) 见证：固定机人候选 = `(前道完工, 机台段列表 id/len, 人员段列表 id/len, 机台邻居数+末尾工种)`；件级作用域下前道完工用图前驱证据、不随批次进度变化，见证里记 None。
- 自动派工候选的见证覆盖合格池内全部机台/人员的同类读数加忙时；只有探针报告“两对候选在（完工时刻, 换型）上并列”时才把 `ResourceDemand.revision` 纳入，因为只有并列时 `prefer_resource_pair` 才会看需求提示。并列标记由 `_choose_best_pair` 通过 `AutoAssignAttempt.pair_tie_occurred` 报出。
- 候选类型不设白名单；改为按类判定“朴素记录类”（无 `__getattribute__`/`__getattr__` 钩子、字段无描述符），生产的 `OpForScheduleAlgo` 通过，钩子类每轮全量重评。
- 评分内部函数或自动派工内部函数被 monkeypatch 时（`_native_score_functions_unchanged` / `native_auto_assign_unchanged` 为假）不用缓存，保留“被插桩就能观察到每次调用”的测试契约。
- 2026-09-12 的证书复用仍先服务它能证明的候选；它证明不了的候选（非原生日历、共享资源、非白名单类型）回落到见证缓存，而不是像原来那样直接全量评分。

## 2. 机人对试算备忘（finding-01 自动派工部分）

- 同一缓存对象按 `(工序身份, 机台, 人员)` 记住无早停的完整试算，见证 = `(前道完工, 机台段 id/len, 人员段 id/len, 机台邻居数+末尾工种)`。
- `_pair_score` 在 SGS 轮次内改用备忘：早停语义用完整试算精确复现——避让只会把开工时刻往后推，所以原生探针在 `abort_after` 上早停当且仅当完整试算的开工时刻晚于 `abort_after`。
- 胜出对在 `_estimate_scoring_slot` 的复算也走同一备忘。

## 3. 评分结果交接正式放置（finding-04）

- `sgs_estimate_reuse.py` 新增第二个作用域 `sgs_handoff_scope`；`_run_sgs_loop` 每轮 `next_round()`，条目在当轮被证明有效才允许交接。
- `_estimate_internal` 不再只在证书复用激活时问 `selected_sgs_estimate`；`_resolve_internal_resources` 先问 `selected_sgs_resources`，命中就不重跑整套机人对搜索，但仍然自己校验工时、记计数、写占用。

## 4. 外层候选同输入去重与预算按需分配（finding-06）

- 新模块 `core/services/scheduler/run/schedule_candidate_dedup.py`。指纹 = 去掉三项图权重的候选配置 + 图 ready 上下文里除 `graph_priority_key_by_op_id`/`score_weights` 以外的全部内容 + 优先键诱导的弱序（复用 `graph_priority_preorder`）+ 派工模式覆盖。SGS 只按比较消费优先键，弱序相同即解码相同，随后的确定性搜索输入也相同。
- 运行器到第一个图候选时一次性准备所有剩余图候选（核心已共享缓存，每档投影很便宜），从而知道还有多少“真正需要搜索”的候选，`allocate_candidate_budget(remaining_candidates=...)` 按该数分片。
- 有已完成同指纹兄弟的候选直接复用其方案：`CandidatePlan.reused_from_candidate_key`（内部）与 `reused_from_label`（公开视图）如实标记，`CandidateComparisonOutcome.reused_count` 与公开汇总 `reused_candidate_count` 计数；复用候选不给预算反馈喂假信号；失败或跳过的兄弟不被复用，下一档自己搜索。
- 端到端基准支持（`tests/_support/optimizer_end_to_end_*`）把 `optimizer_call_count` 的口径改为“完成且未复用”的候选数，复用行必须 0 解码、0 优化器耗时且质量向量等于兄弟。

## 5. 解码内日历纯函数备忘（finding-02，第二阶段）

- 先测量再定方案：1000 工序自动派工一次解码里 `adjust_to_working_time` 231 万次调用只有 9,366 组不同参数（重复 99.6%），`add_working_hours` 重复 96.5%，`get_efficiency` 重复 99.3%。瓶颈不是按天循环本身，而是同一个问题被反复问；审计里"累计工时索引"的方向在测量后放弃——备忘收益更大，且不碰 `CalendarEngine` 的任何算术，零语义风险。
- 新模块 `core/algorithm_runtime/calendar_timing_memo.py`：`MemoizedTimingCalendar` 只暴露估算器用到的四个纯函数（adjust / get_efficiency / add_working_hours / certified_slot_window），按精确参数元组备忘，异常不备忘，非朴素参数（`datetime` 子类、非 `str` 优先级）直接透传，单表上限 32768 条、超限清空。
- 只对"时序方法可证明原生"的日历启用：`register_calendar_timing_guard` 按类型谱系注册守卫。`CalendarEngine` 谱系守卫允许只改 `_resolve_calendar_row` 的子类（基准用的 `MemoryCalendar`），`CalendarService` 守卫在原证书守卫上加 `certified_slot_window`；`ExecutionResourceCalendar` 覆盖层与任何类级/实例级覆写都不启用。守卫每轮 SGS 在 `begin_round` 重查。
- 接入点只有一处：`estimate_internal_slot` 开头向 handoff 换取备忘日历；没有 handoff 的路径（直接调用、件级采纳等）行为与调用轨迹不变。

## 6. 忙块跳过的认证税（finding-03）

- `busy_block_skip._certified_window` 每跳一次 `inspect.getattr_static`，1000 工序自动派工里 101 万次、约 4.3 秒（19%）。新模块 `core/algorithm_runtime/static_attribute.py` 在普通元类实例上给出与 `inspect.getattr_static` 逐项相同的结果（实例字典优先级、数据描述符、`__dict__` 遮蔽、谱系变更后失效），只按类谱系记住"实例字典可信"这一件事；类对象、自定义元类回落到 `inspect`。`resource_quality._plain_operation_type` 同步切换。
- 不改认证粒度（每跳仍认证），对运行中 monkeypatch 的检测语义不变。

## 7. 机人对试算再验证（finding-01 自动派工部分，第二阶段）

- 见证不同不等于结果不同。一次试算是被"扫描区间"内忙块决定的确定性路径：`estimate_internal_slot` 记录首个调整后的开工点与每次尝试的结束/跳转上界（`note_scan`），`occupy_resource` 把每次段插入报给 handoff（`observe_occupation`，带递增序号）。
- `pair_estimate` 见证失配时，若前道完工不变、两条时间线的增长恰好等于备忘之后记录的插入数、且新增段全部落在扫描区间之外（右端按闭区间判，因为认证跳过在触碰处仍会延伸），旧试算就仍然精确；只有机台工种历史变了时才用 `refresh_changeover_penalty` 重算换型罚分（与 `estimate_internal_slot` 尾部完全相同的调用）。
- 任何未记录的变异（直接改列表、整体替换、缩短）都让再验证失效，回到完整试算；缓存关闭时 `estimate_internal_slot` 不记录任何东西。

## 明确不做

- 不改内层 GraphReady 组合、局搜邻域与目标函数；不引入并行；不改候选列表合同（仍是 1 基线 + N 档）。
- 不做跨班次的忙块跳过：认证窗口保证窗内效率恒定、结束时刻随开工单调，跨窗跳过在按日效率变化的日历下不再与逐跳扫描等价。
- 不改 `CalendarEngine` 的按天循环：重复率测量表明解码内备忘已吃掉绝大部分日历成本，改算术只剩语义风险。

# 修复第四轮审查五项低级别问题plan深度review
- 日期: 2026-04-08
- 概述: 针对修复第四轮审查五项低级别问题的plan进行实现可达成性、简洁性、严谨性与潜在风险的深度审查。日期：2026-04-08
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 修复第四轮审查五项低级别问题plan深度review

- 日期：2026-04-08
- 目标：审查 `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md` 的设计是否能准确达成既定目的，并核验相关实现链路是否存在遗漏、过度兜底、静默回退、逻辑不严谨或潜在 BUG。
- 范围：`core/services/scheduler/schedule_optimizer.py`、`core/algorithms/greedy/dispatch/runtime_state.py`、`core/algorithms/greedy/downtime.py`、`core/algorithms/greedy/internal_slot.py`、相关排序输入构建逻辑与对应测试。

## 初始结论

先按模块逐步核对，并在每完成一个有意义的审查单元后记录 milestone。

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_optimizer.py, core/algorithms/greedy/scheduler.py, tests/test_algorithm_date_boundary_split.py, tests/test_optimizer_build_order_once_per_strategy.py, core/algorithms/greedy/dispatch/runtime_state.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/dispatch/sgs.py, tests/test_downtime_timeline_ordered_insert.py, tests/regression_downtime_overlap_skips_invalid_segments.py, tests/regression_dispatch_blocking_consistency.py, core/algorithms/greedy/internal_slot.py, tests/test_internal_slot_estimator_consistency.py, tests/test_sgs_internal_scoring_matches_execution.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 4
- 问题严重级别分布: 高 0 / 中 1 / 低 3
- 最新结论: 该 plan 的主体设计是成立的：五项修复都保持局部、小范围、无公开接口扰动，fix-01/03、fix-02、fix-04、fix-05 的实现方向均较简洁，没有引入新的过度兜底或静默回退。从代码链路看，真正需要修正的不是核心改法，而是验证闭环的严谨性。当前最关键的问题有三类：其一，fix-01 的验证没有直接锁定 optimize 路径的 due_date/ready_date 行为；其二，fix-02 没有为 `accumulate_busy_hours` 的新断言补直测；其三，也是最重要的，plan 中两份 `regression_*.py` 脚本被错误地放进 `pytest` 命令里，按现状不会执行断言，导致最终验证结论失真。此外，fix-05 还应补一条“零工时与重叠占用/停机”的语义测试，否则零工时只验证了不崩溃，尚未真正锁定行为。综上，我认为该 plan 可以达成目标，但应先修订验证命令与补测项后再执行，当前状态适合有条件通过，而不适合按原文直接落地。
- 下一步建议: 先修订 plan：1）把两个 script 风格回归文件改为直接 `python tests/xxx.py` 执行，或改造成 pytest 用例；2）补 `accumulate_busy_hours` 坏参直测；3）补 optimize 级 due/ready 行为回归；4）补零工时重叠场景测试。完成这四项后再进入实现与统一验证。
- 总体结论: 有条件通过

## 评审发现

### 修复1验证未直接锁定 optimize 的 due/ready 语义

- ID: PLAN-R4-01
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 为修复 1 指定的验证集合中，`tests/test_optimizer_build_order_once_per_strategy.py` 只通过自定义 `build_order` 桩函数验证 `_run_multi_start` 的本地缓存，不会执行 `schedule_optimizer._build_order` 的真实实现；而 `tests/test_algorithm_date_boundary_split.py` 的 optimize 级断言只覆盖 `created_at` 的策略感知和单批次路径，没有直接证明去掉 `_build_order` 内的 due_date/ready_date 覆盖循环后，optimize 路径的 due/ready 行为仍被稳定锁定。修复方案本身是对的，但验证闭环没有精确命中改动点。
- 建议:

  补一条直接走 `optimize_schedule -> _build_order -> StrategyFactory.sort` 的用例，至少使用两个批次，显式断言 due_date 或 ready_date 对排序/校验的影响保持不变。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:363-376#_build_order`
  - `core/algorithms/greedy/scheduler.py:83-106#build_batch_sort_inputs`
  - `tests/test_optimizer_build_order_once_per_strategy.py:34-60#_build_order stub`
  - `tests/test_algorithm_date_boundary_split.py:139-219#test_optimize_schedule_created_at_strict_only_for_current_strategy`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/scheduler.py`
  - `tests/test_algorithm_date_boundary_split.py`
  - `tests/test_optimizer_build_order_once_per_strategy.py`

### 修复2缺少 accumulate_busy_hours 新断言的直测

- ID: PLAN-R4-02
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 为 fix-02 指定的验证文件 `tests/test_downtime_timeline_ordered_insert.py` 目前只直接验证了 `update_machine_last_state` 对非 `datetime end_time` 的拒绝路径，以及 `accumulate_busy_hours` 的正常累计路径；并没有任何断言命中新加入的 `accumulate_busy_hours(start_time/end_time)` 类型检查分支。也就是说，即使实现忘记加断言，plan 给出的验证命令仍可能全部通过。
- 建议:

  在同一测试文件中补一个 `accumulate_busy_hours` 的坏参用例，至少分别覆盖 `start_time` 或 `end_time` 为字符串时抛出 `TypeError`。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:47-57`
  - `core/algorithms/greedy/dispatch/runtime_state.py:7-21#accumulate_busy_hours`
  - `tests/test_downtime_timeline_ordered_insert.py:44-105#test_runtime_state_helpers_handle_seed_and_dispatch_modes / test_update_machine_last_state_rejects_non_datetime_end_time`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/algorithms/greedy/dispatch/runtime_state.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/test_downtime_timeline_ordered_insert.py`
  - `tests/regression_downtime_overlap_skips_invalid_segments.py`
  - `tests/regression_dispatch_blocking_consistency.py`

### 计划中的两个 regression 脚本用 pytest 执行不会跑到断言

- ID: PLAN-R4-03
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 的 fix-04 验证命令和最终回归命令都把 `tests/regression_downtime_overlap_skips_invalid_segments.py`、`tests/regression_dispatch_blocking_consistency.py` 作为 pytest 目标文件。但这两个文件都是脚本式 `main()` 入口，断言全部写在 `main()` 内，并且只在 `if __name__ == "__main__"` 时执行；文件内没有 pytest 可收集的 `test_*` 函数。按 plan 当前写法使用 `python -m pytest ...` 时，这两份文件不会执行核心断言，导致验证结果产生“通过但未实际验证”的假象。
- 建议:

  二选一处理：要么把这两份文件改造成 pytest 风格的 `test_*` 用例；要么在 plan 中明确用 `python tests/xxx.py` 直接执行脚本，而不是 `python -m pytest`。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:67-73`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:94-99`
  - `tests/regression_downtime_overlap_skips_invalid_segments.py:14-40#main`
  - `tests/regression_dispatch_blocking_consistency.py:136-153#main`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/algorithms/greedy/dispatch/runtime_state.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/test_downtime_timeline_ordered_insert.py`
  - `tests/regression_downtime_overlap_skips_invalid_segments.py`
  - `tests/regression_dispatch_blocking_consistency.py`

### 零工时与占用重叠的语义仍未锁定

- ID: PLAN-R4-04
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 为 fix-05 新增的零工时测试只要求 `setup_hours=0、unit_hours=0` 时返回 `start_time == end_time` 且不报错，这能覆盖“零工时不崩溃”的基本目标；但它没有覆盖零工时恰好落在设备占用、人员占用或停机区间中的情况。当前 `estimate_internal_slot` 会把 `start_time == end_time` 的瞬时工序继续送入 `find_overlap_shift_end`，而后者会把落在区间内部的零长度查询也视为重叠并返回 shift。这样瞬时工序会被整体后移，后移后的 `end_time` 还会推进批次进度。如果业务预期是“零工时不占资源”，这就是潜在 BUG；即便业务接受当前语义，至少也需要一条测试把该语义显式固定下来。
- 建议:

  补一条零工时重叠场景用例，并先明确业务预期：若零工时不应占资源，则可在 `total_base == 0` 且通过初始 `adjust_to_working_time` 后直接返回；若仍要求资源空闲，也应把该语义写进测试断言，避免后续维护者误改。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:77-90`
  - `core/algorithms/greedy/internal_slot.py:160-185#estimate_internal_slot`
  - `core/algorithms/greedy/downtime.py:67-80#find_overlap_shift_end`
  - `core/algorithms/greedy/dispatch/batch_order.py:106-108#batch_progress update`
  - `core/algorithms/greedy/dispatch/sgs.py:626-629#batch_progress update`
  - `tests/test_internal_slot_estimator_consistency.py:149-284#现有 zero/efficiency 相关测试上下文`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/algorithms/greedy/internal_slot.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/test_internal_slot_estimator_consistency.py`
  - `tests/test_sgs_internal_scoring_matches_execution.py`

## 评审里程碑

### M1 · 第一轮：schedule_optimizer 去双重解析方案与验证链审查

- 状态: 已完成
- 记录时间: 2026-04-08T17:28:27.353Z
- 已审模块: core/services/scheduler/schedule_optimizer.py, core/algorithms/greedy/scheduler.py, tests/test_algorithm_date_boundary_split.py, tests/test_optimizer_build_order_once_per_strategy.py
- 摘要:

  完成对 `schedule_optimizer.py` 中 `_build_order`、`build_batch_sort_inputs`、`_run_multi_start` 及两条验证用例的交叉审查。结论：修复 1/3 的代码设计本身是正确且更简洁的，`_build_order` 中 L369-L374 的覆盖循环确实与 `build_batch_sort_inputs` 的 `due_date/ready_date` 解析重复；删除循环和两个闭包能够收敛到单一事实源，不会引入新的静默回退。但当前 plan 给出的验证闭环偏弱：`tests/test_optimizer_build_order_once_per_strategy.py` 仅验证 multi-start 的本地缓存包装，不会触达 `schedule_optimizer._build_order` 的真实 due/ready 解析逻辑；`tests/test_algorithm_date_boundary_split.py` 虽会经过 optimize 路径，但其 optimize 级断言只锁定 `created_at` 策略感知与单批次路径，未直接锁定 due/ready 行为保持不变。
- 结论:

  修复 1/3 设计方向正确且实现会更简洁，但建议补一条 optimize 级 due_date/ready_date 行为回归，以真正锁住“删循环不改语义”。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:23-43`
  - `core/services/scheduler/schedule_optimizer.py:349-376#_build_order`
  - `core/algorithms/greedy/scheduler.py:69-106#_parse_due_date_for_sort / _parse_ready_date_for_sort / build_batch_sort_inputs`
  - `tests/test_optimizer_build_order_once_per_strategy.py:30-75#test_build_order_is_cached_per_strategy_within_single_multi_start_call`
  - `tests/test_algorithm_date_boundary_split.py:139-219#test_optimize_schedule_created_at_strict_only_for_current_strategy`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/scheduler.py`
  - `tests/test_algorithm_date_boundary_split.py`
  - `tests/test_optimizer_build_order_once_per_strategy.py`
- 下一步建议:

  继续审查 runtime_state.py 与 downtime.py，重点核对 fix-02/fix-04 的实际收益与验证闭环。
- 问题:
  - [低] 测试: 修复1验证未直接锁定 optimize 的 due/ready 语义

### M2 · 第二轮：runtime_state 与 downtime 修复项及验证命令审查

- 状态: 已完成
- 记录时间: 2026-04-08T17:29:29.814Z
- 已审模块: core/algorithms/greedy/dispatch/runtime_state.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/dispatch/sgs.py, tests/test_downtime_timeline_ordered_insert.py, tests/regression_downtime_overlap_skips_invalid_segments.py, tests/regression_dispatch_blocking_consistency.py
- 摘要:

  完成对 `runtime_state.py`、`downtime.py`、相关调用链与验证命令的交叉审查。结论：fix-02 与 fix-04 的代码改动都很小，设计上没有过度兜底；`accumulate_busy_hours` 增加 `datetime` 断言也与 `update_machine_last_state` 的显式失败风格一致，`ordered -> valid_segments` 的重命名能够改善可读性。但 plan 的验证设计存在两处明显缺口：第一，`tests/test_downtime_timeline_ordered_insert.py` 当前只直测 `update_machine_last_state` 的异常分支，并没有命中 `accumulate_busy_hours` 新增的 `TypeError` 路径；第二，plan 中用于 fix-04 和最终验证的两个 `regression_*.py` 文件都是脚本式 `main()` 入口而非 pytest 测试函数，按 plan 写法使用 `python -m pytest ...` 不会执行其中断言，导致验证结果被高估。
- 结论:

  fix-02/fix-04 的改动方向正确，但当前验证命令并不能完整证明改动生效，尤其是两个 script 风格回归文件在 pytest 下属于无效验证。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:47-57`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:67-73`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:94-99`
  - `core/algorithms/greedy/dispatch/runtime_state.py:7-21#accumulate_busy_hours`
  - `core/algorithms/greedy/dispatch/runtime_state.py:24-52#update_machine_last_state`
  - `tests/test_downtime_timeline_ordered_insert.py:44-105#test_runtime_state_helpers_handle_seed_and_dispatch_modes / test_update_machine_last_state_rejects_non_datetime_end_time`
  - `tests/regression_downtime_overlap_skips_invalid_segments.py:14-40#main`
  - `tests/regression_dispatch_blocking_consistency.py:136-153#main`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/algorithms/greedy/dispatch/runtime_state.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/test_downtime_timeline_ordered_insert.py`
  - `tests/regression_downtime_overlap_skips_invalid_segments.py`
  - `tests/regression_dispatch_blocking_consistency.py`
- 下一步建议:

  继续审查 internal_slot 与测试补充方案，重点检查零工时和效率边界设计是否真正锁住潜在风险。
- 问题:
  - [低] 测试: 修复2缺少 accumulate_busy_hours 新断言的直测
  - [中] 测试: 计划中的两个 regression 脚本用 pytest 执行不会跑到断言

### M3 · 第三轮：internal_slot 边界语义与补测方案审查

- 状态: 已完成
- 记录时间: 2026-04-08T17:30:50.018Z
- 已审模块: core/algorithms/greedy/internal_slot.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/dispatch/sgs.py, tests/test_internal_slot_estimator_consistency.py, tests/test_sgs_internal_scoring_matches_execution.py
- 摘要:

  完成对 `internal_slot.py`、`test_internal_slot_estimator_consistency.py` 以及相关调度结果传播链的深度审查。结论：fix-05 的总体方向是正确的，补上 `None/0.0/异常` 的效率边界和零工时场景，能够补足当前测试文件最明显的空白；同时现有文件已通过 `float('inf')`、`abort_after`、只读拷贝、正式计数器等用例锁住了不少关键行为。但是，plan 当前给出的零工时测试只覆盖“无资源占用/无停机”的简单路径，尚未锁定零工时与重叠占用的语义。根据 `estimate_internal_slot` 当前实现，只要 `start_time == end_time` 且该时刻落在占用区间内，`find_overlap_shift_end` 仍会返回 shift，从而把瞬时工序整体后移；而这个后移后的 `end_time` 还会继续推进 `batch_progress`。如果业务语义要求“零工时工序不占资源”，那么这会成为真实排产偏差。
- 结论:

  fix-05 设计总体合理，但仍建议补一条“零工时 + 资源占用/停机重叠”用例，先把预期语义锁定；否则当前 plan 只能证明零工时不崩溃，不能证明零工时语义正确。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md:77-90`
  - `core/algorithms/greedy/internal_slot.py:146-204#estimate_internal_slot`
  - `core/algorithms/greedy/downtime.py:62-80#find_overlap_shift_end`
  - `core/algorithms/greedy/scheduler.py:529-548#_schedule_internal`
  - `core/algorithms/greedy/dispatch/batch_order.py:88-108#dispatch_batch_order`
  - `core/algorithms/greedy/dispatch/sgs.py:608-629#dispatch_sgs`
  - `tests/test_internal_slot_estimator_consistency.py:149-284#现有 estimator 边界测试集合`
  - `tests/test_sgs_internal_scoring_matches_execution.py:154-194#test_sgs_probe_efficiency_fallback_does_not_pollute_formal_counter`
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
  - `core/algorithms/greedy/internal_slot.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/test_internal_slot_estimator_consistency.py`
  - `tests/test_sgs_internal_scoring_matches_execution.py`
- 下一步建议:

  汇总全部发现并给出对当前 plan 的总体结论与修订建议。
- 问题:
  - [低] 测试: 零工时与占用重叠的语义仍未锁定

## 最终结论

该 plan 的主体设计是成立的：五项修复都保持局部、小范围、无公开接口扰动，fix-01/03、fix-02、fix-04、fix-05 的实现方向均较简洁，没有引入新的过度兜底或静默回退。从代码链路看，真正需要修正的不是核心改法，而是验证闭环的严谨性。当前最关键的问题有三类：其一，fix-01 的验证没有直接锁定 optimize 路径的 due_date/ready_date 行为；其二，fix-02 没有为 `accumulate_busy_hours` 的新断言补直测；其三，也是最重要的，plan 中两份 `regression_*.py` 脚本被错误地放进 `pytest` 命令里，按现状不会执行断言，导致最终验证结论失真。此外，fix-05 还应补一条“零工时与重叠占用/停机”的语义测试，否则零工时只验证了不崩溃，尚未真正锁定行为。综上，我认为该 plan 可以达成目标，但应先修订验证命令与补测项后再执行，当前状态适合有条件通过，而不适合按原文直接落地。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnqbgow3-oh82la",
  "createdAt": "2026-04-08T00:00:00.000Z",
  "updatedAt": "2026-04-08T17:31:08.137Z",
  "finalizedAt": "2026-04-08T17:31:08.137Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "修复第四轮审查五项低级别问题plan深度review",
    "date": "2026-04-08",
    "overview": "针对修复第四轮审查五项低级别问题的plan进行实现可达成性、简洁性、严谨性与潜在风险的深度审查。日期：2026-04-08"
  },
  "scope": {
    "markdown": "# 修复第四轮审查五项低级别问题plan深度review\n\n- 日期：2026-04-08\n- 目标：审查 `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md` 的设计是否能准确达成既定目的，并核验相关实现链路是否存在遗漏、过度兜底、静默回退、逻辑不严谨或潜在 BUG。\n- 范围：`core/services/scheduler/schedule_optimizer.py`、`core/algorithms/greedy/dispatch/runtime_state.py`、`core/algorithms/greedy/downtime.py`、`core/algorithms/greedy/internal_slot.py`、相关排序输入构建逻辑与对应测试。\n\n## 初始结论\n\n先按模块逐步核对，并在每完成一个有意义的审查单元后记录 milestone。"
  },
  "summary": {
    "latestConclusion": "该 plan 的主体设计是成立的：五项修复都保持局部、小范围、无公开接口扰动，fix-01/03、fix-02、fix-04、fix-05 的实现方向均较简洁，没有引入新的过度兜底或静默回退。从代码链路看，真正需要修正的不是核心改法，而是验证闭环的严谨性。当前最关键的问题有三类：其一，fix-01 的验证没有直接锁定 optimize 路径的 due_date/ready_date 行为；其二，fix-02 没有为 `accumulate_busy_hours` 的新断言补直测；其三，也是最重要的，plan 中两份 `regression_*.py` 脚本被错误地放进 `pytest` 命令里，按现状不会执行断言，导致最终验证结论失真。此外，fix-05 还应补一条“零工时与重叠占用/停机”的语义测试，否则零工时只验证了不崩溃，尚未真正锁定行为。综上，我认为该 plan 可以达成目标，但应先修订验证命令与补测项后再执行，当前状态适合有条件通过，而不适合按原文直接落地。",
    "recommendedNextAction": "先修订 plan：1）把两个 script 风格回归文件改为直接 `python tests/xxx.py` 执行，或改造成 pytest 用例；2）补 `accumulate_busy_hours` 坏参直测；3）补 optimize 级 due/ready 行为回归；4）补零工时重叠场景测试。完成这四项后再进入实现与统一验证。",
    "reviewedModules": [
      "core/services/scheduler/schedule_optimizer.py",
      "core/algorithms/greedy/scheduler.py",
      "tests/test_algorithm_date_boundary_split.py",
      "tests/test_optimizer_build_order_once_per_strategy.py",
      "core/algorithms/greedy/dispatch/runtime_state.py",
      "core/algorithms/greedy/downtime.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "tests/test_downtime_timeline_ordered_insert.py",
      "tests/regression_downtime_overlap_skips_invalid_segments.py",
      "tests/regression_dispatch_blocking_consistency.py",
      "core/algorithms/greedy/internal_slot.py",
      "tests/test_internal_slot_estimator_consistency.py",
      "tests/test_sgs_internal_scoring_matches_execution.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 4,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 3
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：schedule_optimizer 去双重解析方案与验证链审查",
      "status": "completed",
      "recordedAt": "2026-04-08T17:28:27.353Z",
      "summaryMarkdown": "完成对 `schedule_optimizer.py` 中 `_build_order`、`build_batch_sort_inputs`、`_run_multi_start` 及两条验证用例的交叉审查。结论：修复 1/3 的代码设计本身是正确且更简洁的，`_build_order` 中 L369-L374 的覆盖循环确实与 `build_batch_sort_inputs` 的 `due_date/ready_date` 解析重复；删除循环和两个闭包能够收敛到单一事实源，不会引入新的静默回退。但当前 plan 给出的验证闭环偏弱：`tests/test_optimizer_build_order_once_per_strategy.py` 仅验证 multi-start 的本地缓存包装，不会触达 `schedule_optimizer._build_order` 的真实 due/ready 解析逻辑；`tests/test_algorithm_date_boundary_split.py` 虽会经过 optimize 路径，但其 optimize 级断言只锁定 `created_at` 策略感知与单批次路径，未直接锁定 due/ready 行为保持不变。",
      "conclusionMarkdown": "修复 1/3 设计方向正确且实现会更简洁，但建议补一条 optimize 级 due_date/ready_date 行为回归，以真正锁住“删循环不改语义”。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 23,
          "lineEnd": 43
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 349,
          "lineEnd": 376,
          "symbol": "_build_order"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 69,
          "lineEnd": 106,
          "symbol": "_parse_due_date_for_sort / _parse_ready_date_for_sort / build_batch_sort_inputs"
        },
        {
          "path": "tests/test_optimizer_build_order_once_per_strategy.py",
          "lineStart": 30,
          "lineEnd": 75,
          "symbol": "test_build_order_is_cached_per_strategy_within_single_multi_start_call"
        },
        {
          "path": "tests/test_algorithm_date_boundary_split.py",
          "lineStart": 139,
          "lineEnd": 219,
          "symbol": "test_optimize_schedule_created_at_strict_only_for_current_strategy"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "tests/test_algorithm_date_boundary_split.py"
        },
        {
          "path": "tests/test_optimizer_build_order_once_per_strategy.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_optimizer.py",
        "core/algorithms/greedy/scheduler.py",
        "tests/test_algorithm_date_boundary_split.py",
        "tests/test_optimizer_build_order_once_per_strategy.py"
      ],
      "recommendedNextAction": "继续审查 runtime_state.py 与 downtime.py，重点核对 fix-02/fix-04 的实际收益与验证闭环。",
      "findingIds": [
        "PLAN-R4-01"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：runtime_state 与 downtime 修复项及验证命令审查",
      "status": "completed",
      "recordedAt": "2026-04-08T17:29:29.814Z",
      "summaryMarkdown": "完成对 `runtime_state.py`、`downtime.py`、相关调用链与验证命令的交叉审查。结论：fix-02 与 fix-04 的代码改动都很小，设计上没有过度兜底；`accumulate_busy_hours` 增加 `datetime` 断言也与 `update_machine_last_state` 的显式失败风格一致，`ordered -> valid_segments` 的重命名能够改善可读性。但 plan 的验证设计存在两处明显缺口：第一，`tests/test_downtime_timeline_ordered_insert.py` 当前只直测 `update_machine_last_state` 的异常分支，并没有命中 `accumulate_busy_hours` 新增的 `TypeError` 路径；第二，plan 中用于 fix-04 和最终验证的两个 `regression_*.py` 文件都是脚本式 `main()` 入口而非 pytest 测试函数，按 plan 写法使用 `python -m pytest ...` 不会执行其中断言，导致验证结果被高估。",
      "conclusionMarkdown": "fix-02/fix-04 的改动方向正确，但当前验证命令并不能完整证明改动生效，尤其是两个 script 风格回归文件在 pytest 下属于无效验证。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 47,
          "lineEnd": 57
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 67,
          "lineEnd": 73
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 94,
          "lineEnd": 99
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py",
          "lineStart": 7,
          "lineEnd": 21,
          "symbol": "accumulate_busy_hours"
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py",
          "lineStart": 24,
          "lineEnd": 52,
          "symbol": "update_machine_last_state"
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py",
          "lineStart": 44,
          "lineEnd": 105,
          "symbol": "test_runtime_state_helpers_handle_seed_and_dispatch_modes / test_update_machine_last_state_rejects_non_datetime_end_time"
        },
        {
          "path": "tests/regression_downtime_overlap_skips_invalid_segments.py",
          "lineStart": 14,
          "lineEnd": 40,
          "symbol": "main"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py",
          "lineStart": 136,
          "lineEnd": 153,
          "symbol": "main"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py"
        },
        {
          "path": "tests/regression_downtime_overlap_skips_invalid_segments.py"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/dispatch/runtime_state.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "tests/test_downtime_timeline_ordered_insert.py",
        "tests/regression_downtime_overlap_skips_invalid_segments.py",
        "tests/regression_dispatch_blocking_consistency.py"
      ],
      "recommendedNextAction": "继续审查 internal_slot 与测试补充方案，重点检查零工时和效率边界设计是否真正锁住潜在风险。",
      "findingIds": [
        "PLAN-R4-02",
        "PLAN-R4-03"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：internal_slot 边界语义与补测方案审查",
      "status": "completed",
      "recordedAt": "2026-04-08T17:30:50.018Z",
      "summaryMarkdown": "完成对 `internal_slot.py`、`test_internal_slot_estimator_consistency.py` 以及相关调度结果传播链的深度审查。结论：fix-05 的总体方向是正确的，补上 `None/0.0/异常` 的效率边界和零工时场景，能够补足当前测试文件最明显的空白；同时现有文件已通过 `float('inf')`、`abort_after`、只读拷贝、正式计数器等用例锁住了不少关键行为。但是，plan 当前给出的零工时测试只覆盖“无资源占用/无停机”的简单路径，尚未锁定零工时与重叠占用的语义。根据 `estimate_internal_slot` 当前实现，只要 `start_time == end_time` 且该时刻落在占用区间内，`find_overlap_shift_end` 仍会返回 shift，从而把瞬时工序整体后移；而这个后移后的 `end_time` 还会继续推进 `batch_progress`。如果业务语义要求“零工时工序不占资源”，那么这会成为真实排产偏差。",
      "conclusionMarkdown": "fix-05 设计总体合理，但仍建议补一条“零工时 + 资源占用/停机重叠”用例，先把预期语义锁定；否则当前 plan 只能证明零工时不崩溃，不能证明零工时语义正确。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 77,
          "lineEnd": 90
        },
        {
          "path": "core/algorithms/greedy/internal_slot.py",
          "lineStart": 146,
          "lineEnd": 204,
          "symbol": "estimate_internal_slot"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 62,
          "lineEnd": 80,
          "symbol": "find_overlap_shift_end"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 529,
          "lineEnd": 548,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 88,
          "lineEnd": 108,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 608,
          "lineEnd": 629,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 149,
          "lineEnd": 284,
          "symbol": "现有 estimator 边界测试集合"
        },
        {
          "path": "tests/test_sgs_internal_scoring_matches_execution.py",
          "lineStart": 154,
          "lineEnd": 194,
          "symbol": "test_sgs_probe_efficiency_fallback_does_not_pollute_formal_counter"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/algorithms/greedy/internal_slot.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py"
        },
        {
          "path": "tests/test_sgs_internal_scoring_matches_execution.py"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/internal_slot.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "tests/test_internal_slot_estimator_consistency.py",
        "tests/test_sgs_internal_scoring_matches_execution.py"
      ],
      "recommendedNextAction": "汇总全部发现并给出对当前 plan 的总体结论与修订建议。",
      "findingIds": [
        "PLAN-R4-04"
      ]
    }
  ],
  "findings": [
    {
      "id": "PLAN-R4-01",
      "severity": "low",
      "category": "test",
      "title": "修复1验证未直接锁定 optimize 的 due/ready 语义",
      "descriptionMarkdown": "plan 为修复 1 指定的验证集合中，`tests/test_optimizer_build_order_once_per_strategy.py` 只通过自定义 `build_order` 桩函数验证 `_run_multi_start` 的本地缓存，不会执行 `schedule_optimizer._build_order` 的真实实现；而 `tests/test_algorithm_date_boundary_split.py` 的 optimize 级断言只覆盖 `created_at` 的策略感知和单批次路径，没有直接证明去掉 `_build_order` 内的 due_date/ready_date 覆盖循环后，optimize 路径的 due/ready 行为仍被稳定锁定。修复方案本身是对的，但验证闭环没有精确命中改动点。",
      "recommendationMarkdown": "补一条直接走 `optimize_schedule -> _build_order -> StrategyFactory.sort` 的用例，至少使用两个批次，显式断言 due_date 或 ready_date 对排序/校验的影响保持不变。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 363,
          "lineEnd": 376,
          "symbol": "_build_order"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 83,
          "lineEnd": 106,
          "symbol": "build_batch_sort_inputs"
        },
        {
          "path": "tests/test_optimizer_build_order_once_per_strategy.py",
          "lineStart": 34,
          "lineEnd": 60,
          "symbol": "_build_order stub"
        },
        {
          "path": "tests/test_algorithm_date_boundary_split.py",
          "lineStart": 139,
          "lineEnd": 219,
          "symbol": "test_optimize_schedule_created_at_strict_only_for_current_strategy"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "tests/test_algorithm_date_boundary_split.py"
        },
        {
          "path": "tests/test_optimizer_build_order_once_per_strategy.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "PLAN-R4-02",
      "severity": "low",
      "category": "test",
      "title": "修复2缺少 accumulate_busy_hours 新断言的直测",
      "descriptionMarkdown": "plan 为 fix-02 指定的验证文件 `tests/test_downtime_timeline_ordered_insert.py` 目前只直接验证了 `update_machine_last_state` 对非 `datetime end_time` 的拒绝路径，以及 `accumulate_busy_hours` 的正常累计路径；并没有任何断言命中新加入的 `accumulate_busy_hours(start_time/end_time)` 类型检查分支。也就是说，即使实现忘记加断言，plan 给出的验证命令仍可能全部通过。",
      "recommendationMarkdown": "在同一测试文件中补一个 `accumulate_busy_hours` 的坏参用例，至少分别覆盖 `start_time` 或 `end_time` 为字符串时抛出 `TypeError`。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 47,
          "lineEnd": 57
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py",
          "lineStart": 7,
          "lineEnd": 21,
          "symbol": "accumulate_busy_hours"
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py",
          "lineStart": 44,
          "lineEnd": 105,
          "symbol": "test_runtime_state_helpers_handle_seed_and_dispatch_modes / test_update_machine_last_state_rejects_non_datetime_end_time"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py"
        },
        {
          "path": "tests/regression_downtime_overlap_skips_invalid_segments.py"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "PLAN-R4-03",
      "severity": "medium",
      "category": "test",
      "title": "计划中的两个 regression 脚本用 pytest 执行不会跑到断言",
      "descriptionMarkdown": "plan 的 fix-04 验证命令和最终回归命令都把 `tests/regression_downtime_overlap_skips_invalid_segments.py`、`tests/regression_dispatch_blocking_consistency.py` 作为 pytest 目标文件。但这两个文件都是脚本式 `main()` 入口，断言全部写在 `main()` 内，并且只在 `if __name__ == \"__main__\"` 时执行；文件内没有 pytest 可收集的 `test_*` 函数。按 plan 当前写法使用 `python -m pytest ...` 时，这两份文件不会执行核心断言，导致验证结果产生“通过但未实际验证”的假象。",
      "recommendationMarkdown": "二选一处理：要么把这两份文件改造成 pytest 风格的 `test_*` 用例；要么在 plan 中明确用 `python tests/xxx.py` 直接执行脚本，而不是 `python -m pytest`。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 67,
          "lineEnd": 73
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 94,
          "lineEnd": 99
        },
        {
          "path": "tests/regression_downtime_overlap_skips_invalid_segments.py",
          "lineStart": 14,
          "lineEnd": 40,
          "symbol": "main"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py",
          "lineStart": 136,
          "lineEnd": 153,
          "symbol": "main"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py"
        },
        {
          "path": "tests/regression_downtime_overlap_skips_invalid_segments.py"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "PLAN-R4-04",
      "severity": "low",
      "category": "test",
      "title": "零工时与占用重叠的语义仍未锁定",
      "descriptionMarkdown": "plan 为 fix-05 新增的零工时测试只要求 `setup_hours=0、unit_hours=0` 时返回 `start_time == end_time` 且不报错，这能覆盖“零工时不崩溃”的基本目标；但它没有覆盖零工时恰好落在设备占用、人员占用或停机区间中的情况。当前 `estimate_internal_slot` 会把 `start_time == end_time` 的瞬时工序继续送入 `find_overlap_shift_end`，而后者会把落在区间内部的零长度查询也视为重叠并返回 shift。这样瞬时工序会被整体后移，后移后的 `end_time` 还会推进批次进度。如果业务预期是“零工时不占资源”，这就是潜在 BUG；即便业务接受当前语义，至少也需要一条测试把该语义显式固定下来。",
      "recommendationMarkdown": "补一条零工时重叠场景用例，并先明确业务预期：若零工时不应占资源，则可在 `total_base == 0` 且通过初始 `adjust_to_working_time` 后直接返回；若仍要求资源空闲，也应把该语义写进测试断言，避免后续维护者误改。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md",
          "lineStart": 77,
          "lineEnd": 90
        },
        {
          "path": "core/algorithms/greedy/internal_slot.py",
          "lineStart": 160,
          "lineEnd": 185,
          "symbol": "estimate_internal_slot"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 67,
          "lineEnd": 80,
          "symbol": "find_overlap_shift_end"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 106,
          "lineEnd": 108,
          "symbol": "batch_progress update"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 626,
          "lineEnd": 629,
          "symbol": "batch_progress update"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 149,
          "lineEnd": 284,
          "symbol": "现有 zero/efficiency 相关测试上下文"
        },
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        },
        {
          "path": "core/algorithms/greedy/internal_slot.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py"
        },
        {
          "path": "tests/test_sgs_internal_scoring_matches_execution.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:3c0a68676fac4adfc929d0e5a328f0b2d3b61fa6d62b9c2f454b8af32f36793a",
    "generatedAt": "2026-04-08T17:31:08.137Z",
    "locale": "zh-CN"
  }
}
```

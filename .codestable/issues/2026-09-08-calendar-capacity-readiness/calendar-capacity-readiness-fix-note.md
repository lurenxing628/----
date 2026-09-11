---
doc_type: issue-fix
issue: 2026-09-08-calendar-capacity-readiness
path: fast-track
fix_date: 2026-09-08
tags: [calendar, capacity, readiness, greedy, report]
---

# 跨夜容量与齐套日期下界修复记录

## 结论与范围

- 两处修复及两个集成尾巴均已完成。此前同一组 26 个影响面文件最终 **264 passed in 7.02s**，无失败、无跳过、无 xfail。相比最初 254 项，多出 10 项补充的参数化用例。
- readiness 只写原始时间下界，不调用不适用的全局对齐。新增真实内存库反例验证：全局搜索超过上限，但个人覆盖仍可排产。实际资源日历异常仍进入失败明细和原始异常日志。
- 经用户新增授权，定点更新 date_boundary_split 原两项合同，并给报表旧测试的 policy fixture 补真实 DayPolicy；未放宽原 SQL 降级断言。没有把已知失败留给主线程。
- 累计修改两个产品文件、两份原有测试，新增两份独立测试和本记录；未新增 helper、依赖或日历接口。
- 不重写日历引擎，不裁决分段效率、内外协评分或其他策略。
- 未修改运行 state/slot/downtime、schedule_execution_*、optimizer*、evaluation、前端、启动、打包、report_number_parsing 或共享注册台账。
- 未提交、未暂存、未清理已有 dirty，未操作真实数据库，未启动子代理。

## 根因和实际改法

### 容量

- 真实路径是 `core/services/report/calculations.py:66` 的 `capacity_hours`，不是 `utilization/calculations.py`。
- 调用入口为 `core/services/report/report_engine.py:386`。该入口已有自然日范围合同：开始日 00:00 含，结束日次日 00:00 不含；本轮不改入口。
- 旧算法逐日取午夜 `policy_for_datetime` 后直接加整班 `shift_hours * efficiency`。日历引擎让凌晨归属前夜是正确行为，但报表这样采样会重复前夜并漏掉次日班次。
- 现改为读取既有 `DayPolicy.work_window()`，累计实际工作窗与剩余统计范围的交集，按该窗原有 efficiency 加权；推进至该窗结束并重新取策略，已结束窗则推进到下一自然日。没有把新规则塞进日历引擎。
- 保留全局单资源容量口径、六位小数内部舍入、报表两位小数、零容量降级、不按 priority 或个人日历分母细分、不减停机、不改任务取数和筛选条件。
- 内存库例子：2026-09-07 20:00 至 2026-09-08 06:00 共 10h，随后 08:00 至 16:00 共 8h。两天合计从 20h 改为 18h；只查 9 月 7 日为 4h，只查 9 月 8 日为 14h。范围外的前夜只计入范围内的尾段，末夜范围外尾段不计入。

### 齐套

- `core/algorithms/greedy/scheduler.py:399` 的 `_initialize_ready_progress` 原先未选定人员就调用全局 `adjust_to_working_time`，把周日齐套提前改成周一开工下界，后续个人覆盖无法把时间退回周日。
- 最终只执行 `state.advance_batch(batch_id, ready_start)`，不先调用全局日历。保留原解析、readiness 开关、strict 模式、helper 签名和现有进度取最大值逻辑。
- 曾为兼容旧空工序测试保留“全局调用但丢弃结果”，该中间方案不成立：全局搜索失败仍会挡住个人工作日，且增加无用成本。主审指出后，使用真实日历反例证实，再移除此调用。此前 94 项通过不能证明这一反例不存在。
- 现合同是实际资源排槽负责日历验证；不调用不适用的全局搜索，不等于捕获、忽略异常。未添加 try/except、默认成功或空工序专用分支，未改日历引擎的搜索上限和异常处理策略。
- 内部工序仍由已有排槽逻辑带实际 `operator_id` 调日历；外协仍由已有自然日推进逻辑执行。没有修改运行状态或排槽实现。
- 实测 2026-09-06 周日齐套：个人覆盖可工作时 9 月 6 日 08:00 开工；无覆盖时仍为 9 月 7 日 08:00。普通/urgent/critical 权限、固定和自动资源选择、batch_order/sgs、strict 开关均有测试。

## 本轮写入清单

1. `core/services/report/calculations.py`
2. `core/algorithms/greedy/scheduler.py`
3. `tests/scheduler_analysis/test_report_calendar_capacity_intersections.py`
4. `tests/algorithm/test_ready_date_resource_calendar_lower_bound.py`
5. `tests/algorithm/test_algorithm_date_boundary_split.py`（新增授权的原两项合同及说明）
6. `tests/scheduler_analysis/test_report_source_case_insensitive.py`（新增授权的 policy fixture）
7. `.codestable/issues/2026-09-08-calendar-capacity-readiness/calendar-capacity-readiness-fix-note.md`

`report_engine.py`、`utilization.py`、`report_number_parsing.py` 的既有 dirty 不属于本轮修改。报表入口继续调用修复后的原函数即可，无须改入口。

## 起步证据

- 已读取 AGENTS、attention、system-overview、项目版 cs-issue-fix 及记录模板；定向检索 compound 的 trick/explore，没有找到要求继续用午夜整班采样或齐套提前全局对齐的规则。
- 已运行 `python3 -m tools.symbol_locator whereis/callers/callees` 核对两个函数。capacity 的 deep 结果列出报表入口和 shift_hours_roundtrip 测试。
- 本地 SCIP 索引标记为 2026-07-12；对 `_initialize_ready_progress --deep` 报未找到。没有把它当作完整证据，也没有刷新共享索引；改用普通 callers/callees，并以当前源码和 `rg` 核对 `_prepare_run_state -> _initialize_ready_progress -> advance_batch` 及实际资源排槽调用。

## 实跑验证

运行解释器：仓库 `.venv/bin/python`，实际版本 **Python 3.8.10**。新测试全部使用 `schema_conn` 的 SQLite `:memory:`；相关旧测试使用自身的内存库或 pytest 临时目录。报表入口的新测试保留真实 CalendarService，仅替换方案解析/计划取数；原 SQL 降级测试继续执行真实内存库 SQL，没有改成 mock 数据。

### 真实全局不可用反例

- 内存 WorkCalendar 写入从 2026-09-06 起连续 3661 天停工，只有 O1 在 2026-09-06 的个人日历允许 08:00 至 16:00 工作。
- 真实 CalendarService 的全局 `adjust_to_working_time` 抛 BusinessError，code 为 CALENDAR_ERROR（6006）；指定 O1 则返回当天 08:00。没有 mock 策略返回值、搜索上限或查询数据。
- 然后用同一 CalendarService 运行 GreedyScheduler，覆盖 batch_order/sgs、固定/自动资源、strict 开/关，共 8 项。只包一层观察器记录排槽实际传入的 operator_id，不替换真实日历结果。
- 移除无用调用前：**8 failed, 62 deselected in 1.00s**，失败均发生于 `_initialize_ready_progress -> global adjust -> CALENDAR_ERROR`。移除后 8 项全部通过，结果为当天 08:00 至 09:00，排槽调用全部带 O1；包含在最终 264 项中。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/algorithm/test_ready_date_resource_calendar_lower_bound.py \
  -k personal_shift_survives_global_calendar_search_limit --tb=short
```

新增测试还覆盖前夜尾段、末夜截断、连续夜班、午夜结束、24h 班、默认工作日/周末、效率加权与舍入、零工时、空范围、异常不静默归零、报表分子/分母同范围和坏时间降级；齐套覆盖自然日外协 separate/merged、开关关闭、缺省/早于排产起点的日期、包括空工序在内的初始化不查全局日历，以及真实资源日历异常进入现有结构化失败明细和日志。

### 旧路径合同

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/algorithm/test_algorithms_a3_dependency_boundary.py::test_root_greedy_scheduler_public_contract_is_unchanged \
  tests/algorithm/test_algorithms_a3_dependency_boundary.py::test_old_paths_reexport_the_canonical_contract_and_runtime_objects \
  --tb=short
```

最终另跑结果：**2 passed in 0.36s**，退出码 0。旧 `core.algorithms` / `core.algorithms.greedy` 的 GreedyScheduler identity、公开签名和 date_parsers / ordering 等旧路径 re-export 保持。未改旧别名文件或这两项合同测试。

### 最终合并影响面

按用户要求重跑此前同一组 26 个文件：**264 passed in 7.02s**，退出码 0。包含原 254 项的文件范围和后来增加的 10 项参数化用例；未排除或 xfail 任何一项，没有遗留失败。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/scheduler_analysis/test_report_calendar_capacity_intersections.py \
  tests/algorithm/test_ready_date_resource_calendar_lower_bound.py \
  tests/algorithm/test_algorithm_date_boundary_split.py \
  tests/calendar_maintenance/test_calendar_shift_hours_roundtrip.py \
  tests/calendar_maintenance/test_calendar_shift_start_rollover.py \
  tests/calendar_maintenance/test_calendar_invalid_shift_window_contract.py \
  tests/calendar_maintenance/test_operator_calendar_override_allows_work_on_global_holiday.py \
  tests/calendar_maintenance/test_holiday_default_efficiency_read_guard.py \
  tests/scheduler_analysis/test_utilization_zero_capacity_degradation.py \
  tests/scheduler_analysis/test_report_source_case_insensitive.py \
  tests/scheduler_analysis/test_report_context_filters_contract.py \
  tests/scheduler_analysis/test_report_export_size_mode_selection.py \
  tests/scheduler_analysis/test_report_export_large_scope_rejects_need_async.py \
  tests/algorithm/test_greedy_refactor_contract.py \
  tests/algorithm/test_greedy_run_state_contract.py \
  tests/algorithm/test_greedy_ordering_contract.py \
  tests/algorithm/test_greedy_date_parsers.py \
  tests/algorithm/test_greedy_scheduler_base_date.py \
  tests/algorithm/test_dispatch_blocking_consistency.py \
  tests/algorithm/test_scheduler_strict_mode_dispatch_flags.py \
  tests/algorithm/test_external_merge_mode_case_insensitive.py \
  tests/algorithm/test_seed_external_group_cache_rebuild.py \
  tests/algorithm/test_internal_slot_estimator_consistency.py \
  tests/algorithm/test_efficiency_greater_than_one_shortens_hours.py \
  tests/algorithm/test_seed_results_sanitize_contract.py \
  tests/algorithm/test_greedy_scheduler_algo_stats_auto_assign.py --tb=short
```

两个集成尾巴的处理：

- `test_algorithm_date_boundary_split.py` 原两项现在为 `test_ready_date_resource_calendar_errors_remain_visible[False/True]`。实际排一条内部工序，断言日历收到原始 ready_date 零点和 O1；无排产结果、success=False、failed_ops=1、scheduled_ops=0；结构化失败明细保留工序号和 dispatch_operation_exception；日志中保留原文及同一个 RuntimeError 对象。不是删除异常断言，而是把断言移到真实适用的资源边界。
- 同文件其他测试（排序字段严格性、覆盖排序、readiness 关闭等）未改。AST 对照确认除文件说明和这一个参数化函数外，其余节点完全相同。
- `test_report_source_case_insensitive.py` 只在目标测试内导入并构造真实 DayPolicy，以 dt 的日期生成 8h 工作窗。原 SQL 建库/取数代码和全部降级 assert 保留，AST 对照为一致；原异常时间跳过计数、任务数、停机数与脱敏断言全部通过。
- 这两份旧测试的改动已获得用户明确授权；未修改共享测试注册或债务台账。

历史过程仅供追溯：最初影响面曾为 251 passed / 3 failed；为保留空工序全局调用得到的 94 passed 是不充分的中间快照，已被真实全局超限反例否定。最终合同及验证以上述 264 passed 为准。

### 静态检查及门禁边界

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check --no-cache \
  core/services/report/calculations.py core/algorithms/greedy/scheduler.py \
  tests/scheduler_analysis/test_report_calendar_capacity_intersections.py \
  tests/algorithm/test_ready_date_resource_calendar_lower_bound.py \
  tests/algorithm/test_algorithm_date_boundary_split.py \
  tests/scheduler_analysis/test_report_source_case_insensitive.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit \
  core/services/report/calculations.py core/algorithms/greedy/scheduler.py \
  tests/scheduler_analysis/test_report_calendar_capacity_intersections.py \
  tests/algorithm/test_ready_date_resource_calendar_lower_bound.py \
  tests/algorithm/test_algorithm_date_boundary_split.py \
  tests/scheduler_analysis/test_report_source_case_insensitive.py

PYTHONDONTWRITEBYTECODE=1 RUFF_NO_CACHE=true .venv/bin/python scripts/run_quality_gate.py --fast-precheck
```

- 最终六个 Python 文件通过 Ruff；Python 3.8 兼容扫描读取失败 0、解析拒绝 0、兼容风险 0。产品及原测试差异的 `git diff --check` 通过。
- 项目快速门禁较早曾实跑退出码 1，报告 19 个范围外 lint 问题，涉及 `.codestable/refactors/2026-09-08-sgs-probe-reuse/measure.py`、`tests/_support/optimizer_quality_matrix_cases.py`、`tests/_support/sgs_slot_reuse_case.py`、`tests/algorithm/test_optimizer_profile_predecode_dedup.py`、`tests/gantt/gantt_critical_chain_cache_support.py`、`tests/schedule/service/test_unselected_execution_resource_guardrails.py`。没有顺手修复；这是历史执行快照，不代表这些并发文件当前仍有相同问题。此次集成收尾没有重复全仓快速门禁。
- 按用户要求，最终只跑本轮影响面，未跑完整 algorithm 或完整质量门禁，全量由主代理统一进行。已有大量 dirty 和并发变化，不能称为 clean proof。未进行全量 pyright、全仓测试或 Win7 实机验证。

## 改动保留核对

- 修改前在进程内保存 3063 个已跟踪/未跟踪文件的内容指纹、目标文件原文和暂存 diff 指纹；没有为取快照写仓库或创建 commit。
- 收尾将 scheduler 本轮的一处替换在内存中逆应用，结果与入场 scheduler 原文完全相同，证明其既有 seed 等 dirty 被保留。`report_engine.py` 与入场原文完全相同。
- 暂存 diff 与入场完全相同，其 SHA-256 为 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`。
- 指纹对照显示运行 slot、optimizer、evaluation、执行约束、callgraph 缓存等范围外文件期间也发生了变化；本轮没有回退或接管它们。因此只声明本轮写入清单和当次局部实跑结果，不声明整树未变化、全仓无回归或 clean proof。

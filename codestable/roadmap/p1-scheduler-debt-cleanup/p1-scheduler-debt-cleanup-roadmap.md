---
doc_type: roadmap
slug: p1-scheduler-debt-cleanup
status: active
created: 2026-04-28
last_reviewed: 2026-04-28
tags: [scheduler, p1, technical-debt, quality-gate]
related_requirements: []
related_architecture: [codestable/architecture/ARCHITECTURE.md]
---

# P1 排产合同和技术债清理路线

## 背景

这份路线图用于承接 P1 技术债清理。它不是重新发明一套排产系统，而是在最新 `main` 的基础上，把排产主链里已经拆开的边界逐步收紧，用测试和门禁把合同固定下来。

本轮核实的关键事实：

- 最近提交已经完成了优化器大拆、贪心排产拆分、坏数据说明、优化器被拒方案原因记录等工作。后续 P1 不应再把“大拆优化器”放在最前面。
- `README.md` 已经把 `python scripts/run_quality_gate.py` 定为统一质量门禁，并说明门禁会串联 full-test-debt proof、ruff、pyright、架构适应度、治理台账和启动链专项回归。
- full-test-debt 的当前口径是：不能出现未登记的 full pytest 失败；已登记债务要被台账管住，而且数量只能减少。这不等于历史债务已经全部修完。
- 当前 active full-test-debt 登记只有 5 个 operator-machine 查询相关 xfail。排产 P1-8 到 P1-25 不是当前 active full-test-debt 的直接编号，执行前必须先建立编号和仓库真实事实源之间的映射。
- 复杂度台账、静默兜底台账、页面合同测试、启动链专项测试都可以是 P1 工作，但不能把它们的减少直接说成 full-test-debt 减少。只有关闭 active xfail 并通过同步脚本，才能说 full-test-debt 登记减少。

本轮已做过两层核实：

- 第一层是按模块查代码和台账，覆盖排产输入、冻结窗口、停机资源、优化器、落库、页面、运行态、插件和质量门禁。
- 第二层是对抗性审查，重点检查计划是否混淆债务口径、是否把已完成的优化器改造重复列为首要任务、是否漏掉 CodeStable 路线图格式、是否把支线任务插进排产主链。

因此，本路线图采用这个总顺序：

```text
PR-0 事实源和债务编号映射
-> PR-1 排产输入与外协组合并
-> PR-2 冻结窗口
-> PR-3 停机与资源池
-> PR-4 优化器结果合同补证
-> PR-5 summary/result_summary 合同
-> PR-6 落库与 auto-assign persist
-> PR-7 /scheduler/run 展示合同
-> PR-8 batches_page viewmodel
-> PR-9 runtime/plugin/infra 支线
```

其中 PR-5 放在落库之前，是因为落库会把 `result_summary` 写进排产历史；如果 summary 的形状还不稳定，落库和页面都会被上游脏数据误导。

## 范围

本路线图覆盖：

- P1 编号、债务台账、full-test-debt proof、质量门禁之间的真实映射。
- 排产主链合同清理：输入合同、冻结窗口、停机区间、资源池、优化器输出、summary、落库、页面展示。
- 运行态、插件、启动链、infra 类 P1 的支线处理规则。
- 每个 PR 的最小退出条件：对应登记项减少或被证明已不需要修；不能新增未登记 full pytest 失败；质量门禁仍然通过。

本路线图明确不做：

- 不把优化器再次作为首要大手术。
- 不把页面问题提前插到排产输入、冻结、资源合同之前。
- 不把复杂度台账减少、代码整理、断言改写说成 full-test-debt 减少。
- 不新增 full-test-debt 登记来“消化”失败。
- 不删除 `.limcode/`，它仍然是旧工作流归档和 APS 专项资产库。
- 不把 CodeStable 的 roadmap 写成 requirements 或 architecture。这里记录的是执行路线，不是现状需求或现状架构。

## 主链顺序

排产主链的真实数据流按下面顺序推进：

```text
排产输入合同
-> 冻结窗口 seed/meta
-> 停机区间预加载
-> 自动分配资源池
-> 候选资源停机区间补齐
-> 优化器输入和执行合同
-> 优化器输出和 summary/result_summary 合同
-> 落库校验和持久化
-> /scheduler/run 反馈
-> batches_page 展示
```

这个顺序决定了 PR 顺序。前面的合同没稳定时，后面的页面和落库测试很容易被误伤；后面的失败也不一定是后面模块自己的错。

## 模块拆分

### M0：事实源和证明口径

职责：

- 建立 P1-8 到 P1-25 的当前工作树证据映射。
- 区分 full-test-debt、复杂度台账、静默兜底台账、专项回归、普通测试覆盖。
- 给每个 PR 明确“它到底减少哪一种债务”，以及能不能算 full-test-debt 减少。
- 明确旧 P1 编号如果只有本路线图自引用，只能写“当前工作树未找到独立来源”，不能写成“旧编号已确认存在”或“旧编号客观不存在”。

主要文件：

- `README.md`
- `开发文档/技术债务治理台账.md`
- `tools/quality_gate_shared.py`
- `tools/check_full_test_debt.py`
- `tools/collect_full_test_debt.py`
- `scripts/sync_debt_ledger.py`
- `scripts/run_quality_gate.py`

M0 已完成的收口：

- 映射表已落盘到 `codestable/roadmap/p1-scheduler-debt-cleanup/drafts/p1-debt-source-map.md`。
- `rg -uuu` 搜索当前工作树并排除 `.git/` 元数据和本 roadmap 目录后，没有找到 P1-8 到 P1-25 的独立编号来源；这些编号目前只能作为本路线图整理标签使用。
- 当前 active full-test-debt 是 5 个 operator-machine/personnel 相关 xfail，不是 scheduler P1-8 到 P1-25。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` 已通过，结果为 `active_xfail_count=5`、`collected_count=700`、`unexpected_failure_count=0`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check` 已通过，结果为 `test_debt_count=5`。
- 本次没有改 `tools/test_registry.py`、`tools/quality_gate_shared.py`、`tools/test_debt_registry.py`、`tools/check_full_test_debt.py`、`tools/collect_full_test_debt.py`、`tests/conftest.py`、`tests/main_style_regression_runner.py`、`scripts/run_quality_gate.py`、`scripts/sync_debt_ledger.py` 的运行逻辑。

### M1：排产输入和外协组合并

职责：

- 固定 `_build_algo_operations_outcome()` 的外协组合并合同。
- 只在必要时拆小 helper，不扩大 route 或页面补丁。
- 对 `build_algo_operations(..., return_outcome=True)` 建合同测试。

主要文件：

- `core/services/scheduler/run/schedule_input_builder.py`
- `core/services/scheduler/run/schedule_input_contracts.py`
- `core/services/scheduler/run/schedule_template_lookup.py`

### M2：冻结窗口

职责：

- 把“配置关闭、天数为 0、没有上一版本、配置降级、没有可 seed 工序、上一版本加载失败”这些状态讲清楚。
- 保留旧 meta 字段，不破坏现有页面和历史解释。
- 可以新增 `freeze_disabled_reason`，但不强制引入对外 DTO；如果引入内部 decision 对象，也只作为实现收口。

主要文件：

- `core/services/scheduler/run/freeze_window.py`

### M3：停机区间和资源池

职责：

- 统一停机区间 load 和 extend 的 meta 合同。
- 保证自动分配资源池扩展出的候选设备也补齐停机区间。
- 部分失败时保留成功设备，不把资源池整体禁用。

主要文件：

- `core/services/scheduler/resource_pool_builder.py`
- `data/repositories/machine_downtime_repo.py`

### M4：优化器输出和 summary

职责：

- 只补合同证据，不再大拆优化器。
- 固定被拒方案的 `reason`、`origin`、attempts 压缩、fallback 输出和 bad data strict/non-strict 行为。
- 固定 `summary` 和 `result_summary` 的稳定外形，避免落库和页面继续读不稳定深层字段。

主要文件：

- `core/services/scheduler/run/schedule_optimizer.py`
- `core/services/scheduler/run/optimizer_search_state.py`
- `core/services/scheduler/summary/optimizer_public_summary.py`
- `core/services/scheduler/summary/schedule_summary.py`
- `core/services/scheduler/summary/schedule_summary_assembly.py`

### M5：落库合同

职责：

- 固定排产结果落库前的错误优先级和错误 reason。
- 固定 auto-assign 持久化条件：只在配置允许、只针对内部缺资源工序、只补空字段、不覆盖已有资源。
- 确保 `simulate=True` 不更新工序状态、不持久化自动分配资源。

主要文件：

- `core/services/scheduler/run/schedule_persistence.py`

### M6：页面展示合同

职责：

- `/scheduler/run` route 只做表单解析、调用服务、构建 view result、flash 和跳转。
- `batches_page()` 只做页面状态装配，不直接散读多个服务的深层结构。
- 页面测试只断言用户可见结果，不再绑定 service 内部 summary 形状。

主要文件：

- `web/routes/domains/scheduler/scheduler_run.py`
- `web/routes/domains/scheduler/scheduler_batches.py`

### M7：运行态、插件和 infra 支线

职责：

- 作为并行支线处理，不插进排产主链。
- 只有 `scripts/run_quality_gate.py` 或启动链专项测试实际变红，并有失败日志路径时，支线才可以前移到 PR-3 之后。
- plugin、runtime、DB、backup、transaction 这类 infra P1 必须先由 PR-0 映射清楚，不能被模糊塞进“插件支线”。

主要文件：

- `web/bootstrap/launcher.py`
- `web/bootstrap/plugins.py`

## 接口合同

### 证明合同

每个 PR 必须在说明里标明：

- 债务类型：`full-test-debt`、`complexity`、`silent_fallback`、`startup_regression`、`test_coverage`、`ui_contract` 或其他明确类型。
- 绑定事实源：台账段落、测试 nodeid、代码路径、提交证据或门禁输出。
- 是否计入 full-test-debt 减少。
- 本 PR 解除或减少了哪个登记项。
- 本 PR 没有新增未登记 full pytest 失败的证明。

只有满足下面条件，才能说“减少 full-test-debt”：

- 关闭了 active xfail 中的具体 nodeid。
- 使用仓库脚本更新台账，而不是手工改数字。
- `python tools/check_full_test_debt.py` 通过。
- `python scripts/sync_debt_ledger.py check` 通过。

不能说成“减少 full-test-debt”的情况：

- 只是降低复杂度。
- 只是减少静默回退或把退化改成可见。
- 只是补普通测试、页面合同测试或启动链专项回归。
- 只是某个 scheduler PR 变绿，但没有关闭 active xfail 的具体 `debt_id/nodeid`。

full-test-debt 的当前现场证明来自 `tools/collect_full_test_debt.py` 的输出，再由 `tools/check_full_test_debt.py` 检查。不能只看台账数字，也不能手工修改 `max_registered_xfail`。

### 排产输入合同

目标字段：

- `setup_hours`
- `unit_hours`
- `source_key`
- `ext_days`
- `ext_group_id`
- `ext_merge_mode`
- `ext_group_total_days`
- `merge_context_degraded`
- `merge_context_events`

目标行为：

- 内部工序不查模板组；外协组合并字段为空。
- 外协、无组合并组时，使用单道 `ext_days`。
- 外协、组合并组有效时，`ext_merge_mode="merged"`，使用 `ext_group_total_days`。
- 外协、模板缺失时，非 strict 记录 `template_missing` 并退回 `ext_days`。
- 外协、外部组缺失时，非 strict 记录 `external_group_missing` 并退回 `ext_days`。
- 外协、`total_days` 非法时，strict 抛 `ValidationError`；非 strict 记录 `invalid_number`，清空组合并字段并退回 `ext_days`。

实现限制：

- 优先补合同测试。
- 可以把 `_build_algo_operations_outcome()` 拆成小 helper，但不要移动隐藏缓存或扩大缓存职责，除非测试证明必须这样做。

### 冻结窗口合同

保留旧字段：

- `freeze_state`
- `freeze_applied`
- `freeze_application_status`
- `freeze_degradation_codes`
- `freeze_degradation_public_code`
- `freeze_degradation_reason`
- `freeze_degradation_count`
- `freeze_enabled`
- `freeze_days`

可新增字段：

- `freeze_disabled_reason`

建议取值：

- `config_disabled`
- `no_days`
- `no_previous_version`
- `config_degraded`
- `no_reschedulable_operations`
- `no_previous_schedule_rows`

目标行为：

- 配置关闭是 disabled，不是 degraded。
- 天数为 0 是 disabled，并说明 `no_days`。
- 没有上一版本是 disabled，并说明 `no_previous_version`。
- 配置降级是 degraded，并保留 public code。
- 上一版本加载失败记录 degradation，不产生 seed。
- 部分 seed 可用时，`freeze_application_status=partially_applied`。
- 没有可 seed 工序时，不误报为配置降级。

### 停机和资源池合同

load meta：

- `downtime_load_ok`
- `downtime_load_error`
- `downtime_partial_fail_count`
- `downtime_partial_fail_machines_sample`

extend meta：

- `downtime_extend_attempted`
- `downtime_extend_ok`
- `downtime_extend_error`
- `downtime_extend_partial_fail_count`
- `downtime_extend_partial_fail_machines_sample`

目标行为：

- 没有任何停机记录时，`downtime_load_ok=True`，`downtime_map={}`。
- 单设备加载失败时，partial fail count/sample 稳定。
- repo 初始化失败时，global failure 有 warning。
- auto-assign 关闭时，extend 不动原 map。
- auto-assign 开启且有候选设备时，候选设备的停机区间被补齐。
- 候选设备部分失败时，原有 map 不丢，成功设备保留。
- 候选设备无停机时，不新增空 key，且 `downtime_extend_ok=True`。

实现限制：

- 可以抽出 `_load_machine_intervals(dt_repo, svc, machine_id, start_str)` 一类共享 helper。
- 如果抽 helper，必须保证 load 和 extend 的告警、meta 字段、部分失败语义不变。

### 优化器合同

目标行为：

- 每个被拒方案都有稳定 `reason`，不能只靠中文 message。
- attempts 压缩不能挤掉关键 rejected diagnostics。
- fallback 仍然返回 `OptimizationOutcome`，并保留稳定 attempts 和 algo_stats。
- strict bad data 抛错字段稳定。
- non-strict bad data 进入 degradation/fallback stats，不能静默吞掉。

实现限制：

- 不做优化器大拆。
- 只补最近优化器提交的合同保护和缺口测试。

### Summary 合同

目标行为：

- service 输出给页面和落库的 summary 形状稳定。
- `result_summary` 在落库前已经是可持久化、可回放的形状。
- 页面不直接依赖优化器内部字段。

验收重点：

- `ScheduleHistory.result_summary` 写入前后字段一致。
- latest history 读取时不需要猜内部来源。
- 页面 summary display 由单一 builder 输出。

### 落库合同

错误优先级：

```text
out_of_scope_schedule_rows
> invalid_schedule_rows
> no_actionable_schedule_rows
```

目标行为：

- 只要存在 out-of-scope 行，优先抛 out-of-scope。
- 有合法行也有非法行时，抛 invalid rows。
- 没有任何可落库行时，抛 no actionable，并带上 validation_errors。
- `simulate=True` 不更新工序状态、不持久化 auto-assign。
- `auto_assign_persist=no` 不补资源。
- 外协结果不进入 internal auto-assign。
- 原工序已有 machine/operator 时不覆盖。
- 原工序缺资源且结果有资源时，只补缺失字段。

### 页面合同

`/scheduler/run` 目标 view result：

```python
@dataclass(frozen=True)
class RunScheduleViewResult:
    result_status: str
    headline_message: str
    headline_category: str
    primary_degradation_message: str | None
    secondary_degradation_messages: list[str]
    warning_messages: list[str]
    error_preview: list[str]
    error_total: int
    overdue_sample: list[str]
```

route 只做：

```text
form parsing
-> service call
-> viewmodel build
-> flash viewmodel
-> redirect
```

`batches_page()` 目标拆分：

- `_build_batches_filter_state(request)`
- `_build_batch_rows(batch_svc, status, only_ready)`
- `_build_scheduler_config_panel_state(cfg_svc, cfg)`
- `_build_latest_schedule_history_panel_state(services, cfg)`

验收重点：

- route 测试 mock `sch_svc.run_schedule()`，只断 flash 数量、类别和核心 message。
- batches 页面先不改模板，只做 viewmodel snapshot tests。

### 运行态和插件合同

runtime 目标拆分方向：

- `_read_existing_runtime_lock_state()`
- `_classify_existing_runtime_lock()`
- `_create_runtime_lock_file()`
- `_cleanup_stale_runtime_lock()`

Chrome 停机目标结构：

```python
@dataclass(frozen=True)
class StopChromeResult:
    ok: bool
    status: str
    pids: list[int]
    failed_pids: list[int]
    reason: str | None
```

插件目标合同：

- `config`
- `default`
- `mixed`
- `default_due_to_db_unavailable`
- `default_due_to_config_reader_failed`
- `default_due_to_config_read_failed`

实现限制：

- 先保留旧 wrapper，避免一次改动冲击启动链。
- 插件错误要继续脱敏展示，详细错误写日志或 degradation 事件。

## 子 feature 清单

### PR-0：事实源和债务编号映射

M0 细化和执行结果：

- 已落盘映射表：`codestable/roadmap/p1-scheduler-debt-cleanup/drafts/p1-debt-source-map.md`。
- 当前工作树里，除 `.git/` 元数据和本 roadmap 目录自引用外，未找到 P1-8 到 P1-25 的独立编号来源。
- P1-8 到 P1-25 后续只能作为本路线图整理标签；每个 PR 必须引用映射表里的当前事实源，不能只凭旧编号开修。
- PR-0/M0 是 roadmap 内部准备项，不是代码 feature；映射表和承接说明已经落盘，items.yaml 已标记为 `done`，所以后续 PR-1 可以按 CodeStable 依赖规则启动。
- M0 的 proof 只说明当前点位的债务口径检查通过，不是 clean quality gate；后续 PR 不能继承旧证明，必须在当前 HEAD 复跑自己的检查。

目标：

- 建立 P1-8 到 P1-25 的当前工作树事实源表。
- 每一项标明债务类型、代码路径、测试 nodeid、台账段落、是否纳入路线图处理、是否能计入 full-test-debt 减少。
- 产出后续 PR 的执行边界。

执行步骤：

1. 冻结搜索范围：
   - 用 `rg -uuu` 搜当前工作树和被忽略的 `.limcode/` 历史资料。
   - 排除 `.git/` 元数据和 `codestable/roadmap/p1-scheduler-debt-cleanup/` 自引用后，再判断是否有独立 P1 编号来源。
2. 建立映射表：
   - 固定路径：`codestable/roadmap/p1-scheduler-debt-cleanup/drafts/p1-debt-source-map.md`。
   - 固定字段：`old_p1`、当前归属 PR、债务类型、事实源、当前状态、是否纳入路线图处理、是否计入 full-test-debt 减少、下一步动作、证据结论。
3. 判定规则：
   - 只有代码路径、测试 nodeid、台账段落、旧计划/审查证据、门禁输出之一能直接支撑，才写“当前事实源成立”。
   - 如果编号只在本 roadmap 自引用里出现，只能写“当前工作树未找到独立编号来源”。
   - 如果没有独立编号来源，但能关联到当前代码、台账或测试事实，只能写“编号来源证据不足，当前 PR 仅处理下列事实源”。
   - 如果连关联事实也没有，写“证据不足，不得开修”。
4. full-test-debt 判定：
   - 映射表默认 `是否计入 full-test-debt 减少 = 否`。
   - 只有填了精确 `debt_id/nodeid`，并且 active xfail 数、`max_registered_xfail`、`tools/check_full_test_debt.py`、`scripts/sync_debt_ledger.py check` 都能证明减少，才允许改成“是”。
5. 回填：
   - 回填 PR-1 到 PR-9 的 notes 和头部交接说明。
   - 后续 PR 的 `old_p1` 仍保留为整理标签，但执行时必须以映射表事实源为准。

停止条件：

- 如果 `tools/check_full_test_debt.py` 或 `scripts/sync_debt_ledger.py check` 失败，先判断是 M0 文档改动导致，还是既有事实变化；不能包装成“只改文档不影响”。
- 如果 M0 需要修改 `tools/collect_full_test_debt.py`、`tools/check_full_test_debt.py`、`tools/test_debt_registry.py`、`tools/test_registry.py`、`tools/quality_gate_shared.py`、`tests/conftest.py`、`tests/main_style_regression_runner.py`、`scripts/run_quality_gate.py` 或 `scripts/sync_debt_ledger.py` 的运行逻辑，立即停止，另开修复任务。
- 如果某一项想写“计入 full-test-debt 减少”，但没有精确 `debt_id/nodeid` 和两条脚本通过结果，立即停止。
- 本路线图所有 PR 都不允许新增 `if/fallback/兜底/静默回退` 逻辑；如果实现时觉得必须新增，先停下来说明原因，不得直接改。

退出条件：

- 映射表落盘。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` 通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check` 通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-items.yaml` 通过。
- 如果某个 P1 编号找不到独立来源，明确写“当前工作树未找到独立编号来源”，不能硬编。
- 如果某个 P1 编号没有任何当前事实源，明确写“证据不足，不得开修”。

### PR-1：排产输入与外协组合并合同

承接 PR-0 已完成结果：

- PR-0 映射表已经落到 `codestable/roadmap/p1-scheduler-debt-cleanup/drafts/p1-debt-source-map.md`。
- PR-0/M0 已在 items.yaml 标记为 `done`，但 `feature` 保持 `null`，因为它是路线图内部准备项，不是一次代码 feature。
- P1-8/9/10 旧编号本身未在当前工作树找到独立来源；PR-1 只能处理映射表列出的当前事实源。
- 可处理事实源：
  - `开发文档/技术债务治理台账.md` 中 `_build_algo_operations_outcome` 复杂度登记。
  - `开发文档/技术债务治理台账.md` 中 `lookup_template_group_context_for_op` 复杂度登记。
  - `core/services/scheduler/run/schedule_input_builder.py` 的外协组合并代码事实和合同测试缺口。
- PR-1 不继承 M0 的旧 proof；开始前必须在当前 HEAD 复跑 `validate-yaml.py`、`tools/check_full_test_debt.py`、`scripts/sync_debt_ledger.py check`，并在 design/执行阶段落定自己的窄测试 nodeid。
- 禁止扩大范围：不改页面、不改落库、不处理冻结窗口、不处理停机区间、不碰 runtime/plugin、不修改门禁共享层。
- 验收用语：PR-1 默认只能写 `complexity` 或 `test_coverage` 改善；不能写 full-test-debt 减少。

目标：

- 收紧 `_build_algo_operations_outcome()`。
- 为内部工序、外协无组、外协有效组合并、模板缺失、外部组缺失、非法 total_days 建测试。

退出条件：

- 映射表中 P1-8/9/10 的当前事实源被解除、减少或确认已由近期提交解决。
- 不改页面、不改落库。
- 新增测试只围绕 input builder 和 template lookup。

### PR-2：冻结窗口 decision/meta 合同

目标：

- 固定 disabled/degraded/applied/unapplied/partially_applied 的区别。
- 视需要新增 `freeze_disabled_reason`。

退出条件：

- 映射表中 P1-14/15 的当前事实源被解除、减少或确认已由近期提交解决。
- 不删除旧 meta 字段。
- 冻结窗口测试覆盖配置关闭、天数为 0、无上一版本、配置降级、加载失败、部分 seed、无可 seed 工序。

### PR-3：停机区间与自动分配资源池合同

目标：

- 固定 downtime load 和 extend 的 meta 字段。
- 确保候选设备停机区间被补齐。
- 部分失败不丢成功设备。

退出条件：

- 映射表中 P1-16/17 的当前事实源被解除、减少或确认已由近期提交解决。
- 不改算法主逻辑。
- 自动分配关闭、开启、部分失败、无停机记录均有测试。

### PR-4：优化器结果合同补证

目标：

- 保护近期优化器提交。
- 固定 rejected reason、attempts compact、fallback outcome、strict bad data 合同。

退出条件：

- 只补测试和少量字段标准化。
- 不重新拆优化器。
- 如果事实源显示优化器债务已经关闭，把结果回填到 PR-0 映射表，不做无意义改动。

### PR-5：summary/result_summary 合同

目标：

- 固定 service summary 和历史 `result_summary` 的可持久化形状。
- 让落库和页面都吃同一层稳定输出。

退出条件：

- 最新 history 的 summary 读取不再依赖内部临时字段。
- summary display builder 有窄测试。
- 落库前后 `result_summary` 字段一致。

### PR-6：落库校验与 auto-assign persist

目标：

- 拆小 `build_validated_schedule_payload()`。
- 固定错误优先级和 auto-assign 持久化条件。

退出条件：

- 映射表中 P1-11/12/13 的当前事实源被解除、减少或确认已由近期提交解决。
- `simulate=True`、`auto_assign_persist=no`、外协结果、已有资源不覆盖、缺资源只补缺失字段都有测试。

### PR-7：/scheduler/run ViewResult

目标：

- route 不再直接解释 summary 深层字段。
- 建立 `RunScheduleViewResult`。

退出条件：

- 映射表中 P1-18 的当前事实源被解除、减少或确认已由近期提交解决。
- route 测试只 mock service，断用户可见 flash。
- 页面没有因为 service 内部字段调整而反复返工。

### PR-8：batches_page() viewmodel

目标：

- 拆出页面筛选、批次行、配置面板、最新历史面板状态构建。
- 保持模板尽量不变，先稳定 viewmodel。

退出条件：

- 映射表中 P1-19 的当前事实源被解除、减少或确认已由近期提交解决。
- 默认 status、空 status、only_ready、config degraded、latest history 缺失、latest summary parse failed、latest algo config snapshot 均有 snapshot tests。

### PR-9：runtime/plugin/infra 支线

目标：

- 处理映射表中 P1-20 到 P1-24 对应的 runtime/plugin/infra 事实源。
- P1-25 当前工作树证据不足，不得直接开修；需要先补具体路径、台账条目或测试 nodeid。
- 只有启动链专项测试或 `scripts/run_quality_gate.py` 实际变红，并有失败日志路径时，PR-9 才可以前移到 PR-3 后面。

退出条件：

- 不插队排产主链，除非门禁或启动链专项测试明确变红并有失败日志。
- runtime lock、Chrome 停机、插件 enabled source、插件 degradation 有专项测试。
- infra 类 P1 不被模糊塞进 plugin，需要单独标出事实源和退出条件。

## 排期建议

最小闭环是 PR-0。没有 PR-0，后面每个 PR 都可能把“测试覆盖”“复杂度减少”“full-test-debt 减少”混在一起说，最后会让验收失真。

PR-0 映射表落盘并通过证明检查后，排产主链按 PR-1 到 PR-8 顺序推进。PR-9 是支线，默认不插队；只有启动链专项测试或统一门禁实际变红并有失败日志路径，才把 PR-9 前移。

每个 PR 收尾时都要做三件事：

- 更新或确认对应 P1 映射项状态。
- 运行与本 PR 有关的窄测试。
- 运行 full-test-debt 和台账同步检查；最终合并前运行统一质量门禁。

## 验收口径

单个 PR 的最低验收：

- 对应 P1 登记项或当前事实源被减少、解除、明确证明近期提交已解决，或标为证据不足不得开修。
- 没有新增未登记 full pytest 失败。
- 没有新增 active xfail。
- 没有新增 `if/fallback/兜底/静默回退` 逻辑；如果实现时确实需要，必须先停下来说明原因。
- `python tools/check_full_test_debt.py` 通过。
- `python scripts/sync_debt_ledger.py check` 通过。
- 与改动相关的窄测试通过。

阶段性合并前验收：

- `python scripts/run_quality_gate.py` 通过。
- 如果准备合并回主分支，最终再跑 `python scripts/run_quality_gate.py --require-clean-worktree`。

## 风险和观察项

- P1-8 到 P1-25 的文字编号除本 roadmap 目录自引用外，在当前工作树里没有独立命中。后续 PR 必须先看 `drafts/p1-debt-source-map.md`，不能只凭 old_p1 标签开修。
- 当前 active full-test-debt 只有 5 个 operator-machine 查询 xfail。排产 PR 多数更可能减少 complexity、silent fallback、测试覆盖缺口或专项回归风险，而不是直接减少 full-test-debt。
- 优化器相关合同已有近期提交支撑。PR-4 的默认动作是补证，不是改造。
- PR-4/PR-5 路径已按当前代码修正为 `core/services/scheduler/summary/optimizer_public_summary.py`、`schedule_summary.py` 和 `schedule_summary_assembly.py`，不再引用不存在的 `run/optimizer_public_summary.py` 或 `run/schedule_core.py`。
- P1-25 当前证据不足。除非后续补出具体路径、台账条目或测试 nodeid，否则不得直接进入修复。
- 冻结窗口不一定需要新公开 DTO。是否引入内部 decision 对象，以测试和代码简化程度为准。
- 停机区间 helper 也不是强制动作。只有当 load 和 extend 的解析规则确实重复或漂移时，才抽 helper。
- 落库的 `no_actionable` 与 `invalid_schedule_rows` 边界必须由测试写清楚，避免以后又靠中文文案判断。

## 变更记录

- 2026-04-28：根据最新 main、README 质量门禁口径、技术债务台账、排产主链代码核实结果，以及两轮子代理审查，建立本路线图。
- 2026-04-28：细化并执行 M0，落盘 `drafts/p1-debt-source-map.md`；明确 P1-8 到 P1-25 除本 roadmap 自引用外未找到独立编号来源，后续 PR 只能按映射表里的当前事实源执行；补齐 items.yaml 的 `description` 和 `feature: null`；修正 PR-4/PR-5 的过期 summary 路径。
- 2026-04-28：复核 M0 后补硬执行口径：PR-0/M0 作为 roadmap 内部准备项标记为 `done`，P1 搜索证明排除 `.git/` 元数据，M0 proof 明确不是 clean quality gate，并把“不新增 if/fallback/兜底/静默回退逻辑”写成全局停止条件。

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
- M0 当时 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` 已通过，结果为 `active_xfail_count=5`、`collected_count=700`、`unexpected_failure_count=0`。
- M3 二次 review 后复核 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` 已通过，结果为 `active_xfail_count=5`、`collected_count=744`、`unexpected_failure_count=0`。
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

M1 已完成的收口：

- 已新增 `tests/test_schedule_input_builder_external_merge_contract.py`，直接覆盖内部工序不查模板、外协无组、`separate`、有效 `merged`、模板缺失、外部组缺失、非法 `total_days` 的 strict/non-strict 行为。
- 已新增 `tests/test_schedule_template_lookup_contract.py`，固定模板缺失、无 `ext_group_id`、外部组缺失、`merged`/`separate`、缓存命中和 strict fail fast。
- 已新增 `tests/test_schedule_service_input_merge_context_contract.py`，让 `ScheduleService.run_schedule()` 真走 collector 和 input builder，再进入 summary，证明 `merge_context_degraded` 不会被混成普通 `input_fallback`。
- 已把 `schedule_input_builder.py` 和 `schedule_template_lookup.py` 中原本堆在入口里的判断搬到小 helper；没有改 `build_algo_operations(..., strict_mode, return_outcome)` 签名，没有改 `OpForScheduleAlgo` 字段，没有改事件 code/field 的基本形状。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把 `_build_algo_operations_outcome` 和 `lookup_template_group_context_for_op` 两条复杂度登记从台账受控结构块移除；这是 complexity 债务关闭，不是 full-test-debt 减少。
- `core/services/scheduler/run/schedule_input_contracts.py` 仍只读参照，本轮没有修改 collector 合同层。
- 本轮没有改页面、落库、冻结窗口、停机区间、runtime/plugin 或质量门禁工具。

### M2：冻结窗口

职责：

- 把“配置关闭、天数为 0、没有上一版本、配置降级、没有可 seed 工序、上一版本加载失败”这些状态讲清楚。
- 保留旧 meta 字段，不破坏现有页面和历史解释。
- 可以新增 `freeze_disabled_reason`，但不强制引入对外 DTO；如果引入内部 decision 对象，也只作为实现收口。

M2 执行前细化：

- 根因不是调用链丢字段，而是 `build_freeze_window_seed()` 里多个早退分支都只写 `freeze_state="disabled"`，没有说明到底是用户关闭、天数为 0、没有上一版本、没有可 seed 工序，还是上一版本没有可用行。
- `freeze_window_enabled` 自身读取降级时，配置快照已经会留下 `degradation_events`；M2 必须把这个事件识别为冻结窗口 `degraded`，不能把它误当成用户手动关闭。
- 新增可选字段 `freeze_disabled_reason`，固定取值为 `config_disabled`、`no_days`、`no_previous_version`、`no_reschedulable_operations`、`no_previous_schedule_rows`、`config_degraded`。
- 旧字段 `freeze_state`、`freeze_applied`、`freeze_application_status`、`freeze_degradation_codes`、`freeze_degradation_public_code`、`freeze_degradation_reason`、`freeze_degradation_count`、`freeze_enabled`、`freeze_days` 必须继续保留。
- `disabled` 表示正常不启用冻结窗口，不记 degraded、不加 warning；`degraded` 只表示本来应该应用冻结窗口，但配置或上一版本种子事实源不可用。
- 本次不新增 fallback、不新增静默吞错、不把冻结窗口问题混进 `input_fallback` 或 `config_fallback`。如果实现时发现还要增加特殊分支，先停下来说明原因。

M2 执行完成回填：

- 已在冻结窗口内部 meta 写入 `freeze_disabled_reason`，把配置关闭、天数为 0、没有上一版本、没有可 seed 工序、上一版本没有可用行分开记录；这些仍然都是正常 `disabled`，不会被写成失败。
- 已把 `freeze_window_enabled` / `freeze_window_days` 的配置读取降级接入冻结窗口判断；配置坏了时状态是 `degraded`，strict 模式继续 fail closed，不会被误当成用户手动关闭。
- 已保留全部旧 meta 字段；summary 只在 `freeze_state="disabled"` 时透传安全原因字段，`config_degraded` 仍走降级字段表达，不把内部错误原文、路径或数据库异常暴露给页面和历史解释。
- 已补冻结窗口和 summary 合同测试，覆盖配置关闭、天数为 0、没有上一版本、没有可 seed、上一版本无行、成功应用、配置降级 relaxed/strict、缺前缀 strict、坏时间 strict，以及旧 warning 兼容不扩大。
- 复审后修掉了一处下游语义风险：配置降级不再以 `freeze_disabled_reason` 暴露到 `result_summary.algo.freeze_window`，避免页面或历史 JSON 把 degraded 误读成 disabled。
- 二次审查后又补修了分析页展示问题：页面现在以 `freeze_state` 为主事实，`enabled=no + freeze_state=degraded` 会显示“已降级”，不会被显示成普通“未启用”。
- 已补录 CodeStable feature 承接：`codestable/features/2026-04-28-freeze-window-disabled-contract/`，并把 items.yaml 的 M2 条目指向该 feature。
- 已同步 `drafts/p1-debt-source-map.md`：P1-15 从 `needs-recheck` 改为 `evidence-locked-by-M2`；后续搜索旧 P1 编号时排除 `codestable/**`，避免被本次补录文档自引用污染。
- 本轮没有新增 fallback、没有新增静默兜底，也没有把冻结窗口问题混进 `input_fallback` 或 `config_fallback`。
- P1-14 没关闭：`build_freeze_window_seed` 当前复杂度是 26，阈值是 15，所以没有运行台账自动刷新移除复杂度登记。P1-15 的冻结窗口状态合同已由本轮测试补证，但它不是 full-test-debt 减少。
- `tools/check_full_test_debt.py` 仍显示 active xfail 为 5 条，集中在 operator-machine/query service 旧登记，本轮没有减少 full-test-debt。

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
- 固定被拒方案的稳定诊断口径、`origin`、attempts 压缩、已有 `state.best is None` 输出外形和 bad data strict/non-strict 行为。
- 固定 `summary` 和 `result_summary` 的稳定外形，避免落库和页面继续读不稳定深层字段。

主要文件：

- `core/services/scheduler/run/schedule_optimizer.py`
- `core/services/scheduler/run/optimizer_search_state.py`
- `core/services/scheduler/summary/optimizer_public_summary.py`
- `core/services/scheduler/summary/schedule_summary.py`
- `core/services/scheduler/summary/schedule_summary_assembly.py`

M4 执行前细化：

- M4 按完整模块执行，但内部拆成两个可验段落：PR-4 只锁优化器结果合同，PR-5 再锁 `summary/result_summary`、落库历史和页面读取。两段都完成后，才算 M4 完整收口。
- PR-4 不默认新增独立 `reason` 字段；稳定原因先按现有 `origin.type`、`origin.field` 和补充用的 `origin.message` 固定。若红灯证明必须新增字段，先停下来说明，因为这会改变公共诊断形状。
- PR-4 只证明已有统计和诊断可见，并验证已有 `state.best is None` 路径的输出外形；不新增新的 fallback 行为，也不在 summary 或页面层补二次兜底。
- PR-5 以 PR-4 的优化器输出为输入，证明 `result_summary.algo.attempts` 只放页面可展示字段，`diagnostics.optimizer.attempts` 可以随历史 JSON 落库但不被页面展示。
- M4 不减少 full-test-debt，除非实际关闭 active xfail 中的精确 `debt_id/nodeid`，并通过 `tools/check_full_test_debt.py` 与 `scripts/sync_debt_ledger.py check`。
- 本轮不改冻结窗口、停机资源池、落库业务规则、runtime/plugin 或质量门禁工具运行逻辑；如果测试逼出这些范围外问题，先回路线图更新，不在 feature 里偷改。

### M5：落库合同

职责：

- 固定排产结果落库前的错误优先级和错误 reason。
- 固定 auto-assign 持久化条件：只在配置允许、只针对内部缺资源工序、只补空字段、不覆盖已有资源。
- 确保 `simulate=True` 不更新工序状态、不持久化自动分配资源。

主要文件：

- `core/services/scheduler/run/schedule_persistence.py`

M5 执行前细化：

- M5 对应 items.yaml 的 PR-6：`schedule-persistence-auto-assign-contract`，只处理 `core/services/scheduler/run/schedule_persistence.py` 和对应合同测试。
- 当前没有确认出必须立刻改业务逻辑的功能 bug；根因是 `build_validated_schedule_payload()` 复杂度登记仍打开，且错误优先级、simulate、auto-assign 写回条件缺少 PR-6 专项测试。
- 本轮代码改动只允许把 `build_validated_schedule_payload()` 的既有判断原样搬到私有 helper；错误文案、`reason`、`details`、优先级、source 判定和 `assigned_by_op_id` 形状必须保持不变。
- 本轮不新增“写自动分配资源前重读数据库工序”的特殊检查；旧对象覆盖风险只作为观察项记录，后续如需治理另开任务。
- 本轮不改 summary、result_summary、schema、页面、route、viewmodel、repo、质量门禁脚本、full-test-debt 脚本和台账脚本运行逻辑。
- 如果红灯测试或静态检查证明必须新增业务 `if`、fallback、兜底、宽泛默认值、宽泛 `try/except`、新 reason 或新 details，立即停线说明，不直接实现。
- PR-6 不减少 full-test-debt；P1-11 只有复杂度登记真的被受控脚本移除后才能写 fixed，P1-12/P1-13 只能写 test_coverage 证据锁定。

M5 执行完成回填：

- 已新增 PR-6 专项测试，覆盖错误优先级、simulate 不改真实状态和资源、`auto_assign_persist=no`、外协隔离、已有资源不覆盖、只补空字段和 missing set 门控。
- 已把 `build_validated_schedule_payload()` 的既有判断原样搬到私有 helper；错误文案、`reason`、`details`、优先级、source 判定和 `assigned_by_op_id` 形状保持不变。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 后，高复杂度登记从 40 降到 39，P1-11 对应复杂度登记已移除。
- 本轮没有新增写前重读数据库工序的特殊检查；旧对象覆盖风险作为观察项保留。
- 本轮没有改 summary、result_summary、schema、页面、route、viewmodel、repo、质量门禁脚本、full-test-debt 脚本或台账脚本运行逻辑。
- `tools/check_full_test_debt.py` 仍显示 active xfail 为 5 条 operator-machine/query service 旧登记，`collected_count=748`，本轮不写 full-test-debt 减少。

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

- 每个被拒方案都有稳定诊断口径：`source="candidate_rejected"`、`origin.type`、`origin.field` 必须保留，`origin.message` 只作为排障补充，不作为唯一合同。
- attempts 压缩不能挤掉关键 rejected diagnostics。
- 已有 `state.best is None` 路径仍然返回真实 `OptimizationOutcome`，并保留稳定 attempts 和 algo_stats。
- strict bad data 抛错字段稳定。
- non-strict bad data 只记录允许跳过的候选，不能静默改成成功。

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

M1 执行结果：

- P1-8 已关闭：`_build_algo_operations_outcome` 的复杂度登记已由台账同步脚本移除。
- P1-9 已关闭：`lookup_template_group_context_for_op` 的复杂度登记已由台账同步脚本移除。
- P1-10 已补证：外协组合并行为已有 builder、lookup、service-summary 三层窄测试锁住，但它本来不是 full-test-debt 或复杂度登记项，所以写作“测试覆盖补齐”，不写作“债务登记关闭”。
- 已复跑 `tools/check_full_test_debt.py`，active xfail 仍是 5 条 operator-machine/personnel 相关登记；本 PR 不减少 full-test-debt。
- 已复跑 `scripts/sync_debt_ledger.py check`，台账结构和自动字段通过检查。
- 已复跑新增测试、排产输入 collector/summary 相关测试、外协 merged 回归、greedy 合同、架构体检、ruff 和 diff 空白检查。
- 已在干净工作区复跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`，完整质量门禁通过。

### PR-2：冻结窗口 decision/meta 合同

承接 PR-1 / M1 已完成结果：

- M1 已完成排产输入与外协组合并合同收口，P1-8/P1-9 两条复杂度登记已关闭，P1-10 的外协组合并测试覆盖已补齐。
- M1 没有改冻结窗口、停机区间、落库、页面、runtime/plugin 或质量门禁工具；PR-2 必须从冻结窗口当前代码和当前测试重新核实，不能继承 M1 的测试结论当作冻结窗口 proof。
- M1 的 full-test-debt 结论只能说明“本轮没有减少 full-test-debt，active xfail 仍是 operator-machine/personnel 相关”；PR-2 如果要写任何债务减少，也必须用自己的 `tools/check_full_test_debt.py`、`scripts/sync_debt_ledger.py check` 和目标测试重新证明。
- PR-2 仍以 `core/services/scheduler/run/freeze_window.py` 为主，不借 M1 的外协组合并 helper 扩大范围。

目标：

- 固定 disabled/degraded/applied/unapplied/partially_applied 的区别。
- 视需要新增 `freeze_disabled_reason`。
- 只把 `freeze_disabled_reason` 作为安全原因字段透传到 `result_summary.algo.freeze_window`，不暴露异常原文、路径或数据库错误。

执行计划：

1. 在现有 disabled 早退出口写明原因：配置关闭、天数为 0、无上一版本、无可 seed 工序、上一版本无排程行。
2. 在判断普通关闭前，先检查冻结窗口相关配置降级事件，覆盖 `freeze_window_enabled`、`freeze_window_days` 和 `freeze_seed_unavailable`。
3. 保持 strict 行为：进入 `degraded` 时 `strict_mode=True` 继续抛 `ValidationError(field="freeze_window")`；普通 disabled 不抛。
4. 补冻结窗口窄测试，覆盖配置关闭、天数为 0、无上一版本、无可 seed、上一版本无行、成功 applied、配置降级 relaxed/strict、缺前缀 strict、坏时间 strict。
5. 补 summary 测试，确认 `freeze_disabled_reason` 可安全透传，旧字段仍兼容，旧 warning 兼容口不扩大。

执行结果：

- 已完成 `freeze_disabled_reason` 内部 meta 写入，普通 disabled 分成 `config_disabled`、`no_days`、`no_previous_version`、`no_reschedulable_operations`、`no_previous_schedule_rows`。
- 已把 `freeze_window_enabled` / `freeze_window_days` 配置读取降级识别为冻结窗口 `degraded`；strict 模式继续抛 `ValidationError(field="freeze_window")`，普通 disabled 不抛。
- 已把 summary 输出收窄为“只在 `freeze_state="disabled"` 时透传 `freeze_disabled_reason`”；配置降级继续通过降级 code/reason/count 表达，避免页面和历史解释误读。
- 已补 `tests/regression_freeze_window_fail_closed_contract.py` 与 `tests/regression_schedule_summary_freeze_state_contract.py`，并复跑冻结窗口、summary/config 下游、复杂度体检、ruff、pyright、full-test-debt、台账检查和 yaml 校验。
- 已请 4 个 subagent 做只读复审：冻结窗口合同、summary/页面/落库下游、无新增 fallback 对抗、roadmap/items/提交边界。复审提出的 degraded 公开字段风险和 strict 无上一版本行覆盖缺口已修复并复跑。
- Review finding 修复补充：分析页现在以 `freeze_state` 展示冻结窗口状态，`enabled=no + freeze_state=degraded` 不再显示成普通未启用；已补真实页面渲染测试。
- CodeStable 承接补充：已补录 `2026-04-28-freeze-window-disabled-contract` feature 三件套，items.yaml 已指向该 feature，source-map 已同步 P1-15 为 `evidence-locked-by-M2`。
- P1-14 当前不关闭：`build_freeze_window_seed` 复杂度仍为 26，高于阈值 15；未运行台账自动刷新移除该登记。P1-15 的状态合同已补测试锁住，但不写成 full-test-debt 减少。
- `tools/check_full_test_debt.py` 仍为 5 条 active xfail，集中在 operator-machine/query service 旧登记；本 PR 不减少 full-test-debt。

退出条件：

- 映射表中 P1-14/15 的当前事实源被解除、减少或确认已由近期提交解决。
- 不删除旧 meta 字段。
- 冻结窗口测试覆盖配置关闭、天数为 0、无上一版本、配置降级、加载失败、部分 seed、无可 seed 工序。

### PR-3：停机区间与自动分配资源池合同

承接 PR-2 / M2 已完成结果：

- 冻结窗口状态合同已经收口，下一步只处理停机区间和自动分配资源池，不继承 M2 的冻结窗口 proof 当作停机 proof。
- 二次审查发现的 M2 尾巴也已补齐：分析页降级展示已修正，M2 feature 承接已补录，P1-15 source-map 已同步。PR-3 仍不能继承这些 proof 当作停机或资源池 proof。
- M2 没有减少 full-test-debt，active xfail 仍是 5 条 operator-machine/query service 旧登记；PR-3 如果要声明债务变化，必须用自己的测试和台账检查重新证明。
- M2 没有关闭 P1-14 复杂度登记，说明 PR-3 不能把“冻结窗口复杂度未降”当作自己范围内的问题处理；PR-3 只从 `resource_pool_builder.py` 和 `machine_downtime_repo.py` 的当前事实源出发。

M3 细化计划：

- 已由多个只读 subagent 核实：M3 只能绑定 P1-16 / P1-17，不继承 M1/M2 proof，不碰冻结窗口、优化器、落库、页面、runtime/plugin。
- 当前代码已经有一部分 load/extend meta 和部分失败保留成功设备行为；本轮不能把已有行为包装成 bug，只能用新增测试证明缺口、补证或降复杂度。
- 根因是 `downtime_map={}` 本身分不清“真没停机”还是“加载失败后为空”，必须靠明确 meta 和 summary 投影说明；同时 load/extend 重复了“查停机、整理区间、记录失败设备”的流程。
- 本轮候选设备口径采用资源池宽口径：`operators_by_machine` 中有可用人员关系的设备；不进入逐工序精确候选和算法排序。
- 实现限制：不新增业务 `if`、fallback、兜底或静默吞错；如必须加特殊处理，先停下来说明原因。

执行步骤：

1. 建立 `2026-04-28-downtime-resource-pool-contract` feature 承接，items.yaml 改为 `in-progress`。
2. 补 `resource_pool_builder`、`MachineDowntimeRepository.list_active_after`、真实 DB collector 三类窄测试。
3. 只在 `resource_pool_builder.py` 内部抽小 helper 收口重复读取逻辑，保持字段和值不变。
4. 如果复杂度降到阈值内，用受控脚本刷新技术债务台账；只写 complexity 改善，不写 full-test-debt 减少。
5. 跑目标验证、债务脚本、yaml 校验和 clean gate；执行后再请 subagent 做停机/资源池合同、无新增兜底、下游影响、测试债务四路复审。
6. 验收通过后写 acceptance，M3 标 done，source-map 回填 P1-16/P1-17，PR-4 头部写清 M3 已做内容和不能继承的证明边界。

执行结果：

- 已完成 CodeStable feature 承接：`codestable/features/2026-04-28-downtime-resource-pool-contract/`，并把 items.yaml 的 M3 条目改为 done。
- 已新增停机和资源池窄测试：停机读取成功、无记录、整体失败、单设备失败保留健康设备、逐设备查询全部失败按 partial 暴露；资源池候选设备补停机、无停机不加空 key、部分失败保留成功设备、extend 查询前整体失败保留原 map；`MachineDowntimeRepository.list_active_after()` 真实查询覆盖跨过排产开始时间的停机记录；collector 真实 DB 链路。
- 已把 `load_machine_downtimes` 和 `extend_downtime_map_for_resource_pool` 里重复的停机查询、时间段整理、失败设备记录和 meta/sample 写入收口到内部 helper；公开字段、warning 口径和 summary 投影保持不变。
- 复杂度已回到阈值内：`load_machine_downtimes` 从 21 降到 5，`extend_downtime_map_for_resource_pool` 从 21 降到 8；`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 后高复杂度登记从 42 降到 40。
- 已请 4 个只读 subagent 做执行后复审，又按 review findings 请 5 个子代理深挖根因。复审指出的跨开始时间查询、逐设备查询全失败、extend 整体失败、full-test-debt 精确数字和 source-map 行号漂移问题，已用测试和文档修正；没有改业务实现，也没有新增 fallback/兜底。
- 本轮没有改冻结窗口、优化器主逻辑、落库、页面、runtime/plugin 或质量门禁工具；没有新增 fallback、兜底、静默吞错，也没有改变资源池候选设备的宽口径。
- P1-16/P1-17 已按 complexity/test_coverage 关闭；二次 review 后 `tools/check_full_test_debt.py` 通过，active xfail 仍为 5 条 operator-machine/query service 旧登记，`collected_count=744`，所以本轮不写 full-test-debt 减少。

目标：

- 固定 downtime load 和 extend 的 meta 字段。
- 确保候选设备停机区间被补齐。
- 部分失败不丢成功设备。

退出条件：

- 映射表中 P1-16/17 的当前事实源被解除、减少或确认已由近期提交解决。
- 不改算法主逻辑。
- 自动分配关闭、开启、部分失败、无停机记录均有测试。

### PR-4：优化器结果合同补证

承接 PR-3 / M3 已完成结果：

- M3 已完成停机区间读取和自动分配资源池候选设备补停机合同；二次 review 后补齐跨开始时间停机查询、逐设备查询全失败 partial 口径、extend 整体失败保留原 map 三个边界测试，load/extend 的公开 meta 字段和 summary 投影保持稳定。
- M3 已关闭 P1-16/P1-17 当前复杂度事实源，并补齐普通测试证据；这只能证明停机和资源池合同，不等于优化器输出合同已经稳定。
- M3 没有减少 full-test-debt，二次 review 后 active xfail 仍为 5 条 operator-machine/query service 旧登记，`collected_count=744`；PR-4 若要声明债务变化，必须用自己的测试和债务脚本重新证明。
- PR-4 不要继承 M3 的停机 proof 当作优化器 proof，也不要顺手改资源池候选口径、停机读取或页面展示；只处理优化器结果、attempts、rejected 诊断口径、已有 `state.best is None` 输出外形和 bad data strict/non-strict 证据。

目标：

- 保护近期优化器提交。
- 固定 rejected 诊断口径、attempts compact、已有 `state.best is None` 输出外形、strict bad data 合同。

退出条件：

- 只补测试和必要的诊断标准化；不新增独立 reason 字段，除非先停下说明并确认。
- 不重新拆优化器。
- 如果事实源显示优化器债务已经关闭，把结果回填到 PR-0 映射表，不做无意义改动。

PR-4 执行计划：

1. 创建 `codestable/features/2026-04-28-optimizer-result-contract-evidence/` feature 三件套，items.yaml 改为 `in-progress`。
2. 先补红灯测试，覆盖 `12` 条 scored attempt 加 `1` 条 rejected attempt 进入 `build_result_summary` 后，公开 attempts 保留 `11` 条，rejected 留在 `diagnostics.optimizer.attempts`，并保留 `origin.type/field/message` 且没有假 `score`。
3. 补已有 `state.best is None` 路径测试，覆盖该旧路径仍返回稳定 `OptimizationOutcome`，并断言 `summary`、`used_strategy`、`used_params`、`best_score`、`best_order`、`algo_stats`、`attempts` 外形。
4. 复跑 optimizer attempts、local search、multi-start/OR-Tools strict、public summary projection、cfg snapshot、seed boundary 和 runtime seam 相关测试。
5. 请 subagent 复审优化器链路、测试缺口和无新增兜底；若复审指出真实问题，先修再验收。
6. 写 acceptance，PR-4 checklist 的 checks 按真实结果标 `passed/failed`，PR-4 items 标 done，并在 PR-5 头部写清 PR-4 已证明和不能替 PR-5 证明的边界。

PR-4 执行结果：

- 已创建并验收 `codestable/features/2026-04-28-optimizer-result-contract-evidence/`，checklist 全部完成，acceptance 已写入。
- 已新增 rejected 诊断穿过 attempts 压缩和 summary 投影后的分层测试：公开 attempts 只保留 11 条普通记录，不出现 `source`、`tag`、`used_params`、`algo_stats`、`origin`；rejected 记录留在 `diagnostics.optimizer.attempts`，保留 `origin.type/field/message`，且没有假 `score`。
- 已加严已有 `state.best is None` 路径外形测试，确认仍返回真实 `OptimizationOutcome`，并固定 `summary`、`used_strategy`、`used_params`、`best_score`、`best_order`、`algo_stats`、`attempts`。
- 已按 subagent 复审把 `optimizer_attempt_records.py`、`schedule_optimizer_steps.py`、`optimizer_local_search.py` 纳入 PR-4 文件边界和静态检查；本轮没有改这些运行文件。
- 已通过 PR-4 目标测试、ruff、pyright、full-test-debt、台账检查、yaml 校验和 `git diff --check`。full-test-debt 仍是 5 条 active xfail，`collected_count=744`，不声明减少。
- 本轮没有新增独立 `reason` 字段，没有新增 `if`、fallback、兜底、静默吞错或宽泛默认值逻辑，也没有改 summary、页面、落库、冻结窗口、停机资源池、runtime/plugin 或质量门禁工具运行逻辑。

### PR-5：summary/result_summary 合同

承接 PR-4 / M4 优化器半段已完成结果：

- PR-4 已经证明：被拒候选只作为诊断保留，attempts 压缩不会把关键 rejected diagnostics 挤掉，已有 `state.best is None` 路径仍返回稳定 `OptimizationOutcome`，strict 候选坏数据直接抛错，non-strict 只记录允许跳过的候选。
- PR-4 的证明只覆盖优化器输出，不等于 `summary/result_summary` 落库、历史读取和页面展示已经稳定。
- PR-5 必须自己证明：`result_summary` 写入前后的公开形状一致，页面不展示 `diagnostics.optimizer.attempts` 里的内部排障词，latest history 读取不需要猜优化器内部来源。
- PR-5 仍要重新跑自己的 full-test-debt 和台账检查；不能继承 PR-4 proof 当作 summary proof。

目标：

- 固定 service summary 和历史 `result_summary` 的可持久化形状。
- 让落库和页面都吃同一层稳定输出。

退出条件：

- 最新 history 的 summary 读取不再依赖内部临时字段。
- summary display builder 有窄测试。
- 落库前后 `result_summary` 字段一致。

PR-5 执行计划：

1. 创建 `codestable/features/2026-04-28-scheduler-summary-result-summary-contract/` feature 三件套，items.yaml 改为 `in-progress`。
2. 补 summary/落库测试，走 `build_result_summary -> persist_schedule -> ScheduleHistory` 读回，确认公开 `algo.attempts` 不含 `source`、`tag`、`used_params`、`algo_stats`、`origin`，诊断只在 `diagnostics.optimizer.attempts`。
3. 补页面泄漏测试，构造带 `INTERNAL_OPTIMIZER_SECRET` 的 diagnostics，确认分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页响应不显示这个内部词。
4. 复跑 summary projection、size guard、service 透传 algo_stats、history/analysis/batches/week-plan/reports 页面合同和 full-test-debt/台账/yaml 检查。
5. 请 subagent 复审落库/页面/历史读取、内部诊断不外泄、M5/PR-6 头部承接；若复审指出真实问题，先修再验收。
6. 写 acceptance，PR-5 checklist 的 checks 按真实结果标 `passed/failed`，PR-5 items 标 done，并在 PR-6 头部写清完整 M4 已完成内容和不能继承的 proof 边界。

PR-5 执行结果：

- 已创建并验收 `codestable/features/2026-04-28-scheduler-summary-result-summary-contract/`，checklist 全部完成，acceptance 已写入。
- 已新增真实落库读回测试，走 `build_result_summary -> persist_schedule -> ScheduleHistoryRepository.get_by_version -> json.loads`，确认公开 `algo.attempts` 全量不含 `candidate_rejected`、`source`、`tag`、`used_params`、`algo_stats`、`origin`。
- 已确认 `diagnostics.optimizer.attempts` 在正常大小下随历史 JSON 落库并读回，rejected 诊断保留 `origin.type/field/message`；这只代表正常大小 summary，不代表超大 summary 必须保留 diagnostics，size guard 仍可截断并标记。
- 已新增真实页面和接口响应不泄漏测试：把 `INTERNAL_OPTIMIZER_SECRET` 放进内部 diagnostics，访问分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页，这些响应均不展示这个内部词。
- 已通过 PR-5 目标测试、页面合同测试、ruff、pyright、full-test-debt、台账检查、yaml 校验和 `git diff --check`。full-test-debt 仍是 5 条 active xfail，`collected_count=744`，不声明减少。
- 完整 M4 收口后已在干净工作区复跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`，最终质量门禁通过。
- 本轮没有改运行代码，没有改 `summary_schema_version=1.2`，没有改 `OptimizationOutcome` 字段，没有新增 `if`、fallback、兜底、静默吞错或宽泛默认值逻辑，也没有在模板、route 或 viewmodel 里补二次过滤。

### PR-6：落库校验与 auto-assign persist

PR-6 头部承接 M4 完整完成结果：

- M4 已拆成 PR-4 和 PR-5 完成：PR-4 固定优化器输出、rejected 诊断、attempts 压缩和已有 `state.best is None` 路径外形；PR-5 固定 summary/result_summary 写入历史、读回和页面展示边界。
- M4 只补测试和 CodeStable 追踪文档，没有改运行代码；没有新增独立 `reason` 字段，没有改 `summary_schema_version=1.2`，没有改 `OptimizationOutcome` 字段，没有新增 `if`、fallback、兜底、静默吞错或宽泛默认值逻辑。
- M4 不减少 full-test-debt，active xfail 仍是 5 条 operator-machine/query service 旧登记，`collected_count=744`。
- M4 已在干净工作区通过最终质量门禁后交接给 PR-6。
- PR-6 可以承接 M4 已证明的稳定 summary 输入，但不能把 M4 的 proof 当成落库校验和 auto-assign persist 已完成。PR-6 仍要自己证明 `build_validated_schedule_payload()` 错误优先级、simulate 不写状态、不持久化自动分配资源，以及 auto-assign persist 只补空资源且不覆盖已有资源。

目标：

- 拆小 `build_validated_schedule_payload()`。
- 固定错误优先级和 auto-assign 持久化条件。

退出条件：

- 映射表中 P1-11/12/13 的当前事实源被解除、减少或确认已由近期提交解决。
- `simulate=True`、`auto_assign_persist=no`、外协结果、已有资源不覆盖、缺资源只补缺失字段都有测试。

PR-6 执行计划：

1. 建立 `codestable/features/2026-04-28-schedule-persistence-auto-assign-contract/`，把 PR-6 design/checklist 与 roadmap item 互相指向，items.yaml 进入 `in-progress`。
2. 新增 PR-6 专项测试，覆盖 out-of-scope 与 invalid 同时出现、全部非法但无可落库行、simulate 不改真实状态和资源、`auto_assign_persist=no`、外协隔离、已有资源不覆盖、只补空字段和 missing set 门控。
3. 只在 `schedule_persistence.py` 内原样搬移 `build_validated_schedule_payload()` 现有判断到私有 helper；不改 reason/details/优先级，不加新兜底。
4. 复跑 PR-6 窄测试、现有落库/服务回归、PR-5 下游页面/报表读取回归、ruff、pyright、full-test-debt、台账、yaml 和 `git diff --check`。
5. 若复杂度达标，用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 刷新台账，再用 `check` 复核；如果复杂度登记没关，停线说明，不为了指标新增逻辑。
6. 请 subagent 复审落库合同、自动分配写回、下游影响、无新增兜底和 CodeStable 回填；若发现真实问题，先修复再验收。
7. 写 acceptance，PR-6 checklist 的 checks 按真实结果标 `passed/failed`，items 标 `done`，source-map 回填 P1-11/12/13，并在 PR-7 头部写清 PR-6 只证明落库合同，不证明 `/scheduler/run` 页面合同。

PR-6 执行结果：

- 已创建并验收 `codestable/features/2026-04-28-schedule-persistence-auto-assign-contract/`，checklist 全部完成，acceptance 已写入。
- 已新增 `tests/test_schedule_persistence_auto_assign_contract.py`，直接锁住错误优先级、全部非法但无可落库行、simulate、`auto_assign_persist=no`、外协隔离、已有资源不覆盖、只补空字段和 missing set 门控；该文件已进入默认 pytest 收集，默认收集数为 748。
- 已把 `build_validated_schedule_payload()` 的既有判断原样搬到 `_build_validated_schedule_row()`；对抗性复审发现的 `row is None` 静默跳过分支已删除，没有新增新 reason、新 details、fallback、兜底、静默吞错或宽泛默认值逻辑。
- 已通过 PR-6 专项测试、现有落库/服务回归、PR-5 下游页面/报表读取回归、ruff、pyright、复杂度体检、full-test-debt、台账检查、YAML 校验和 `git diff --check`；复审修正提交后最终 clean quality gate 也要在干净工作区复跑通过。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 后，P1-11 复杂度登记已移除，`complexity_count=39`；P1-12/P1-13 按 test_coverage 锁证。
- 本轮没有新增写前重读数据库工序的特殊检查，没有改 summary、页面、route、viewmodel、repo、runtime/plugin 或质量门禁工具；没有减少 full-test-debt，active xfail 仍为 5 条，`collected_count=748`。

### PR-7：/scheduler/run ViewResult

PR-7 头部承接 PR-6 完成结果：

- PR-6 已收口落库校验和 auto-assign persist：坏排产结果会在落库前按稳定优先级拒绝，simulate 不改真实批次/工序状态和资源，auto-assign persist 只补内部缺资源工序的空字段。
- PR-6 只证明 `schedule_persistence.py` 的落库合同，不证明 `/scheduler/run` route、view result、flash、跳转或页面文案已经完成。
- PR-7 可以承接稳定的 service/persistence 输出，但必须自己证明 route 只做表单解析、服务调用、view result、flash 和跳转；不能把 PR-6 的 proof 当成页面合同 proof。
- PR-6 不减少 full-test-debt，active xfail 仍为 5 条；PR-7 若要声明任何债务变化，也必须用自己的测试、台账和 full-test-debt 检查重新证明。

目标：

- route 不再直接解释 summary 深层字段。
- 建立 `RunScheduleViewResult`。

退出条件：

- 映射表中 P1-18 的当前事实源被解除、减少或确认已由近期提交解决。
- route 测试只 mock service，断用户可见 flash。
- 页面没有因为 service 内部字段调整而反复返工。

M6 / PR-7 执行前细化：

- 本次只做 PR-7，不把 PR-8 `batches_page()` 混进同一轮实现。PR-8 继续作为下一任务，等 PR-7 验收后在头部承接。
- 根因不是服务返回缺字段，而是 `run_schedule()` route 直接拆 `summary`、`result_status` 和 `overdue_batches` 来拼页面提示，route 背了展示规则。
- 新增 `RunScheduleViewResult` 纯展示对象，只消费 `ScheduleService.run_schedule()` 返回的公开 dict，并复用 `build_summary_display_state()`。
- `scheduler_run.py` 只保留表单解析、服务调用、ViewResult 构建、flash、异常边界和跳转；展示文案、降级、告警、错误预览和超期样本裁剪搬到 viewmodel。
- 不改 `ScheduleService`、summary、result_summary、落库、模板、`scheduler_week_plan.py`、`scheduler_batches.py`、`scheduler_bp.py`。
- 不新增业务 `if`、fallback、兜底、静默吞错、新默认值、新 reason 或新 details；如果实现时发现必须新增特殊处理，先停线说明原因。
- P1-18 旧编号来源仍证据不足，本轮只按当前 `scheduler_run.py:run_schedule` 复杂度、页面合同和测试覆盖事实源处理；不写 full-test-debt 减少。

执行步骤：

1. 创建 `codestable/features/2026-04-28-scheduler-run-view-result/` design/checklist，并把 items.yaml 改为 `in-progress`。
2. 补 `tests/test_scheduler_run_view_result_contract.py`，覆盖成功、部分成功、失败、公开降级提示、告警数量、错误预览、超期样本最多 10 个和 `AppError` 用户提示。
3. 新增 `web/viewmodels/scheduler_run_view_result.py`，原样搬移 `/scheduler/run` 现有展示判断。
4. 收薄 `web/routes/domains/scheduler/scheduler_run.py`，route 只按 ViewResult flash 和跳转。
5. 跑 PR-7 目标测试、共享页面测试、ruff、pyright、复杂度体检、full-test-debt、台账检查、YAML 校验和 `git diff --check`。
6. 若 `run_schedule` 复杂度降到阈值内，用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 刷新台账；否则停线说明，不为了关登记新增逻辑。
7. 执行后请 subagent 复审 PR-7 合同、无新增兜底、共享层影响、测试是否绑定内部 summary、CodeStable 回填和债务口径；通过后写 acceptance，并在 PR-8 头部写清 proof 边界。

M6 / PR-7 执行结果回填：

- 已新增 `web/viewmodels/scheduler_run_view_result.py`，把 `/scheduler/run` 的主提示、主降级、次级降级、告警、错误预览和超期样本整理从 route 搬到 ViewResult。
- `web/routes/domains/scheduler/scheduler_run.py` 现在只保留表单解析、调用 `ScheduleService.run_schedule()`、构建 ViewResult、flash、异常边界和跳转。
- 已新增 `tests/test_scheduler_run_view_result_contract.py`，覆盖成功、失败、公开降级提示、超期样本最多 10 个、跳转目标、普通异常通用提示和 `AppError` 用户文案；现有 `/scheduler/run` 回归继续覆盖部分成功、告警数量、错误预览和 checkbox 三态。
- 对抗复审发现 ViewResult 曾多做一层消息默认整理，本轮已删除，继续交给原有 `scheduler_bp` 展示函数处理，没有新增 fallback、兜底、静默吞错、新 reason 或新 details。
- 二次对抗审查又补强了测试：失败、业务错误和普通意外错误都会断言跳回批次页；普通意外错误只给用户看通用中文提示；源码字符串守护已收窄为“不让 route 直接拆展示状态”。
- 没有改 `ScheduleService`、summary、result_summary、落库、模板、`scheduler_week_plan.py`、`scheduler_batches.py` 或 `scheduler_bp.py`。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已移除 P1-18 对应的 `run_schedule` 复杂度登记；`complexity_count` 从 39 降到 38。
- `tools/check_full_test_debt.py` 仍是 5 条 active xfail，`collected_count=755`，本轮不写 full-test-debt 减少。

### PR-8：batches_page() viewmodel

PR-8 头部承接 PR-7 完成结果：

- PR-7 只证明 `/scheduler/run` 的表单解析、服务调用、ViewResult 构建、flash、异常边界和跳转。
- PR-7 不证明 `batches_page()` 的筛选、批次行、配置面板、最新历史面板、latest summary 解析或页面快照。
- PR-8 必须从 P1-19 自己开始取证，先确认 `complexity:web-routes-domains-scheduler-scheduler_batches-batches_page` 仍是当前事实源。
- PR-8 不能继承 PR-7 的 full-test-debt、复杂度或页面 proof；完成时也要自己跑目标测试、共享页面保护、债务检查和 CodeStable 回填。

PR-8 执行前细化：

- 本次只做 `/scheduler/` 批次首页 `batches_page()`，不混入 `/scheduler/run`、批次管理页、Excel 批次页、配置保存页或 runtime/plugin/infra 支线。
- 根因是 `batches_page()` 同时承担请求读取、服务调用、批次行加工、配置面板加工、最近排产快照加工和模板参数拼装；P1-19 的当前事实源仍是 `complexity:web-routes-domains-scheduler-scheduler_batches-batches_page`。
- 新增 `web/viewmodels/scheduler_batches_page.py`，只接收普通数据，不导入 Flask、service、repo 或 route；拆出筛选状态、批次行、配置面板、最近排产快照和模板上下文构建。
- `batches_page()` route 只保留 `request.args`、`g.services`、`parse_page_args()`、服务调用、现有历史读取异常日志边界、viewmodel 调用和 `render_template()`。
- 保持模板字段名不变；执行中如果发现模板和既有页面合同不一致，只允许补齐已有合同，不改页面结构。
- 不新增新的 `if`、fallback、兜底、静默吞错、新默认值、新 reason 或新 details；如果发现必须新增特殊处理，先停线说明原因。

PR-8 执行计划：

1. 创建 `codestable/features/2026-04-28-batches-page-viewmodel/` design/checklist，并把 items.yaml 改为 `in-progress`。
2. 新增默认可收集测试，覆盖默认 status、空 status、only_ready、批次行中文字段、配置降级、无最近历史、summary 解析失败、latest algo config snapshot 和非 pending 控件隐藏。
3. 新增 `scheduler_batches_page` viewmodel，复用现有 enum display、配置显示和 summary 显示 helper。
4. 瘦身 `scheduler_batches.py:batches_page()`，不改批次管理页、Excel 批次页、配置保存链路、运行排产 route、模板或共享 summary 展示规则。
5. 跑 PR-8 目标测试、共享页面测试、邻近模块测试、ruff、pyright、复杂度体检、full-test-debt、台账检查、YAML 校验和 `git diff --check`。
6. 如果复杂度降到阈值内，运行 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`；否则停线说明，不为关登记新增逻辑。
7. 执行后请 subagent 复审页面合同、无新增兜底、共享层影响、测试口径、CodeStable 回填和 P1-19 债务口径；通过后写 acceptance，并在 PR-9 头部写清 PR-8 proof 边界。

目标：

- 拆出页面筛选、批次行、配置面板、最新历史面板状态构建。
- 保持模板尽量不变，先稳定 viewmodel。

退出条件：

- 映射表中 P1-19 的当前事实源被解除、减少或确认已由近期提交解决。
- 默认 status、空 status、only_ready、config degraded、latest history 缺失、latest summary parse failed、latest algo config snapshot 均有 snapshot tests。

PR-8 执行结果回填：

- 已新增 `web/viewmodels/scheduler_batches_page.py`，把 `/scheduler/` 批次首页的筛选状态、批次展示行、配置面板、最近历史面板和模板上下文整理从 route 搬到纯展示构建层。
- `web/routes/domains/scheduler/scheduler_batches.py:batches_page()` 现在只保留请求读取、服务调用、分页、原有最近历史读取失败日志边界、配置面板共享构建器调用、viewmodel 构建和渲染；没有把原有异常边界扩大到 summary 解析或整页渲染。
- 已新增默认可收集的 `tests/test_scheduler_batches_page_viewmodel.py`，覆盖默认 `status=pending`、显式 `status=` 全部状态、非 pending 状态控件隐藏、`only_ready` 三态过滤、筛选空结果文案、批次行中文字段、配置降级公开提示、无最近历史、summary 解析失败不泄漏原文、latest algo config snapshot 和 route 使用 viewmodel 输出。
- 对抗复审发现 `status=` 后端已经表示全部状态，但状态下拉框没有“全部”选项；已在 `templates/scheduler/batches.html` 和 `web_new_test/templates/scheduler/batches.html` 补齐这个既有页面合同，并把空 status 测试改成只检查状态下拉框。
- 后续对抗审核发现全部状态页标题、筛选空结果文案和配置面板 helper 残留会让 PR-8 收口不够干净；已用固定中性文案修正页面误导，并把配置面板装配 helper 从 route 文件移到共享配置展示 helper。
- 没有改 `/scheduler/run`、批次管理页、Excel 批次页、配置保存链路、页面说明 registry、route wrapper 或共享 summary 展示规则。
- 没有新增 fallback、兜底、静默吞错、新默认值、新 reason 或新 details；本轮只是搬移已有页面装配判断，并修正模板与既有筛选合同的不一致。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已移除 P1-19 对应的 `batches_page` 复杂度登记；`complexity_count` 从 38 降到 37。
- `tools/check_full_test_debt.py` 仍是 5 条 active xfail，`collected_count=772`，本轮不写 full-test-debt 减少。

### PR-9 / M7：runtime/plugin/infra 支线

M7 头部承接 PR-8 完成结果：

- PR-8 只证明 `/scheduler/` 批次首页的筛选状态、批次展示行、配置面板、最近历史面板、模板“全部状态”选项和 viewmodel 装配。
- PR-8 不证明 runtime/plugin/infra，不证明启动链、插件 enabled source、Chrome 停机、launcher 分类或 plugin degradation。
- M7 深挖后确认不能把 P1-20..P1-25 塞进一个宽泛 PR：P1-20/P1-21/P1-22 属于 launcher/runtime/Chrome stop；P1-23 属于 plugin enabled-source；P1-24 只复核 plugin fallback；P1-25 继续证据不足，不开修。
- M7 不继承 PR-8 的页面 proof；所有结论都必须来自启动链专项测试、plugin 专项测试、架构体检、台账检查和 CodeStable 回填。

M7-0 证据校准和设计落地：

- 两轮 subagent 深挖确认 `web/bootstrap/launcher.py` 是启动现场门面，不是普通工具文件；`entrypoint.py`、`scripts/run_quality_gate.py`、批处理、安装包和测试都依赖它的公开函数。
- `launcher.py` 的根因是职责混在一起，但公开函数名、状态文件、合同字段和 CLI 返回码不能改。
- Chrome stop 有真行为问题：多进程 Chrome 中一个 pid 被杀可能连带带走另一个 pid，旧实现按“每个旧 pid 都杀成功”判断，会误报失败。
- `web/bootstrap/plugins.py:_apply_enabled_sources` 的根因是插件开关来源判定、公开状态行整理、错误脱敏和整体来源汇总混在一起。
- P1-24 没有找到可包装成 open bug 的 plugin fallback；P1-25 没有找到当前路径、台账条目或测试 nodeid。

M7-A launcher 门面瘦身与 runtime 启停修复：

- 新增 `web/bootstrap/launcher_network.py`、`launcher_paths.py`、`launcher_processes.py`、`launcher_contracts.py`、`launcher_stop.py`。
- `web/bootstrap/launcher.py` 保留公开门面和旧测试兼容入口，从 1204 行降到 177 行；新模块都仍在 `web/bootstrap/**/*.py` 扫描范围内，没有把债移出门禁。
- `stop_aps_chrome_processes()` 仍返回 bool，`stop_runtime_from_dir()` 仍返回 0/1，`--runtime-stop` 外部合同不变。
- APS Chrome 停止改为“最终复查同 profile 进程是否仍存在”；旧 pid 已经被连带关闭不再误报失败，最终仍有 profile 进程则继续失败。
- Chrome 独立安装脚本同步改为记录 Stop-Process 失败 pid 后再最终复查，不改变 silent uninstall 的失败返回口径。
- `tools/quality_gate_shared.py` 的启动链样本点已迁移到新文件对应处理点；`开发文档/技术债务治理台账.md` 的 accepted risk 引用已从旧 `launcher.py` id 迁移到新模块 id。

M7-B plugin enabled-source 合同收窄：

- `_apply_enabled_sources()` 已拆成 `_resolve_enabled_source()`、`_public_plugin_status_row()`、`_config_source_summary()`。
- 新增真实可选插件默认关闭测试：`pandas_excel_backend` 和 `ortools_probe` 无配置时默认关闭、不注册能力，Excel 默认仍走 openpyxl。
- 系统页新增插件留痕状态和冲突能力展示，状态结构里的 `telemetry_persisted` 与 `conflicted_capabilities` 不再只能靠内部数据查看。
- P1-24 只写“已复核”，不包装成已修 open bug；P1-25 保持证据不足。

M7 执行结果回填：

- P1-20：`oversize:web-bootstrap-launcher` 已解除，超长登记从 9 降到 8。
- P1-21：`_classify_runtime_state` 复杂度登记已解除。
- P1-22：`_list_aps_chrome_pids`、`stop_runtime_from_dir` 复杂度登记已解除，同批关闭 `acquire_runtime_lock` 这个 launcher 复杂度兄弟项。
- P1-23：`_apply_enabled_sources` 复杂度登记已解除。
- P1-24：复核后没有 open plugin fallback 修复项，本轮只补用户可见状态。
- P1-25：证据不足，未处理。
- `scripts/sync_debt_ledger.py check` 已通过，当前 `complexity_count=32`、`oversize_count=8`、`silent_fallback_count=154`、`test_debt_count=5`。
- `tools/check_full_test_debt.py` 仍为 5 条 active xfail，本轮不声明 full-test-debt 减少。
- 代码完成后已调用 4 路 subagent 只读审查：兜底审查、启动入口审查和插件合同审查均未发现阻断问题；台账审查发现 accepted risk 说明仍有乱码，已修成可读中文并重跑台账校验通过。

后续任务头部承接说明：

- M7 已把 runtime/plugin/infra 支线中有当前事实源的 P1-20/P1-21/P1-22/P1-23 处理完成。
- 后续如果继续做启动链，只能基于新 `launcher_*` 模块和当前台账事实源，不得再引用旧 `launcher.py` 行号或旧复杂度登记。
- 后续如果继续做 plugin，只能基于新 enabled-source 合同和真实 open 台账项；P1-24 不能被当作未修 bug 反复包装。
- 后续看 M7 台账时，以新模块 id 和已修复的 accepted risk 中文说明为准；不要再引用旧 `launcher.py` 接受风险说明或乱码备注。
- P1-25 仍然证据不足，除非补出具体路径、台账条目或测试 nodeid，否则不得开修。

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
- 2026-04-28：执行 M1，补齐排产输入、模板查询和服务汇总链路合同测试；最小拆分 `schedule_input_builder.py` 与 `schedule_template_lookup.py` 后刷新台账，P1-8/P1-9 两条复杂度登记已由脚本移除，P1-10 测试覆盖已补齐；PR-2 头部已写入 M1 完成内容和不可继承的 proof 边界。
- 2026-04-28：执行 M2，给冻结窗口 disabled 原因补上 `freeze_disabled_reason`，把配置读取降级归入 `degraded` 并保持 strict fail closed；summary 只透传安全 disabled 原因，配置降级不伪装成 disabled；复审发现的问题已修复。P1-14 因复杂度仍为 26/15 保持打开，P1-15 已补状态合同测试，本轮未减少 full-test-debt。
- 2026-04-28：修复 M2 二次 review finding：分析页按冻结窗口状态展示 degraded，不再把配置降级显示成普通未启用；补录 `2026-04-28-freeze-window-disabled-contract` feature 三件套；同步 P1-15 source-map 为 `evidence-locked-by-M2`，并在 M3 头部写清只能承接停机和资源池。
- 2026-04-28：执行 M3，收口停机读取和资源池候选设备补停机合同；补齐 load/extend、仓库真实查询和 collector 真实链路测试；刷新台账后 P1-16/P1-17 复杂度事实源关闭，高复杂度登记从 42 降到 40；本轮未减少 full-test-debt，M4 头部已写清不能继承 M3 proof 当作优化器 proof，最终 clean quality gate 已通过。
- 2026-04-28：修复 M3 二次 review findings：补跨过排产开始时间的停机查询测试、逐设备查询全部失败的 partial 口径测试、extend 查询前整体失败保留原 map 测试；把 M0 历史 `collected_count=700` 和当前 `collected_count=744` 拆开写，并把 source-map 台账引用改为稳定 id/symbol，不再靠会漂移的台账行号。
- 2026-04-28：细化 M4 完整治理计划，明确 M4 分 PR-4 优化器结果合同和 PR-5 summary/result_summary 合同两段执行；PR-4 不新增独立 reason 字段、不新增 fallback 行为，PR-5 承接落库历史和页面不泄漏内部诊断；items.yaml 已补窄测试、债务检查和最终 clean quality gate 命令。
- 2026-04-28：完成 PR-4 优化器结果合同补证；新增 rejected 诊断穿过 attempts 压缩和 summary 投影后的分层测试，加严已有 `state.best is None` 路径外形测试；PR-4 没有改运行代码，没有新增 reason/fallback/兜底/静默吞错，没有减少 full-test-debt，active xfail 仍为 5 条。
- 2026-04-28：完成 PR-5 summary/result_summary 合同补证；新增真实落库读回测试和真实页面/接口响应不泄漏测试，证明公开 attempts 不混入内部字段，diagnostics 正常大小下可落库读回但不展示到已覆盖响应；PR-5 没有改运行代码，没有改 schema 版本或 OptimizationOutcome，没有新增 fallback/兜底/静默吞错，没有减少 full-test-debt；完整 M4 最终 clean quality gate 已通过。
- 2026-04-28：完成 PR-6 落库校验与 auto-assign persist 合同；新增专项测试锁住错误优先级、simulate、配置关闭、外协隔离和只补空字段，并在复审后改为默认门禁可收集的 `test_*.py` 路径；原样搬移 `build_validated_schedule_payload()` 既有判断后关闭 P1-11 复杂度登记，复审发现的 `row is None` 静默跳过分支已删除，`complexity_count=39`；P1-12/P1-13 按测试覆盖锁证；本轮没有新增 fallback/兜底/静默吞错，没有减少 full-test-debt，PR-7 头部已写清不能继承落库 proof 当作页面 proof。
- 2026-04-28：完成 PR-7 `/scheduler/run` ViewResult；把页面提示组装从 route 搬到纯展示构建层，route 只保留表单、服务调用、ViewResult、flash、异常边界和跳转；复审后补强跳转目标和普通异常通用提示测试，移除 P1-18 复杂度登记，`complexity_count=38`；本轮没有新增 fallback/兜底/静默吞错，没有减少 full-test-debt，PR-8 头部已写清不能继承 `/scheduler/run` proof 当作 `batches_page()` proof。
- 2026-04-28：完成 PR-8 `/scheduler/` 批次首页 viewmodel；把筛选状态、批次展示行、配置面板、最近历史面板和模板上下文从 route 搬到纯展示构建层，route 只保留请求读取、服务调用、分页、原有最近历史读取失败日志边界、viewmodel 和渲染；复审后补齐 `status=` 的全部状态下拉选项、精确空 status 测试、非 pending 状态控件隐藏测试，并移除 P1-19 复杂度登记，`complexity_count=37`；本轮没有新增 fallback/兜底/静默吞错，没有减少 full-test-debt，PR-9 头部已写清不能继承页面 proof 当作 runtime/plugin/infra proof。
- 2026-04-28：处理 PR-8 对抗审核 findings；批次首页标题和空结果文案改成固定中性文案，配置面板装配 helper 从 route 文件移到共享配置展示 helper，测试补齐 `only_ready` 三态、非 pending 状态、空结果文案、summary 解析失败不泄漏原文和 route 使用 viewmodel 输出；没有新增 fallback/兜底/静默吞错。
- 2026-04-28：完成 M7 runtime/plugin/infra 支线校准与执行；M7 拆成证据校准、launcher/runtime/Chrome stop、plugin enabled-source 三段，P1-20/P1-21/P1-22/P1-23 关闭当前事实源，P1-24 只复核，P1-25 继续证据不足；四路 subagent 复审后修复 accepted risk 乱码说明，最终台账为 `complexity_count=32`、`oversize_count=8`、`silent_fallback_count=154`、`test_debt_count=5`，本轮没有新增 fallback/兜底/静默吞错，没有减少 full-test-debt。

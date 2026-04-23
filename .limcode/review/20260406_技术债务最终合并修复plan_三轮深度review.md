# 20260406_技术债务最终合并修复plan_三轮深度review
- 日期: 2026-04-06
- 概述: 对最新《技术债务最终合并修复plan》做三轮深度核对，逐项校验路径、函数、调用链、计数、验证命令与实际代码一致性。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 20260406 技术债务最终合并修复plan 三轮深度review

- 日期：2026-04-06
- 目标文件：`.limcode/plans/20260405_技术债务最终合并修复plan.md`
- review 方式：三轮深度核对（结构事实、代码事实、执行可落地性）
- 当前结论：进行中

## 范围
- 核对 plan 中引用的实际代码路径、函数、变量、测试入口、门禁入口与目录结构是否与当前工作区一致。
- 重点检查：是否仍存在路径漂移、函数归属错误、参数数量错误、调用链断裂、过度兼容/静默回退未被完整纳入、验证命令失真等问题。

## 关注点
1. 目录/文件路径是否真实存在。
2. 关键函数、构造器、参数计数、仓储数量、回退点数量是否与当前代码一致。
3. 验证命令、测试文件、门禁文件是否能对应到真实文件。
4. plan 的批次依赖与执行顺序是否会导致中间态断裂。
5. 是否仍有遗漏的静默回退、兼容桥、旧路径引用或不严谨表述。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, tests/test_architecture_fitness.py, tests/regression_safe_next_url_hardening.py, tests/test_source_merge_mode_constants.py, web/routes/system_utils.py, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_persistence.py, tests/regression_schedule_input_builder_template_missing_surfaces_event.py, pyproject.toml, .pre-commit-config.yaml
- 当前进度: 已记录 3 个里程碑；最新：m3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 7
- 问题严重级别分布: 高 4 / 中 2 / 低 1
- 最新结论: 经过三轮逐项核对，当前 plan 相比前版已经明显收敛，主体结构、任务分批、关键函数归属、目录计数和大部分验证命令都与现状对齐；但它**仍不能直接视为“执行者拿到即可无歧义开工”的最终权威稿**。阻断点主要集中在四处：一是任务 3 迁移后的路径敏感测试/门禁尚未成体系收口；二是任务 5 仍漏掉 `schedule_orchestrator.py:_normalize_optimizer_outcome(...)` 这条主链兼容桥；三是 `if best is None` 的归属在任务 5、任务 6 与批次 2 退出条件之间仍自相矛盾；四是 `pyproject.toml` 全局忽略 `F401`，会让任务 3 设计的 `per-file-ignores` 门禁实质失效。此外，`persist_schedule()` 参数计数仍偏 1，任务 5 还漏掉了模板缺失退化回归，plan 内也残留少量文案级漂移。结论：**需要继续修订后再执行**；建议先完成高优先级四项修正，再做一次针对任务 3 / 任务 5 / 任务 3 门禁链的快速复核。
- 下一步建议: 先修正四个高优先级问题：补齐任务 3 路径敏感测试清单、把 `_normalize_optimizer_outcome()` 纳入任务 5、统一 `if best is None` 的单一归属、移除全局 `F401` 忽略并改为窄化 `per-file-ignores`；随后再补正参数计数与遗漏回归。
- 总体结论: 需要后续跟进

## 评审发现

### 任务 3 后的路径敏感测试未收口

- ID: plan-task3-path-sensitive-tests-gap
- 严重级别: 高
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  plan 已要求任务 3 之后统一改用迁移后路径，并把 `_safe_next_url` 从 `web/routes/system_utils.py` 抽到 `web/routes/navigation_utils.py`；但现有 `tests/test_architecture_fitness.py`、`tests/regression_safe_next_url_hardening.py`、`tests/test_source_merge_mode_constants.py` 仍绑定旧根路径或旧符号归属。尤其任务 3 的验证命令本身就要求立即运行 `tests/test_architecture_fitness.py`，而该文件内含大量旧路径白名单，迁移后会先于任务 9 触发失败。当前 plan 对这批路径敏感测试的更新范围写得过窄，无法保证任务 3 完成后立刻可回归。
- 建议:

  在任务 3 增加一个明确子步骤，按清单同步修正所有路径敏感门禁/回归：至少包含 `tests/test_architecture_fitness.py` 的全部路径白名单、`tests/regression_safe_next_url_hardening.py`、`tests/test_source_merge_mode_constants.py`、以及依赖源码路径的支撑脚本；否则任务 3 的验证命令会先于任务 9 失效。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:587-593`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:607-610`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:649-667`
  - `tests/test_architecture_fitness.py:44-70#_known_oversize_files`
  - `tests/test_architecture_fitness.py:404-449#test_no_silent_exception_swallow`
  - `tests/test_architecture_fitness.py:546-603#test_cyclomatic_complexity_threshold`
  - `tests/regression_safe_next_url_hardening.py:53-68#main`
  - `tests/test_source_merge_mode_constants.py:92-99#test_target_files_have_no_source_merge_mode_quoted_literals`
  - `web/routes/system_utils.py:19-41#_safe_next_url`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_safe_next_url_hardening.py`
  - `tests/test_source_merge_mode_constants.py`
  - `web/routes/system_utils.py`

### 任务 5 漏掉 `_normalize_optimizer_outcome` 兼容桥

- ID: plan-task5-misses-normalized-optimizer-outcome-bridge
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  plan 已把 `_merge_summary_warnings`、`_schedule_with_optional_strict_mode` 等兼容桥纳入任务 5，但 `schedule_orchestrator.py` 里真正位于主链入口处的 `_normalize_optimizer_outcome(...)` 仍未被纳入范围。当前 `orchestrate_schedule_run()` 先调用 `optimize_schedule_fn(...)`，再通过 `_normalize_optimizer_outcome()` 对 `results/summary/used_strategy/used_params/best_score/attempts/algo_stats` 等字段进行 `getattr/list/dict` 兼容性整形。只删除 `_merge_summary_warnings` 并不能真正收紧“优化器结果对象”的边界，主链仍然保留一整块形态探测逻辑。
- 建议:

  把 `_normalize_optimizer_outcome()` 明确纳入任务 5：要么直接要求 `optimize_schedule()` 返回稳定 `OptimizationOutcome` 并删掉该整形层，要么改成显式契约校验并在失败时抛出可观测错误，而不是继续用 `getattr(...)` 静默兼容。
- 证据:
  - `core/services/scheduler/schedule_orchestrator.py:53-68#_normalize_optimizer_outcome`
  - `core/services/scheduler/schedule_orchestrator.py:103-129#orchestrate_schedule_run`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:785-792`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:829-855`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### `if best is None` 归属仍然冲突

- ID: plan-task5-task6-best-none-ownership-conflict
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  plan 一方面在任务 5 中要求把 `_schedule_with_optional_strict_mode` 的导入、常规调用与 `if best is None` 分支同步收口，另一方面又在任务 6 中写明“本步只决定 `if best is None` 的最终命运”；更进一步，批次 2 退出条件已经要求在任务 5 / 批次 2 结束时让该分支“已删除或改为显式失败路径”。这让执行者无法判断：该分支到底应在任务 5 完成，还是允许保留到任务 6。
- 建议:

  统一单一归属。更稳妥的写法是：任务 5 先把该分支改成显式失败路径并移除兼容函数依赖；任务 6 只在证明不可达后再删除分支。与此同时，把批次 2 退出条件与任务 6 文案同步成同一口径。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:549-582#optimize_schedule`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:829-844`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:944-947`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1427-1434`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### `persist_schedule()` 参数计数仍偏 1

- ID: plan-persist-schedule-keyword-count-off-by-one
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  plan 多处把 `persist_schedule()` 描述成“22 个命名参数”，但当前 `schedule_persistence.py: persist_schedule()` 实际只有 21 个关键字参数（`cfg` 到 `time_cost_ms`），`svc` 是位置参数；`schedule_service.py` 的调用点也只传了 21 个关键字参数。这个计数偏差虽然不会直接改坏代码，但会让后续“拆到 RunContext + ScheduleOrchestrationOutcome”的核对标准继续漂移。
- 建议:

  统一改成“21 个关键字参数（另加 `svc`）”，或直接改成“不再以参数个数做文案锚点，只列清字段归属”。
- 证据:
  - `core/services/scheduler/schedule_persistence.py:244-268#persist_schedule`
  - `core/services/scheduler/schedule_service.py:291-314#_run_schedule_impl`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:93`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:821-827`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1431-1433`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### 任务 5 漏掉模板缺失退化回归

- ID: plan-task5-misses-template-missing-regression
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  删除 `_lookup_template_group_context` 的旧 `_get_template_and_group_for_op` 回退后，除了 `regression_schedule_input_builder_safe_float_parse.py` 和 `...strict_hours_and_ext_days.py` 之外，现有 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py` 也会直接受影响。该测试专门验证统一模板查找入口在模板缺失时是否仍产出 `template_missing` 结构化退化事件，并保留 `merge_context_events` 与 `ext_days` 语义。当前 plan 没把它写进任务 5 的验证命令，存在遗漏。
- 建议:

  把 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py` 补入任务 5 的实施前确认与验证命令，作为删除模板查找兼容桥后的必跑护栏。
- 证据:
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py:24-51#test_schedule_input_builder_template_missing_surfaces_event`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:798-818`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:858-872`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### 全局 `F401` 忽略会让门面白名单失效

- ID: plan-ruff-f401-global-ignore-undermines-per-file-gates
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m3
- 说明:

  当前 `pyproject.toml` 已全局忽略 `F401`，而 plan 又在任务 3 中要求把根层门面与迁移后的聚合文件逐条写入 `per-file-ignores`。如果不先移除全局 `F401`，这些 `per-file-ignores` 只是形式化登记，不会真正收紧 side-effect 导入边界，也无法达到“只有门面文件可豁免，其余文件必须被门禁拦住”的目标。
- 建议:

  把“收紧 `ruff` 例外”写成两步：先移除全局 `F401` 忽略，再仅对批准的 side-effect 聚合文件保留 `per-file-ignores`。否则任务 3 的门禁设计不会真正生效。
- 证据:
  - `pyproject.toml:28-43`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:643-647`
  - `pyproject.toml`
  - `.pre-commit-config.yaml`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### plan 仍有局部文案漂移

- ID: plan-minor-self-consistency-drifts-remain
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: m3
- 说明:

  plan 还残留少量不会立刻改坏代码、但会削弱执行严谨性的内部漂移：任务 4 的“当前六个文件”与上文列举的 7 个文件不一致；关键结构决策第 3 点仍引用旧根路径 `core/services/scheduler/schedule_summary_degradation.py`，与任务 3 的子包目标路径和任务 5 的文件职责口径不一致。
- 建议:

  统一把未来态路径写成迁移后的 canonical 路径，并把“六个文件”改为准确计数，避免执行者在细节处重新猜测。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:177-182`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:500-505`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:697-706`
  - `pyproject.toml`
  - `.pre-commit-config.yaml`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

## 评审里程碑

### m1 · 第一轮：结构事实与路径迁移核对

- 状态: 已完成
- 记录时间: 2026-04-06T02:58:14.724Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, tests/test_architecture_fitness.py, tests/regression_safe_next_url_hardening.py, tests/test_source_merge_mode_constants.py, web/routes/system_utils.py
- 摘要:

  已核对最新 plan 与当前目录结构的一致性。`core/services/scheduler/` 当前确有 45 个平铺文件，`web/routes/` 当前确有 59 个平铺文件，任务 3 的基线计数准确；`ScheduleService.__init__` 当前也确实内部创建 10 个仓储实例。

  但在“任务 3 迁移后仍要立即跑架构门禁/端点回归”的执行链上，plan 仍遗漏一批现存的路径敏感测试与门禁条目：
  - `tests/test_architecture_fitness.py` 内部存在大量基于旧根路径的超长文件白名单、局部解析白名单、静默吞异常白名单、复杂度白名单；
  - `tests/regression_safe_next_url_hardening.py` 仍直接导入 `web.routes.system_utils` 并调用 `_safe_next_url`；
  - `tests/test_source_merge_mode_constants.py` 仍直接读取 `core/services/scheduler/schedule_optimizer.py`、`freeze_window.py` 等旧根路径文件。

  而 plan 在任务 3 中已经明确：`_safe_next_url` 将迁出到 `web/routes/navigation_utils.py`，任务 3 完成后后续步骤只再引用迁移后路径；同时任务 3 的验证命令又要求立即执行 `tests/test_architecture_fitness.py`。这会导致任务 3 自身就出现“代码已迁移，但门禁/回归仍绑定旧路径”的断层。
- 结论:

  目录计数与多数路径事实已对齐，但任务 3 之后的测试/门禁路径漂移治理仍未收口，当前 plan 还不能保证迁移后立即可验证。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:587-593`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:607-610`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:649-667`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1270-1273`
  - `tests/test_architecture_fitness.py:44-70#_known_oversize_files`
  - `tests/test_architecture_fitness.py:404-449#test_no_silent_exception_swallow`
  - `tests/test_architecture_fitness.py:546-603#test_cyclomatic_complexity_threshold`
  - `tests/regression_safe_next_url_hardening.py:53-68#main`
  - `tests/regression_safe_next_url_hardening.py:82-83#main`
  - `tests/test_source_merge_mode_constants.py:92-99#test_target_files_have_no_source_merge_mode_quoted_literals`
  - `web/routes/system_utils.py:19-41#_safe_next_url`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_safe_next_url_hardening.py`
  - `tests/test_source_merge_mode_constants.py`
  - `web/routes/system_utils.py`
- 下一步建议:

  继续第二轮，深入核对调度主链兼容桥、结果对象边界与参数计数是否完全与 plan 一致。
- 问题:
  - [高] 测试: 任务 3 后的路径敏感测试未收口

### m2 · 第二轮：调度主链、兼容桥与结果边界核对

- 状态: 已完成
- 记录时间: 2026-04-06T02:59:03.492Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_persistence.py, tests/regression_schedule_input_builder_template_missing_surfaces_event.py, .limcode/plans/20260405_技术债务最终合并修复plan.md
- 摘要:

  已沿 `ScheduleService.run_schedule() -> collect_schedule_run_input() -> orchestrate_schedule_run() -> persist_schedule()` 主链逐段核对 plan 与代码现状。当前 plan 对以下事实描述是正确的：
  - `collect_schedule_run_input()` 当前确为 16 个入参（含 `svc`）；
  - `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_schedule_with_optional_strict_mode`、`_scheduler_accepts_strict_mode`、`_merge_summary_warnings` 都仍然存在；
  - `schedule_service.py` 返回值构建块确实仍对 `orchestration.summary` 做 7 处 `getattr(...)` 读取。

  但继续深挖后，plan 仍有四个关键断口：
  1. 只点名了 `_merge_summary_warnings`，却没有把 `schedule_orchestrator.py:_normalize_optimizer_outcome(...)` 纳入兼容桥清理范围；该函数当前仍对 `optimize_schedule()` 的返回对象做整块 `getattr/list/dict` 规范化，实际上仍是主链上的形态探测桥。
  2. `if best is None` 的最终归属仍然自相矛盾：任务 5 说任务 6 决定最终命运，但批次 2 退出条件又要求在任务 5/批次 2 结束时就删除或改成显式失败路径。
  3. `persist_schedule()` 的“22 个命名参数”说法仍未修正，实际定义与调用都只有 21 个关键字参数（`svc` 另算）。
  4. 删除 `_lookup_template_group_context` 旧回退时，plan 的验证命令漏掉了现有 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`，该测试正是统一模板查找入口与结构化退化事件的直接护栏。
- 结论:

  主链大方向已比旧版 plan 明确很多，但兼容桥边界、分支归属、参数计数与回归护栏仍有残留不一致，当前还不足以称为“执行者拿到即可无歧义开工”的版本。
- 证据:
  - `core/services/scheduler/schedule_orchestrator.py:53-68#_normalize_optimizer_outcome`
  - `core/services/scheduler/schedule_orchestrator.py:71-100#_merge_summary_warnings`
  - `core/services/scheduler/schedule_optimizer.py:549-582#optimize_schedule`
  - `core/services/scheduler/schedule_persistence.py:244-268#persist_schedule`
  - `core/services/scheduler/schedule_service.py:291-314#_run_schedule_impl`
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py:24-51#test_schedule_input_builder_template_missing_surfaces_event`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:785-792`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:829-855`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:858-872`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:944-947`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1427-1434`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  继续第三轮，收口质量门禁、`ruff` 规则、静默回退门禁与文案一致性。
- 问题:
  - [高] 可维护性: 任务 5 漏掉 `_normalize_optimizer_outcome` 兼容桥
  - [高] 其他: `if best is None` 归属仍然冲突
  - [中] 其他: `persist_schedule()` 参数计数仍偏 1
  - [中] 测试: 任务 5 漏掉模板缺失退化回归

### m3 · 第三轮：质量门禁与文案一致性核对

- 状态: 已完成
- 记录时间: 2026-04-06T02:59:50.595Z
- 已审模块: pyproject.toml, .pre-commit-config.yaml, .limcode/plans/20260405_技术债务最终合并修复plan.md
- 摘要:

  第三轮聚焦质量门禁与文案自洽性。当前仓库的 `pyproject.toml` 已经把 `F401` 放在全局 `ignore` 中，同时又单独维护 `per-file-ignores`；而 plan 在任务 3 里把 side-effect 导入治理建立在 `per-file-ignores` 之上，却没有要求移除全局 `F401`。这意味着即使把 `scheduler.py`、`scheduler_pages.py` 等门面文件逐条写进 `per-file-ignores`，`ruff` 也依然不会对其他文件的未使用导入做约束，门禁会处于“看上去更精细、实际上仍全局放开”的状态。

  另外，plan 还残留少量文案级自洽问题：
  - 任务 4“实施前确认”列了 7 个配置规则文件，但下一步却写成“当前六个文件”；
  - “关键结构决策”第 3 点仍引用旧根路径 `core/services/scheduler/schedule_summary_degradation.py`，而任务 3 的目标目录与任务 5 的职责描述已经把它放到了 `core/services/scheduler/summary/` 子包。

  这些问题不如前两轮发现那样会直接打断主链，但会削弱 plan 作为唯一权威执行稿的严谨性。
- 结论:

  第三轮确认：plan 在门禁设计上还有一个会实质失效的高优先级问题（全局 `F401` 忽略），并残留少量局部文案漂移；若不修正，执行阶段仍可能出现“规则已写、门禁不生效”的假收敛。
- 证据:
  - `pyproject.toml:28-43`
  - `.pre-commit-config.yaml:1-12`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:643-647`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:697-706`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:177-182`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:500-505`
  - `pyproject.toml`
  - `.pre-commit-config.yaml`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  汇总三轮结论并给出最终是否可执行的判断，以及建议的最小修正清单。
- 问题:
  - [高] 可维护性: 全局 `F401` 忽略会让门面白名单失效
  - [低] 文档: plan 仍有局部文案漂移

## 最终结论

经过三轮逐项核对，当前 plan 相比前版已经明显收敛，主体结构、任务分批、关键函数归属、目录计数和大部分验证命令都与现状对齐；但它**仍不能直接视为“执行者拿到即可无歧义开工”的最终权威稿**。阻断点主要集中在四处：一是任务 3 迁移后的路径敏感测试/门禁尚未成体系收口；二是任务 5 仍漏掉 `schedule_orchestrator.py:_normalize_optimizer_outcome(...)` 这条主链兼容桥；三是 `if best is None` 的归属在任务 5、任务 6 与批次 2 退出条件之间仍自相矛盾；四是 `pyproject.toml` 全局忽略 `F401`，会让任务 3 设计的 `per-file-ignores` 门禁实质失效。此外，`persist_schedule()` 参数计数仍偏 1，任务 5 还漏掉了模板缺失退化回归，plan 内也残留少量文案级漂移。结论：**需要继续修订后再执行**；建议先完成高优先级四项修正，再做一次针对任务 3 / 任务 5 / 任务 3 门禁链的快速复核。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnmlevj8-acq7oj",
  "createdAt": "2026-04-06T00:00:00.000Z",
  "updatedAt": "2026-04-06T03:01:16.193Z",
  "finalizedAt": "2026-04-06T03:01:16.193Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260406_技术债务最终合并修复plan_三轮深度review",
    "date": "2026-04-06",
    "overview": "对最新《技术债务最终合并修复plan》做三轮深度核对，逐项校验路径、函数、调用链、计数、验证命令与实际代码一致性。"
  },
  "scope": {
    "markdown": "# 20260406 技术债务最终合并修复plan 三轮深度review\n\n- 日期：2026-04-06\n- 目标文件：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n- review 方式：三轮深度核对（结构事实、代码事实、执行可落地性）\n- 当前结论：进行中\n\n## 范围\n- 核对 plan 中引用的实际代码路径、函数、变量、测试入口、门禁入口与目录结构是否与当前工作区一致。\n- 重点检查：是否仍存在路径漂移、函数归属错误、参数数量错误、调用链断裂、过度兼容/静默回退未被完整纳入、验证命令失真等问题。\n\n## 关注点\n1. 目录/文件路径是否真实存在。\n2. 关键函数、构造器、参数计数、仓储数量、回退点数量是否与当前代码一致。\n3. 验证命令、测试文件、门禁文件是否能对应到真实文件。\n4. plan 的批次依赖与执行顺序是否会导致中间态断裂。\n5. 是否仍有遗漏的静默回退、兼容桥、旧路径引用或不严谨表述。"
  },
  "summary": {
    "latestConclusion": "经过三轮逐项核对，当前 plan 相比前版已经明显收敛，主体结构、任务分批、关键函数归属、目录计数和大部分验证命令都与现状对齐；但它**仍不能直接视为“执行者拿到即可无歧义开工”的最终权威稿**。阻断点主要集中在四处：一是任务 3 迁移后的路径敏感测试/门禁尚未成体系收口；二是任务 5 仍漏掉 `schedule_orchestrator.py:_normalize_optimizer_outcome(...)` 这条主链兼容桥；三是 `if best is None` 的归属在任务 5、任务 6 与批次 2 退出条件之间仍自相矛盾；四是 `pyproject.toml` 全局忽略 `F401`，会让任务 3 设计的 `per-file-ignores` 门禁实质失效。此外，`persist_schedule()` 参数计数仍偏 1，任务 5 还漏掉了模板缺失退化回归，plan 内也残留少量文案级漂移。结论：**需要继续修订后再执行**；建议先完成高优先级四项修正，再做一次针对任务 3 / 任务 5 / 任务 3 门禁链的快速复核。",
    "recommendedNextAction": "先修正四个高优先级问题：补齐任务 3 路径敏感测试清单、把 `_normalize_optimizer_outcome()` 纳入任务 5、统一 `if best is None` 的单一归属、移除全局 `F401` 忽略并改为窄化 `per-file-ignores`；随后再补正参数计数与遗漏回归。",
    "reviewedModules": [
      ".limcode/plans/20260405_技术债务最终合并修复plan.md",
      "tests/test_architecture_fitness.py",
      "tests/regression_safe_next_url_hardening.py",
      "tests/test_source_merge_mode_constants.py",
      "web/routes/system_utils.py",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_persistence.py",
      "tests/regression_schedule_input_builder_template_missing_surfaces_event.py",
      "pyproject.toml",
      ".pre-commit-config.yaml"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 7,
    "severity": {
      "high": 4,
      "medium": 2,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "m1",
      "title": "第一轮：结构事实与路径迁移核对",
      "status": "completed",
      "recordedAt": "2026-04-06T02:58:14.724Z",
      "summaryMarkdown": "已核对最新 plan 与当前目录结构的一致性。`core/services/scheduler/` 当前确有 45 个平铺文件，`web/routes/` 当前确有 59 个平铺文件，任务 3 的基线计数准确；`ScheduleService.__init__` 当前也确实内部创建 10 个仓储实例。\n\n但在“任务 3 迁移后仍要立即跑架构门禁/端点回归”的执行链上，plan 仍遗漏一批现存的路径敏感测试与门禁条目：\n- `tests/test_architecture_fitness.py` 内部存在大量基于旧根路径的超长文件白名单、局部解析白名单、静默吞异常白名单、复杂度白名单；\n- `tests/regression_safe_next_url_hardening.py` 仍直接导入 `web.routes.system_utils` 并调用 `_safe_next_url`；\n- `tests/test_source_merge_mode_constants.py` 仍直接读取 `core/services/scheduler/schedule_optimizer.py`、`freeze_window.py` 等旧根路径文件。\n\n而 plan 在任务 3 中已经明确：`_safe_next_url` 将迁出到 `web/routes/navigation_utils.py`，任务 3 完成后后续步骤只再引用迁移后路径；同时任务 3 的验证命令又要求立即执行 `tests/test_architecture_fitness.py`。这会导致任务 3 自身就出现“代码已迁移，但门禁/回归仍绑定旧路径”的断层。",
      "conclusionMarkdown": "目录计数与多数路径事实已对齐，但任务 3 之后的测试/门禁路径漂移治理仍未收口，当前 plan 还不能保证迁移后立即可验证。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 587,
          "lineEnd": 593,
          "excerptHash": "manual-m1-e1"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 607,
          "lineEnd": 610,
          "excerptHash": "manual-m1-e2"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 649,
          "lineEnd": 667,
          "excerptHash": "manual-m1-e3"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1270,
          "lineEnd": 1273,
          "excerptHash": "manual-m1-e4"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 44,
          "lineEnd": 70,
          "symbol": "_known_oversize_files",
          "excerptHash": "manual-m1-e5"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 404,
          "lineEnd": 449,
          "symbol": "test_no_silent_exception_swallow",
          "excerptHash": "manual-m1-e6"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 546,
          "lineEnd": 603,
          "symbol": "test_cyclomatic_complexity_threshold",
          "excerptHash": "manual-m1-e7"
        },
        {
          "path": "tests/regression_safe_next_url_hardening.py",
          "lineStart": 53,
          "lineEnd": 68,
          "symbol": "main",
          "excerptHash": "manual-m1-e8"
        },
        {
          "path": "tests/regression_safe_next_url_hardening.py",
          "lineStart": 82,
          "lineEnd": 83,
          "symbol": "main",
          "excerptHash": "manual-m1-e9"
        },
        {
          "path": "tests/test_source_merge_mode_constants.py",
          "lineStart": 92,
          "lineEnd": 99,
          "symbol": "test_target_files_have_no_source_merge_mode_quoted_literals",
          "excerptHash": "manual-m1-e10"
        },
        {
          "path": "web/routes/system_utils.py",
          "lineStart": 19,
          "lineEnd": 41,
          "symbol": "_safe_next_url",
          "excerptHash": "manual-m1-e11"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_safe_next_url_hardening.py"
        },
        {
          "path": "tests/test_source_merge_mode_constants.py"
        },
        {
          "path": "web/routes/system_utils.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "tests/test_architecture_fitness.py",
        "tests/regression_safe_next_url_hardening.py",
        "tests/test_source_merge_mode_constants.py",
        "web/routes/system_utils.py"
      ],
      "recommendedNextAction": "继续第二轮，深入核对调度主链兼容桥、结果对象边界与参数计数是否完全与 plan 一致。",
      "findingIds": [
        "plan-task3-path-sensitive-tests-gap"
      ]
    },
    {
      "id": "m2",
      "title": "第二轮：调度主链、兼容桥与结果边界核对",
      "status": "completed",
      "recordedAt": "2026-04-06T02:59:03.492Z",
      "summaryMarkdown": "已沿 `ScheduleService.run_schedule() -> collect_schedule_run_input() -> orchestrate_schedule_run() -> persist_schedule()` 主链逐段核对 plan 与代码现状。当前 plan 对以下事实描述是正确的：\n- `collect_schedule_run_input()` 当前确为 16 个入参（含 `svc`）；\n- `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_schedule_with_optional_strict_mode`、`_scheduler_accepts_strict_mode`、`_merge_summary_warnings` 都仍然存在；\n- `schedule_service.py` 返回值构建块确实仍对 `orchestration.summary` 做 7 处 `getattr(...)` 读取。\n\n但继续深挖后，plan 仍有四个关键断口：\n1. 只点名了 `_merge_summary_warnings`，却没有把 `schedule_orchestrator.py:_normalize_optimizer_outcome(...)` 纳入兼容桥清理范围；该函数当前仍对 `optimize_schedule()` 的返回对象做整块 `getattr/list/dict` 规范化，实际上仍是主链上的形态探测桥。\n2. `if best is None` 的最终归属仍然自相矛盾：任务 5 说任务 6 决定最终命运，但批次 2 退出条件又要求在任务 5/批次 2 结束时就删除或改成显式失败路径。\n3. `persist_schedule()` 的“22 个命名参数”说法仍未修正，实际定义与调用都只有 21 个关键字参数（`svc` 另算）。\n4. 删除 `_lookup_template_group_context` 旧回退时，plan 的验证命令漏掉了现有 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py`，该测试正是统一模板查找入口与结构化退化事件的直接护栏。",
      "conclusionMarkdown": "主链大方向已比旧版 plan 明确很多，但兼容桥边界、分支归属、参数计数与回归护栏仍有残留不一致，当前还不足以称为“执行者拿到即可无歧义开工”的版本。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 53,
          "lineEnd": 68,
          "symbol": "_normalize_optimizer_outcome",
          "excerptHash": "manual-m2-e1"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 71,
          "lineEnd": 100,
          "symbol": "_merge_summary_warnings",
          "excerptHash": "manual-m2-e2"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 549,
          "lineEnd": 582,
          "symbol": "optimize_schedule",
          "excerptHash": "manual-m2-e3"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py",
          "lineStart": 244,
          "lineEnd": 268,
          "symbol": "persist_schedule",
          "excerptHash": "manual-m2-e4"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 291,
          "lineEnd": 314,
          "symbol": "_run_schedule_impl",
          "excerptHash": "manual-m2-e5"
        },
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py",
          "lineStart": 24,
          "lineEnd": 51,
          "symbol": "test_schedule_input_builder_template_missing_surfaces_event",
          "excerptHash": "manual-m2-e6"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 785,
          "lineEnd": 792,
          "excerptHash": "manual-m2-e7"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 829,
          "lineEnd": 855,
          "excerptHash": "manual-m2-e8"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 858,
          "lineEnd": 872,
          "excerptHash": "manual-m2-e9"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 944,
          "lineEnd": 947,
          "excerptHash": "manual-m2-e10"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1427,
          "lineEnd": 1434,
          "excerptHash": "manual-m2-e11"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_persistence.py",
        "tests/regression_schedule_input_builder_template_missing_surfaces_event.py",
        ".limcode/plans/20260405_技术债务最终合并修复plan.md"
      ],
      "recommendedNextAction": "继续第三轮，收口质量门禁、`ruff` 规则、静默回退门禁与文案一致性。",
      "findingIds": [
        "plan-task5-misses-normalized-optimizer-outcome-bridge",
        "plan-task5-task6-best-none-ownership-conflict",
        "plan-persist-schedule-keyword-count-off-by-one",
        "plan-task5-misses-template-missing-regression"
      ]
    },
    {
      "id": "m3",
      "title": "第三轮：质量门禁与文案一致性核对",
      "status": "completed",
      "recordedAt": "2026-04-06T02:59:50.595Z",
      "summaryMarkdown": "第三轮聚焦质量门禁与文案自洽性。当前仓库的 `pyproject.toml` 已经把 `F401` 放在全局 `ignore` 中，同时又单独维护 `per-file-ignores`；而 plan 在任务 3 里把 side-effect 导入治理建立在 `per-file-ignores` 之上，却没有要求移除全局 `F401`。这意味着即使把 `scheduler.py`、`scheduler_pages.py` 等门面文件逐条写进 `per-file-ignores`，`ruff` 也依然不会对其他文件的未使用导入做约束，门禁会处于“看上去更精细、实际上仍全局放开”的状态。\n\n另外，plan 还残留少量文案级自洽问题：\n- 任务 4“实施前确认”列了 7 个配置规则文件，但下一步却写成“当前六个文件”；\n- “关键结构决策”第 3 点仍引用旧根路径 `core/services/scheduler/schedule_summary_degradation.py`，而任务 3 的目标目录与任务 5 的职责描述已经把它放到了 `core/services/scheduler/summary/` 子包。\n\n这些问题不如前两轮发现那样会直接打断主链，但会削弱 plan 作为唯一权威执行稿的严谨性。",
      "conclusionMarkdown": "第三轮确认：plan 在门禁设计上还有一个会实质失效的高优先级问题（全局 `F401` 忽略），并残留少量局部文案漂移；若不修正，执行阶段仍可能出现“规则已写、门禁不生效”的假收敛。",
      "evidence": [
        {
          "path": "pyproject.toml",
          "lineStart": 28,
          "lineEnd": 43,
          "excerptHash": "manual-m3-e1"
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 1,
          "lineEnd": 12,
          "excerptHash": "manual-m3-e2"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 643,
          "lineEnd": 647,
          "excerptHash": "manual-m3-e3"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 697,
          "lineEnd": 706,
          "excerptHash": "manual-m3-e4"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 177,
          "lineEnd": 182,
          "excerptHash": "manual-m3-e5"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 500,
          "lineEnd": 505,
          "excerptHash": "manual-m3-e6"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "pyproject.toml",
        ".pre-commit-config.yaml",
        ".limcode/plans/20260405_技术债务最终合并修复plan.md"
      ],
      "recommendedNextAction": "汇总三轮结论并给出最终是否可执行的判断，以及建议的最小修正清单。",
      "findingIds": [
        "plan-ruff-f401-global-ignore-undermines-per-file-gates",
        "plan-minor-self-consistency-drifts-remain"
      ]
    }
  ],
  "findings": [
    {
      "id": "plan-task3-path-sensitive-tests-gap",
      "severity": "high",
      "category": "test",
      "title": "任务 3 后的路径敏感测试未收口",
      "descriptionMarkdown": "plan 已要求任务 3 之后统一改用迁移后路径，并把 `_safe_next_url` 从 `web/routes/system_utils.py` 抽到 `web/routes/navigation_utils.py`；但现有 `tests/test_architecture_fitness.py`、`tests/regression_safe_next_url_hardening.py`、`tests/test_source_merge_mode_constants.py` 仍绑定旧根路径或旧符号归属。尤其任务 3 的验证命令本身就要求立即运行 `tests/test_architecture_fitness.py`，而该文件内含大量旧路径白名单，迁移后会先于任务 9 触发失败。当前 plan 对这批路径敏感测试的更新范围写得过窄，无法保证任务 3 完成后立刻可回归。",
      "recommendationMarkdown": "在任务 3 增加一个明确子步骤，按清单同步修正所有路径敏感门禁/回归：至少包含 `tests/test_architecture_fitness.py` 的全部路径白名单、`tests/regression_safe_next_url_hardening.py`、`tests/test_source_merge_mode_constants.py`、以及依赖源码路径的支撑脚本；否则任务 3 的验证命令会先于任务 9 失效。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 587,
          "lineEnd": 593,
          "excerptHash": "manual-m1-f1a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 607,
          "lineEnd": 610,
          "excerptHash": "manual-m1-f1b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 649,
          "lineEnd": 667,
          "excerptHash": "manual-m1-f1c"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 44,
          "lineEnd": 70,
          "symbol": "_known_oversize_files",
          "excerptHash": "manual-m1-f1d"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 404,
          "lineEnd": 449,
          "symbol": "test_no_silent_exception_swallow",
          "excerptHash": "manual-m1-f1e"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 546,
          "lineEnd": 603,
          "symbol": "test_cyclomatic_complexity_threshold",
          "excerptHash": "manual-m1-f1f"
        },
        {
          "path": "tests/regression_safe_next_url_hardening.py",
          "lineStart": 53,
          "lineEnd": 68,
          "symbol": "main",
          "excerptHash": "manual-m1-f1g"
        },
        {
          "path": "tests/test_source_merge_mode_constants.py",
          "lineStart": 92,
          "lineEnd": 99,
          "symbol": "test_target_files_have_no_source_merge_mode_quoted_literals",
          "excerptHash": "manual-m1-f1h"
        },
        {
          "path": "web/routes/system_utils.py",
          "lineStart": 19,
          "lineEnd": 41,
          "symbol": "_safe_next_url",
          "excerptHash": "manual-m1-f1i"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_safe_next_url_hardening.py"
        },
        {
          "path": "tests/test_source_merge_mode_constants.py"
        },
        {
          "path": "web/routes/system_utils.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-task5-misses-normalized-optimizer-outcome-bridge",
      "severity": "high",
      "category": "maintainability",
      "title": "任务 5 漏掉 `_normalize_optimizer_outcome` 兼容桥",
      "descriptionMarkdown": "plan 已把 `_merge_summary_warnings`、`_schedule_with_optional_strict_mode` 等兼容桥纳入任务 5，但 `schedule_orchestrator.py` 里真正位于主链入口处的 `_normalize_optimizer_outcome(...)` 仍未被纳入范围。当前 `orchestrate_schedule_run()` 先调用 `optimize_schedule_fn(...)`，再通过 `_normalize_optimizer_outcome()` 对 `results/summary/used_strategy/used_params/best_score/attempts/algo_stats` 等字段进行 `getattr/list/dict` 兼容性整形。只删除 `_merge_summary_warnings` 并不能真正收紧“优化器结果对象”的边界，主链仍然保留一整块形态探测逻辑。",
      "recommendationMarkdown": "把 `_normalize_optimizer_outcome()` 明确纳入任务 5：要么直接要求 `optimize_schedule()` 返回稳定 `OptimizationOutcome` 并删掉该整形层，要么改成显式契约校验并在失败时抛出可观测错误，而不是继续用 `getattr(...)` 静默兼容。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 53,
          "lineEnd": 68,
          "symbol": "_normalize_optimizer_outcome",
          "excerptHash": "manual-m2-f1a"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 103,
          "lineEnd": 129,
          "symbol": "orchestrate_schedule_run",
          "excerptHash": "manual-m2-f1b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 785,
          "lineEnd": 792,
          "excerptHash": "manual-m2-f1c"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 829,
          "lineEnd": 855,
          "excerptHash": "manual-m2-f1d"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-task5-task6-best-none-ownership-conflict",
      "severity": "high",
      "category": "other",
      "title": "`if best is None` 归属仍然冲突",
      "descriptionMarkdown": "plan 一方面在任务 5 中要求把 `_schedule_with_optional_strict_mode` 的导入、常规调用与 `if best is None` 分支同步收口，另一方面又在任务 6 中写明“本步只决定 `if best is None` 的最终命运”；更进一步，批次 2 退出条件已经要求在任务 5 / 批次 2 结束时让该分支“已删除或改为显式失败路径”。这让执行者无法判断：该分支到底应在任务 5 完成，还是允许保留到任务 6。",
      "recommendationMarkdown": "统一单一归属。更稳妥的写法是：任务 5 先把该分支改成显式失败路径并移除兼容函数依赖；任务 6 只在证明不可达后再删除分支。与此同时，把批次 2 退出条件与任务 6 文案同步成同一口径。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 549,
          "lineEnd": 582,
          "symbol": "optimize_schedule",
          "excerptHash": "manual-m2-f2a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 829,
          "lineEnd": 844,
          "excerptHash": "manual-m2-f2b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 944,
          "lineEnd": 947,
          "excerptHash": "manual-m2-f2c"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1427,
          "lineEnd": 1434,
          "excerptHash": "manual-m2-f2d"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-persist-schedule-keyword-count-off-by-one",
      "severity": "medium",
      "category": "other",
      "title": "`persist_schedule()` 参数计数仍偏 1",
      "descriptionMarkdown": "plan 多处把 `persist_schedule()` 描述成“22 个命名参数”，但当前 `schedule_persistence.py: persist_schedule()` 实际只有 21 个关键字参数（`cfg` 到 `time_cost_ms`），`svc` 是位置参数；`schedule_service.py` 的调用点也只传了 21 个关键字参数。这个计数偏差虽然不会直接改坏代码，但会让后续“拆到 RunContext + ScheduleOrchestrationOutcome”的核对标准继续漂移。",
      "recommendationMarkdown": "统一改成“21 个关键字参数（另加 `svc`）”，或直接改成“不再以参数个数做文案锚点，只列清字段归属”。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_persistence.py",
          "lineStart": 244,
          "lineEnd": 268,
          "symbol": "persist_schedule",
          "excerptHash": "manual-m2-f3a"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 291,
          "lineEnd": 314,
          "symbol": "_run_schedule_impl",
          "excerptHash": "manual-m2-f3b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 93,
          "lineEnd": 93,
          "excerptHash": "manual-m2-f3c"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 821,
          "lineEnd": 827,
          "excerptHash": "manual-m2-f3d"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1431,
          "lineEnd": 1433,
          "excerptHash": "manual-m2-f3e"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-task5-misses-template-missing-regression",
      "severity": "medium",
      "category": "test",
      "title": "任务 5 漏掉模板缺失退化回归",
      "descriptionMarkdown": "删除 `_lookup_template_group_context` 的旧 `_get_template_and_group_for_op` 回退后，除了 `regression_schedule_input_builder_safe_float_parse.py` 和 `...strict_hours_and_ext_days.py` 之外，现有 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py` 也会直接受影响。该测试专门验证统一模板查找入口在模板缺失时是否仍产出 `template_missing` 结构化退化事件，并保留 `merge_context_events` 与 `ext_days` 语义。当前 plan 没把它写进任务 5 的验证命令，存在遗漏。",
      "recommendationMarkdown": "把 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py` 补入任务 5 的实施前确认与验证命令，作为删除模板查找兼容桥后的必跑护栏。",
      "evidence": [
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py",
          "lineStart": 24,
          "lineEnd": 51,
          "symbol": "test_schedule_input_builder_template_missing_surfaces_event",
          "excerptHash": "manual-m2-f4a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 798,
          "lineEnd": 818,
          "excerptHash": "manual-m2-f4b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 858,
          "lineEnd": 872,
          "excerptHash": "manual-m2-f4c"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "tests/regression_schedule_input_builder_template_missing_surfaces_event.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-ruff-f401-global-ignore-undermines-per-file-gates",
      "severity": "high",
      "category": "maintainability",
      "title": "全局 `F401` 忽略会让门面白名单失效",
      "descriptionMarkdown": "当前 `pyproject.toml` 已全局忽略 `F401`，而 plan 又在任务 3 中要求把根层门面与迁移后的聚合文件逐条写入 `per-file-ignores`。如果不先移除全局 `F401`，这些 `per-file-ignores` 只是形式化登记，不会真正收紧 side-effect 导入边界，也无法达到“只有门面文件可豁免，其余文件必须被门禁拦住”的目标。",
      "recommendationMarkdown": "把“收紧 `ruff` 例外”写成两步：先移除全局 `F401` 忽略，再仅对批准的 side-effect 聚合文件保留 `per-file-ignores`。否则任务 3 的门禁设计不会真正生效。",
      "evidence": [
        {
          "path": "pyproject.toml",
          "lineStart": 28,
          "lineEnd": 43,
          "excerptHash": "manual-m3-f1a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 643,
          "lineEnd": 647,
          "excerptHash": "manual-m3-f1b"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-minor-self-consistency-drifts-remain",
      "severity": "low",
      "category": "docs",
      "title": "plan 仍有局部文案漂移",
      "descriptionMarkdown": "plan 还残留少量不会立刻改坏代码、但会削弱执行严谨性的内部漂移：任务 4 的“当前六个文件”与上文列举的 7 个文件不一致；关键结构决策第 3 点仍引用旧根路径 `core/services/scheduler/schedule_summary_degradation.py`，与任务 3 的子包目标路径和任务 5 的文件职责口径不一致。",
      "recommendationMarkdown": "统一把未来态路径写成迁移后的 canonical 路径，并把“六个文件”改为准确计数，避免执行者在细节处重新猜测。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 177,
          "lineEnd": 182,
          "excerptHash": "manual-m3-f2a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 500,
          "lineEnd": 505,
          "excerptHash": "manual-m3-f2b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 697,
          "lineEnd": 706,
          "excerptHash": "manual-m3-f2c"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:b58c29af646c687d0d2d307c8e0b5eb8fb40c5566c97dde94c275587da03bdc3",
    "generatedAt": "2026-04-06T03:01:16.193Z",
    "locale": "zh-CN"
  }
}
```

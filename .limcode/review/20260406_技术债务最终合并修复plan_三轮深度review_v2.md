# 20260406_技术债务最终合并修复plan_三轮深度review_v2
- 日期: 2026-04-06
- 概述: 对技术债务最终合并修复plan开展三轮深度审查，核对仓库事实、执行顺序、门禁设计与潜在静默回退风险。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 20260406 技术债务最终合并修复plan 三轮深度review v2

- 日期：2026-04-06
- 目标对象：`.limcode/plans/20260405_技术债务最终合并修复plan.md`
- review 目标：核对该 plan 是否能基于当前仓库事实落地，是否存在路径失真、执行断层、过度兜底、静默回退残留、验证口径失配与潜在 BUG。
- review 方法：分三轮进行——第一轮核对仓库事实与路径；第二轮核对任务依赖、门禁与验证闭环；第三轮核对优雅性、简洁性、潜在 BUG 与遗漏风险。

## 初始结论

待审查。

## 评审摘要

- 当前状态: 已完成
- 已审模块: 任务1 工程基线与质量门禁, 任务2 请求级服务装配与仓储束, 任务3 目录骨架与路由领域子包, 任务4 调度配置单一事实源, 任务5 排产主链上下文与兼容桥, 任务6 算法主流程与类型约束, 任务7 数据基础设施与 Gantt 热点, 任务8 页面组装、Excel 页面流程、模板树与前端协议, 任务9 测试目录重整与覆盖率口径, 任务10 文档、证据与审计轨道
- 当前进度: 已记录 3 个里程碑；最新：m3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 6
- 问题严重级别分布: 高 0 / 中 6 / 低 0
- 最新结论: 三轮核对后，`20260405_技术债务最终合并修复plan.md` 的总体方向、批次切分和大多数热点定位是成立的，尤其对请求级装配、调度主链兼容桥、`web/ui_mode.py` / `static_versioning.py`、数据库/备份热点与文档入口链的关注，基本贴合当前仓库事实。但它还不能直接作为“唯一权威实施计划”进入执行：当前至少还存在 6 个中等严重度缺口，分别落在 `web/bootstrap/` 治理清单、配置单一事实源范围、Gantt 服务层静默回退白名单归属、task8 试点页专项回归验收、task9 关键界面门禁迁移、task10 文档路径漂移自动校验上。若不先修正这些漏项，执行者可能出现“按计划完成并通过自带验证，但仓库里仍残留静默回退、测试治理断点或文档路径失真”的情况。因此，本 plan 当前适合视为高质量草案，而非最终单一事实源；建议先做一次定向修订，再进入真正实施。
- 下一步建议: 先按 review 发现修订 plan：补齐 task1 的 `factory.py:_maintenance_gate_response` 与 `web/bootstrap/paths.py:runtime_base_dir`，把 `schedule_summary_freeze.py` 与 `gantt_service.py` 残项并入 task4/task7，给 task8 增补试点页专项回归，给 task9 纳入 `regression_frontend_common_interactions.py` 与 `test_ui_mode.py`，并给 task10 增加文档路径漂移校验；完成这些后，再把修订版 plan 作为唯一权威实施计划。
- 总体结论: 需要后续跟进

## 评审发现

### bootstrap 启动链清单仍有漏项

- ID: bootstrap-governance-scope-still-incomplete
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  任务1已经把 `web/bootstrap/` 作为重点治理对象，但显式登记名单仍未覆盖 `factory.py:_maintenance_gate_response()` 与 `web/bootstrap/paths.py:runtime_base_dir()`。前者在维护窗口响应判定中仍有裸 `except Exception: pass`，后者在运行根目录解析失败时整段静默回退；这两个点都处于启动/请求装配关键路径。如果不并入治理台账和统一门禁，批次0结束后仍会残留未受控的静默回退，导致 plan 的“启动链静默回退治理闭环”结论不够严谨。
- 建议:

  把这两个函数补入任务1步骤5.5的显式清单、完成判定与专项门禁说明中，并要求与现有 `factory.py` 其余例外点采用同一台账格式管理。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:323-330`
  - `web/bootstrap/factory.py:124-133#_maintenance_gate_response`
  - `web/bootstrap/paths.py:14-25#runtime_base_dir`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `pyproject.toml`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/paths.py`

### 配置单一事实源遗漏摘要侧读取点

- ID: config-sss-misses-summary-readers
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  task4 的文件职责与实施步骤集中在配置服务、优化器与算法参数门面，但当前 `core/services/scheduler/schedule_summary_freeze.py` 仍直接用 `cfg_get()` 读取 `freeze_window_enabled/freeze_window_days`，并在 `int(...)` 失败时静默回退为 `0`。如果这个摘要侧读取点不并入 task4，那么冻结窗口相关字段仍会保留第二套读取/回退语义，plan 声称的“新增配置字段只需一处登记”“默认值、空值、数值规则只定义一次”就无法完全成立。
- 建议:

  把 `schedule_summary_freeze.py`（以及同类摘要侧配置消费点）显式补入 task4 范围，要求统一走注册表或统一配置读取门面，不再保留独立 `cfg_get()+int()` 回退语义。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:754-763`
  - `core/services/scheduler/schedule_summary_freeze.py:10-18#_cfg_freeze_window_state`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_summary_freeze.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/gantt_service.py`
  - `tests/test_architecture_fitness.py`

### Gantt 服务层静默回退仍无清零归属

- ID: gantt-service-fallback-whitelist-unassigned
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  task7 已经把 `gantt_critical_chain.py` 的 5 处异常治理列为显式步骤，但当前架构门禁白名单里还保留了 `core/services/scheduler/gantt_service.py:_critical_chain_cache_key` 与 `_get_critical_chain` 两个静默吞异常热点。plan 的 task7 没有为这两个既有白名单提供清零步骤或后续任务归属，导致 Gantt 领域在 task7 完成后仍会残留已知 `pass/continue` 型静默回退，与 plan 自己提出的“少兜底、少静默回退”目标不完全一致。
- 建议:

  在 task7 中增加 `gantt_service.py` 的缓存键/缓存写回静默回退治理，或至少把这两个白名单明确绑定到 task7 的完成判定与专项回归中，避免成为未分配残项。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1113-1120`
  - `tests/test_architecture_fitness.py:435-438#test_no_silent_exception_swallow`
  - `core/services/scheduler/gantt_service.py:97-156`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_summary_freeze.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/gantt_service.py`
  - `tests/test_architecture_fitness.py`

### 试点页重构未绑定现成路由专项回归

- ID: excel-pageflow-pilot-validation-misses-route-tests
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m3
- 说明:

  task8 明确把 `scheduler_excel_calendar.py` 与 `process_excel_part_operation_hours.py` 作为首批试点页面，但其验证命令只跑通用 Excel/模板/UI 测试，没有把当前仓库中已经存在的试点页专项回归纳入执行。现有测试已经覆盖执行器接线、严格数值、导入语义、源行号与 append 语义等页面特有行为；若 pageflow 骨架重构后不把这些现成测试纳入 task8 验收，就无法覆盖 plan 自己在“实施前确认”里点名的差异点，容易出现骨架通过而页面特性回归失守。
- 建议:

  把这几条现成的试点页专项回归显式并入 task8 的验证命令或完成判定；如果后续会迁目录，可在 task8 中先写“当前路径/迁移后路径二选一”的执行约定，但不能遗漏页面特有测试。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1196-1215`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1292-1304`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py:11-16#find_repo_root`
  - `tests/regression_scheduler_excel_calendar_strict_numeric.py:1-5`
  - `tests/regression_process_excel_part_operation_hours_import.py:8-13#find_repo_root`
  - `tests/regression_process_excel_part_operation_hours_source_row_num.py:10-15#find_repo_root`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/bootstrap/static_versioning.py`
  - `web/ui_mode.py`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py`
  - `tests/regression_scheduler_excel_calendar_strict_numeric.py`
  - `tests/regression_process_excel_part_operation_hours_import.py`
  - `tests/regression_process_excel_part_operation_hours_source_row_num.py`
  - `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`
  - `tests/regression_frontend_common_interactions.py`
  - `tests/test_ui_mode.py`
  - `tests/check_quickref_vs_routes.py`
  - `开发文档/系统速查表.md`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `evidence/README.md`
  - `开发文档/开发文档.md`
  - `AGENTS.md`
  - `plugins/README.md`
  - `installer/README_WIN7_INSTALLER.md`

### 测试目录重整遗漏关键界面门禁

- ID: task9-misses-ui-contract-gates
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m3
- 说明:

  task8 的验证仍直接依赖 `tests/regression_frontend_common_interactions.py` 与 `tests/test_ui_mode.py` 两条关键界面门禁，但 task9 的首批迁移与共享路径辅助覆盖范围并没有把它们纳入。前者还是根层脚本式回归，并继续使用 `os.path.join(here, "..")` 的固定父级仓库根定位；后者则是 `web/ui_mode.py` 运行时编排层的直接回归。这样会导致 task8 的关键界面契约在 task9 完成后仍停留在根层旧形态，削弱“本轮直接触达区域已有分层回归入口”的治理闭环。
- 建议:

  把这两条测试至少纳入 task9 的首批迁移/归位范围；其中 `regression_frontend_common_interactions.py` 还应同步切到共享仓库根辅助，避免它在进入子目录后再次失效。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1298-1301`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1333-1398`
  - `tests/regression_frontend_common_interactions.py:7-10#_find_repo_root`
  - `tests/test_ui_mode.py:206-241`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/bootstrap/static_versioning.py`
  - `web/ui_mode.py`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py`
  - `tests/regression_scheduler_excel_calendar_strict_numeric.py`
  - `tests/regression_process_excel_part_operation_hours_import.py`
  - `tests/regression_process_excel_part_operation_hours_source_row_num.py`
  - `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`
  - `tests/regression_frontend_common_interactions.py`
  - `tests/test_ui_mode.py`
  - `tests/check_quickref_vs_routes.py`
  - `开发文档/系统速查表.md`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `evidence/README.md`
  - `开发文档/开发文档.md`
  - `AGENTS.md`
  - `plugins/README.md`
  - `installer/README_WIN7_INSTALLER.md`

### 文档路径漂移缺少自动校验

- ID: doc-path-drift-lacks-automated-validation
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: m3
- 说明:

  task10 要求把 `开发文档/系统速查表.md` 中真实存在的路由、入口、目录、脚本路径同步进去，但它的验证命令只跑 `check_quickref_vs_routes.py` 的 HTTP 接口对比和 README 链接断言。当前 `系统速查表.md` 已经存在 `web/routes/*.py`、`web/routes/scheduler.py` 等旧路径描述，而 `check_quickref_vs_routes.py` 只解析文档里的 `GET/POST` 接口，再与 Flask `url_map` 比较，根本不会校验这些文件路径/模块路径是否仍真实存在。因此 task10 按现有验证全部通过后，文档路径漂移依旧可能残留。
- 建议:

  新增一个轻量文档漂移校验：至少对 `系统速查表.md` 中显式列出的关键文件/目录路径做存在性检查，或扩展 `check_quickref_vs_routes.py` 让它同时核对文档中的模块路径与任务3/8迁移后的真实文件位置。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1461-1490`
  - `tests/check_quickref_vs_routes.py:21-23#main`
  - `tests/check_quickref_vs_routes.py:41-52#main`
  - `开发文档/系统速查表.md:47-60`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/bootstrap/static_versioning.py`
  - `web/ui_mode.py`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py`
  - `tests/regression_scheduler_excel_calendar_strict_numeric.py`
  - `tests/regression_process_excel_part_operation_hours_import.py`
  - `tests/regression_process_excel_part_operation_hours_source_row_num.py`
  - `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`
  - `tests/regression_frontend_common_interactions.py`
  - `tests/test_ui_mode.py`
  - `tests/check_quickref_vs_routes.py`
  - `开发文档/系统速查表.md`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `evidence/README.md`
  - `开发文档/开发文档.md`
  - `AGENTS.md`
  - `plugins/README.md`
  - `installer/README_WIN7_INSTALLER.md`

## 评审里程碑

### m1 · 第一轮：基线事实、任务1-3与目录/装配策略核对

- 状态: 已完成
- 记录时间: 2026-04-06T07:37:50.463Z
- 已审模块: 任务1 工程基线与质量门禁, 任务2 请求级服务装配与仓储束, 任务3 目录骨架与路由领域子包
- 摘要:

  已核对批次0-1相关事实。当前仓库确实缺少 `README.md`、`开发文档/README.md`、`audit/README.md`、`开发文档/技术债务治理台账.md`、`scripts/run_quality_gate.py`、`.github/workflows/quality.yml` 与 `tests/regression/`，说明任务1的工程基线补齐方向成立；`requirements-dev.txt` 仅有 `pytest`，`.pre-commit-config.yaml` 仍直接调用裸 `ruff`，`pyproject.toml` 仍保留全局 `F401` 与非递归 `tests/*`，说明任务1的依赖/门禁调整具备直接依据。任务2的 185 处 `Service/Repository(g.db, ...)` 命中、`scheduler_config.py` 的 6 处直接装配、`ScheduleService.__init__` 内部平铺创建 10 个仓储实例、以及 `_safe_next_url` 仍位于 `web/routes/system_utils.py` 的事实，与 plan 描述一致。总体上，批次0-1的大方向是对的，且执行顺序也基本克制。

  但同时发现一个仍会影响“静默回退治理闭环”的缺口：任务1对 `web/bootstrap/` 的显式治理清单仍不完整。plan 已覆盖 `_open_db/_close_db/_perf_headers`、`plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py`、`static_versioning.py`，但当前实际启动链中还存在 `factory.py:_maintenance_gate_response()` 的裸 `except Exception: pass`，以及 `web/bootstrap/paths.py:runtime_base_dir()` 的整段静默回退。这两个点既属于请求装配/启动路径，又不在任务1的明确登记名单里；若不补入治理台账与统一门禁，任务1完成后仍会留下未受控的启动期静默回退。
- 结论:

  批次0-1的大方向正确，但任务1的 `web/bootstrap/` 例外清单还需补齐到 `factory.py:_maintenance_gate_response` 与 `web/bootstrap/paths.py:runtime_base_dir`，否则“启动链静默回退已纳入统一治理”的完成判定并不严谨。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:323-330`
  - `requirements-dev.txt:1-4`
  - `.pre-commit-config.yaml:5-10`
  - `pyproject.toml:28-43`
  - `web/bootstrap/factory.py:124-133#_maintenance_gate_response`
  - `web/bootstrap/paths.py:14-25#runtime_base_dir`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `pyproject.toml`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/paths.py`
- 下一步建议:

  继续第二轮，重点核对任务4-7对主链兼容桥、Gantt 静默回退与数据基础设施热点的覆盖是否完整。
- 问题:
  - [中] 可维护性: bootstrap 启动链清单仍有漏项

### m2 · 第二轮：任务4-7主链、配置与数据/甘特治理核对

- 状态: 已完成
- 记录时间: 2026-04-06T07:38:47.679Z
- 已审模块: 任务4 调度配置单一事实源, 任务5 排产主链上下文与兼容桥, 任务6 算法主流程与类型约束, 任务7 数据基础设施与 Gantt 热点
- 摘要:

  已核对任务4-7与当前实现的对应关系。优点是，task4 对 `schedule_optimizer.py` / `schedule_optimizer_steps.py` 的 `_cfg_value`、`_norm_text`、本地闭包清理要求，task5 对 `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_lookup_template_group_context` 旧回退、`_schedule_with_optional_strict_mode`、`_normalize_optimizer_outcome()`、`persist_schedule()` 21 个关键字参数与 `orchestration.summary` 防御性 `getattr(...)` 的收口，基本都准确命中当前代码中的真实热点；task7 对 `database.py`、`backup.py`、`schedule_repo.py` 三类热点的拆分方向也与现状一致。

  但第二轮发现两个仍会削弱目标达成度的覆盖缺口：

  1. task4 想建立“调度配置单一事实源”，却没有把摘要侧仍在自行解析配置的 `core/services/scheduler/schedule_summary_freeze.py` 纳入范围。当前 `_cfg_freeze_window_state()` 仍直接 `cfg_get()` + `int(...)`，失败就静默回退为 `0`；如果 task4 只改配置服务、优化器与参数门面，不改这个摘要侧读者，那么 `freeze_window_enabled/freeze_window_days` 仍会保留第二套读取语义，plan 的“新增配置字段只需一处登记”与“默认值/空值/数值规则只定义一次”结论无法完全成立。

  2. task7 把 Gantt 读查询退化治理聚焦在 `gantt_critical_chain.py`，这一步当然必要；但当前架构门禁白名单里还明确登记了 `core/services/scheduler/gantt_service.py:_critical_chain_cache_key` 与 `_get_critical_chain` 的静默吞异常，而 plan 的 task7 并未给出这两个既有白名单的清零归属。也就是说，即使 `gantt_critical_chain.py` 的 5 个异常都治理完，Gantt 主服务层仍会保留未分配的 `pass/continue` 型静默回退，无法完全满足 plan 自己提出的“少兜底、少静默回退”目标。
- 结论:

  批次2-3对主链兼容桥与数据基础设施热点的命中度较高，但 task4 还需把 `schedule_summary_freeze.py` 这类摘要侧配置读取点纳入单一事实源治理，task7 还需显式接管 `gantt_service.py` 已登记的静默吞异常白名单，否则配置语义与 Gantt 静默回退都还会残留尾项。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:754-763`
  - `core/services/scheduler/schedule_summary_freeze.py:10-18#_cfg_freeze_window_state`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1113-1120`
  - `tests/test_architecture_fitness.py:435-438#test_no_silent_exception_swallow`
  - `core/services/scheduler/gantt_service.py:97-156`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_summary_freeze.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/gantt_service.py`
  - `tests/test_architecture_fitness.py`
- 下一步建议:

  进入第三轮，核对任务8-10的界面、测试与文档轨道是否仍存在覆盖不足或执行后仍无法达成最终目标的地方。
- 问题:
  - [中] 可维护性: 配置单一事实源遗漏摘要侧读取点
  - [中] 可维护性: Gantt 服务层静默回退仍无清零归属

### m3 · 第三轮：任务8-10界面、测试与文档闭环核对

- 状态: 已完成
- 记录时间: 2026-04-06T07:45:39.171Z
- 已审模块: 任务8 页面组装、Excel 页面流程、模板树与前端协议, 任务9 测试目录重整与覆盖率口径, 任务10 文档、证据与审计轨道
- 摘要:

  已完成对任务8-10的第三轮核对。总体判断是：task8 对 `web/bootstrap/static_versioning.py`、`web/ui_mode.py`、`templates/system/logs.html`、`templates/system/backup.html` 的命中是准确的，尤其对 `_mtime_version()` / `_versioned_url_for()` / `install_versioned_url_for()` 的静默吞异常、`ui_v2_static` 初始化顺序、以及两张系统页的行内 `<script defer>`，都抓到了当前真实问题；task10 对根入口链、`开发文档/开发文档.md` 归档化、`系统速查表.md` 路径校正、`evidence/README.md` 与 `audit/README.md` 职责分离的方向也成立。

  但第三轮确认，plan 还存在三个会影响“能否作为单一权威实施计划”成立的收口缺口：

  1. task8 选择 `scheduler_excel_calendar.py` 与 `process_excel_part_operation_hours.py` 作为首批试点页面，这是合理的；但它的验证命令没有把当前仓库里已经存在的试点页专项回归纳入执行。现在仓库里已有 `tests/regression_scheduler_excel_calendar_uses_executor.py`、`tests/regression_scheduler_excel_calendar_strict_numeric.py`、`tests/regression_process_excel_part_operation_hours_import.py`、`tests/regression_process_excel_part_operation_hours_source_row_num.py`、`tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py` 等直接针对这两条页面链路的测试。若 pageflow 骨架重构后只跑通用预览/确认测试，而不跑这些页面特有回归，就无法覆盖 task8 在“实施前确认”里自己点名的模式限制、额外基线状态、预览后行状态改写与导入语义差异。

  2. task9 要重整测试目录与路径治理，但它遗漏了 task8 自己还在依赖的两条界面门禁：`tests/regression_frontend_common_interactions.py` 与 `tests/test_ui_mode.py`。前者是根层脚本式回归，且仍用 `os.path.join(here, "..")` 找仓库根；后者是 `web/ui_mode.py` 运行时行为的直接回归。也就是说，task8 的关键界面契约测试仍停留在根层旧形态，task9 却没有把它们纳入首批迁移或最少目录归位范围，这会削弱“本轮直接触达区域已有分层回归入口”的结论。

  3. task10 虽然要求校正 `开发文档/系统速查表.md` 中真实存在的路由、入口、目录、脚本路径，但它的验证命令只检查 `check_quickref_vs_routes.py` 的 HTTP 接口对比与 README 链接存在性。当前 `系统速查表.md` 已经明确写着 `web/routes/*.py`、`web/routes/scheduler.py` 这类旧路径描述；而 `check_quickref_vs_routes.py` 只比对文档中的 `GET/POST` 接口是否与 `url_map` 一致，根本不会验证这些文件路径/模块路径是否还真实存在。因此 task10 即使按现有验证命令全部通过，也仍可能保留文档路径漂移。

  另外，从优雅性看，task8 的“统一页面装配边界”步骤应更克制地区分“已基本达标的 route”与“仍需重构的 route”：当前 `web/routes/scheduler_analysis.py` 已经把页面上下文装配主要委托给 `build_analysis_context(...)`，不宜与 `system_logs.py` 按同一重构重量对待，否则容易制造不必要搬动。
- 结论:

  批次4-6在真实问题命中度上仍然较高，但当前 plan 还不能直接作为唯一权威实施计划：task8 需要把首批试点页专项回归纳入验收，task9 需要接管仍留在根层的关键界面门禁，task10 需要补上文档文件路径/模块路径漂移的自动校验，否则界面链路、测试治理与文档治理三处都会留下“通过了计划自带验证，但仍可能残留失真”的空档。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1196-1215`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1292-1304`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py:11-16#find_repo_root`
  - `tests/regression_scheduler_excel_calendar_strict_numeric.py:1-5`
  - `tests/regression_process_excel_part_operation_hours_import.py:8-13#find_repo_root`
  - `tests/regression_process_excel_part_operation_hours_source_row_num.py:10-15#find_repo_root`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1333-1398`
  - `tests/regression_frontend_common_interactions.py:7-10#_find_repo_root`
  - `tests/test_ui_mode.py:206-241`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1461-1490`
  - `tests/check_quickref_vs_routes.py:21-23#main`
  - `tests/check_quickref_vs_routes.py:41-52#main`
  - `开发文档/系统速查表.md:47-60`
  - `web/routes/scheduler_analysis.py:22-35#analysis_page`
  - `web/routes/system_logs.py:29-67#logs_page`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/bootstrap/static_versioning.py`
  - `web/ui_mode.py`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py`
  - `tests/regression_scheduler_excel_calendar_strict_numeric.py`
  - `tests/regression_process_excel_part_operation_hours_import.py`
  - `tests/regression_process_excel_part_operation_hours_source_row_num.py`
  - `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`
  - `tests/regression_frontend_common_interactions.py`
  - `tests/test_ui_mode.py`
  - `tests/check_quickref_vs_routes.py`
  - `开发文档/系统速查表.md`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `evidence/README.md`
  - `开发文档/开发文档.md`
  - `AGENTS.md`
  - `plugins/README.md`
  - `installer/README_WIN7_INSTALLER.md`
- 下一步建议:

  基于三轮结论修订 plan：补齐 task1/task4/task7/task8/task9/task10 的具体漏项与验证口径后，再把该 plan 视为唯一权威实施计划。
- 问题:
  - [中] 测试: 试点页重构未绑定现成路由专项回归
  - [中] 测试: 测试目录重整遗漏关键界面门禁
  - [中] 文档: 文档路径漂移缺少自动校验

## 最终结论

三轮核对后，`20260405_技术债务最终合并修复plan.md` 的总体方向、批次切分和大多数热点定位是成立的，尤其对请求级装配、调度主链兼容桥、`web/ui_mode.py` / `static_versioning.py`、数据库/备份热点与文档入口链的关注，基本贴合当前仓库事实。但它还不能直接作为“唯一权威实施计划”进入执行：当前至少还存在 6 个中等严重度缺口，分别落在 `web/bootstrap/` 治理清单、配置单一事实源范围、Gantt 服务层静默回退白名单归属、task8 试点页专项回归验收、task9 关键界面门禁迁移、task10 文档路径漂移自动校验上。若不先修正这些漏项，执行者可能出现“按计划完成并通过自带验证，但仓库里仍残留静默回退、测试治理断点或文档路径失真”的情况。因此，本 plan 当前适合视为高质量草案，而非最终单一事实源；建议先做一次定向修订，再进入真正实施。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnmvhm7j-vugd7g",
  "createdAt": "2026-04-06T00:00:00.000Z",
  "updatedAt": "2026-04-06T07:45:55.990Z",
  "finalizedAt": "2026-04-06T07:45:55.990Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260406_技术债务最终合并修复plan_三轮深度review_v2",
    "date": "2026-04-06",
    "overview": "对技术债务最终合并修复plan开展三轮深度审查，核对仓库事实、执行顺序、门禁设计与潜在静默回退风险。"
  },
  "scope": {
    "markdown": "# 20260406 技术债务最终合并修复plan 三轮深度review v2\n\n- 日期：2026-04-06\n- 目标对象：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n- review 目标：核对该 plan 是否能基于当前仓库事实落地，是否存在路径失真、执行断层、过度兜底、静默回退残留、验证口径失配与潜在 BUG。\n- review 方法：分三轮进行——第一轮核对仓库事实与路径；第二轮核对任务依赖、门禁与验证闭环；第三轮核对优雅性、简洁性、潜在 BUG 与遗漏风险。\n\n## 初始结论\n\n待审查。"
  },
  "summary": {
    "latestConclusion": "三轮核对后，`20260405_技术债务最终合并修复plan.md` 的总体方向、批次切分和大多数热点定位是成立的，尤其对请求级装配、调度主链兼容桥、`web/ui_mode.py` / `static_versioning.py`、数据库/备份热点与文档入口链的关注，基本贴合当前仓库事实。但它还不能直接作为“唯一权威实施计划”进入执行：当前至少还存在 6 个中等严重度缺口，分别落在 `web/bootstrap/` 治理清单、配置单一事实源范围、Gantt 服务层静默回退白名单归属、task8 试点页专项回归验收、task9 关键界面门禁迁移、task10 文档路径漂移自动校验上。若不先修正这些漏项，执行者可能出现“按计划完成并通过自带验证，但仓库里仍残留静默回退、测试治理断点或文档路径失真”的情况。因此，本 plan 当前适合视为高质量草案，而非最终单一事实源；建议先做一次定向修订，再进入真正实施。",
    "recommendedNextAction": "先按 review 发现修订 plan：补齐 task1 的 `factory.py:_maintenance_gate_response` 与 `web/bootstrap/paths.py:runtime_base_dir`，把 `schedule_summary_freeze.py` 与 `gantt_service.py` 残项并入 task4/task7，给 task8 增补试点页专项回归，给 task9 纳入 `regression_frontend_common_interactions.py` 与 `test_ui_mode.py`，并给 task10 增加文档路径漂移校验；完成这些后，再把修订版 plan 作为唯一权威实施计划。",
    "reviewedModules": [
      "任务1 工程基线与质量门禁",
      "任务2 请求级服务装配与仓储束",
      "任务3 目录骨架与路由领域子包",
      "任务4 调度配置单一事实源",
      "任务5 排产主链上下文与兼容桥",
      "任务6 算法主流程与类型约束",
      "任务7 数据基础设施与 Gantt 热点",
      "任务8 页面组装、Excel 页面流程、模板树与前端协议",
      "任务9 测试目录重整与覆盖率口径",
      "任务10 文档、证据与审计轨道"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 6,
    "severity": {
      "high": 0,
      "medium": 6,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1",
      "title": "第一轮：基线事实、任务1-3与目录/装配策略核对",
      "status": "completed",
      "recordedAt": "2026-04-06T07:37:50.463Z",
      "summaryMarkdown": "已核对批次0-1相关事实。当前仓库确实缺少 `README.md`、`开发文档/README.md`、`audit/README.md`、`开发文档/技术债务治理台账.md`、`scripts/run_quality_gate.py`、`.github/workflows/quality.yml` 与 `tests/regression/`，说明任务1的工程基线补齐方向成立；`requirements-dev.txt` 仅有 `pytest`，`.pre-commit-config.yaml` 仍直接调用裸 `ruff`，`pyproject.toml` 仍保留全局 `F401` 与非递归 `tests/*`，说明任务1的依赖/门禁调整具备直接依据。任务2的 185 处 `Service/Repository(g.db, ...)` 命中、`scheduler_config.py` 的 6 处直接装配、`ScheduleService.__init__` 内部平铺创建 10 个仓储实例、以及 `_safe_next_url` 仍位于 `web/routes/system_utils.py` 的事实，与 plan 描述一致。总体上，批次0-1的大方向是对的，且执行顺序也基本克制。\n\n但同时发现一个仍会影响“静默回退治理闭环”的缺口：任务1对 `web/bootstrap/` 的显式治理清单仍不完整。plan 已覆盖 `_open_db/_close_db/_perf_headers`、`plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py`、`static_versioning.py`，但当前实际启动链中还存在 `factory.py:_maintenance_gate_response()` 的裸 `except Exception: pass`，以及 `web/bootstrap/paths.py:runtime_base_dir()` 的整段静默回退。这两个点既属于请求装配/启动路径，又不在任务1的明确登记名单里；若不补入治理台账与统一门禁，任务1完成后仍会留下未受控的启动期静默回退。",
      "conclusionMarkdown": "批次0-1的大方向正确，但任务1的 `web/bootstrap/` 例外清单还需补齐到 `factory.py:_maintenance_gate_response` 与 `web/bootstrap/paths.py:runtime_base_dir`，否则“启动链静默回退已纳入统一治理”的完成判定并不严谨。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 323,
          "lineEnd": 330,
          "excerptHash": "na"
        },
        {
          "path": "requirements-dev.txt",
          "lineStart": 1,
          "lineEnd": 4,
          "excerptHash": "na"
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 5,
          "lineEnd": 10,
          "excerptHash": "na"
        },
        {
          "path": "pyproject.toml",
          "lineStart": 28,
          "lineEnd": 43,
          "excerptHash": "na"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 124,
          "lineEnd": 133,
          "symbol": "_maintenance_gate_response",
          "excerptHash": "na"
        },
        {
          "path": "web/bootstrap/paths.py",
          "lineStart": 14,
          "lineEnd": 25,
          "symbol": "runtime_base_dir",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/paths.py"
        }
      ],
      "reviewedModules": [
        "任务1 工程基线与质量门禁",
        "任务2 请求级服务装配与仓储束",
        "任务3 目录骨架与路由领域子包"
      ],
      "recommendedNextAction": "继续第二轮，重点核对任务4-7对主链兼容桥、Gantt 静默回退与数据基础设施热点的覆盖是否完整。",
      "findingIds": [
        "bootstrap-governance-scope-still-incomplete"
      ]
    },
    {
      "id": "m2",
      "title": "第二轮：任务4-7主链、配置与数据/甘特治理核对",
      "status": "completed",
      "recordedAt": "2026-04-06T07:38:47.679Z",
      "summaryMarkdown": "已核对任务4-7与当前实现的对应关系。优点是，task4 对 `schedule_optimizer.py` / `schedule_optimizer_steps.py` 的 `_cfg_value`、`_norm_text`、本地闭包清理要求，task5 对 `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_lookup_template_group_context` 旧回退、`_schedule_with_optional_strict_mode`、`_normalize_optimizer_outcome()`、`persist_schedule()` 21 个关键字参数与 `orchestration.summary` 防御性 `getattr(...)` 的收口，基本都准确命中当前代码中的真实热点；task7 对 `database.py`、`backup.py`、`schedule_repo.py` 三类热点的拆分方向也与现状一致。\n\n但第二轮发现两个仍会削弱目标达成度的覆盖缺口：\n\n1. task4 想建立“调度配置单一事实源”，却没有把摘要侧仍在自行解析配置的 `core/services/scheduler/schedule_summary_freeze.py` 纳入范围。当前 `_cfg_freeze_window_state()` 仍直接 `cfg_get()` + `int(...)`，失败就静默回退为 `0`；如果 task4 只改配置服务、优化器与参数门面，不改这个摘要侧读者，那么 `freeze_window_enabled/freeze_window_days` 仍会保留第二套读取语义，plan 的“新增配置字段只需一处登记”与“默认值/空值/数值规则只定义一次”结论无法完全成立。\n\n2. task7 把 Gantt 读查询退化治理聚焦在 `gantt_critical_chain.py`，这一步当然必要；但当前架构门禁白名单里还明确登记了 `core/services/scheduler/gantt_service.py:_critical_chain_cache_key` 与 `_get_critical_chain` 的静默吞异常，而 plan 的 task7 并未给出这两个既有白名单的清零归属。也就是说，即使 `gantt_critical_chain.py` 的 5 个异常都治理完，Gantt 主服务层仍会保留未分配的 `pass/continue` 型静默回退，无法完全满足 plan 自己提出的“少兜底、少静默回退”目标。",
      "conclusionMarkdown": "批次2-3对主链兼容桥与数据基础设施热点的命中度较高，但 task4 还需把 `schedule_summary_freeze.py` 这类摘要侧配置读取点纳入单一事实源治理，task7 还需显式接管 `gantt_service.py` 已登记的静默吞异常白名单，否则配置语义与 Gantt 静默回退都还会残留尾项。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 754,
          "lineEnd": 763,
          "excerptHash": "na"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py",
          "lineStart": 10,
          "lineEnd": 18,
          "symbol": "_cfg_freeze_window_state",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1113,
          "lineEnd": 1120,
          "excerptHash": "na"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 435,
          "lineEnd": 438,
          "symbol": "test_no_silent_exception_swallow",
          "excerptHash": "na"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 97,
          "lineEnd": 156,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "reviewedModules": [
        "任务4 调度配置单一事实源",
        "任务5 排产主链上下文与兼容桥",
        "任务6 算法主流程与类型约束",
        "任务7 数据基础设施与 Gantt 热点"
      ],
      "recommendedNextAction": "进入第三轮，核对任务8-10的界面、测试与文档轨道是否仍存在覆盖不足或执行后仍无法达成最终目标的地方。",
      "findingIds": [
        "config-sss-misses-summary-readers",
        "gantt-service-fallback-whitelist-unassigned"
      ]
    },
    {
      "id": "m3",
      "title": "第三轮：任务8-10界面、测试与文档闭环核对",
      "status": "completed",
      "recordedAt": "2026-04-06T07:45:39.171Z",
      "summaryMarkdown": "已完成对任务8-10的第三轮核对。总体判断是：task8 对 `web/bootstrap/static_versioning.py`、`web/ui_mode.py`、`templates/system/logs.html`、`templates/system/backup.html` 的命中是准确的，尤其对 `_mtime_version()` / `_versioned_url_for()` / `install_versioned_url_for()` 的静默吞异常、`ui_v2_static` 初始化顺序、以及两张系统页的行内 `<script defer>`，都抓到了当前真实问题；task10 对根入口链、`开发文档/开发文档.md` 归档化、`系统速查表.md` 路径校正、`evidence/README.md` 与 `audit/README.md` 职责分离的方向也成立。\n\n但第三轮确认，plan 还存在三个会影响“能否作为单一权威实施计划”成立的收口缺口：\n\n1. task8 选择 `scheduler_excel_calendar.py` 与 `process_excel_part_operation_hours.py` 作为首批试点页面，这是合理的；但它的验证命令没有把当前仓库里已经存在的试点页专项回归纳入执行。现在仓库里已有 `tests/regression_scheduler_excel_calendar_uses_executor.py`、`tests/regression_scheduler_excel_calendar_strict_numeric.py`、`tests/regression_process_excel_part_operation_hours_import.py`、`tests/regression_process_excel_part_operation_hours_source_row_num.py`、`tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py` 等直接针对这两条页面链路的测试。若 pageflow 骨架重构后只跑通用预览/确认测试，而不跑这些页面特有回归，就无法覆盖 task8 在“实施前确认”里自己点名的模式限制、额外基线状态、预览后行状态改写与导入语义差异。\n\n2. task9 要重整测试目录与路径治理，但它遗漏了 task8 自己还在依赖的两条界面门禁：`tests/regression_frontend_common_interactions.py` 与 `tests/test_ui_mode.py`。前者是根层脚本式回归，且仍用 `os.path.join(here, \"..\")` 找仓库根；后者是 `web/ui_mode.py` 运行时行为的直接回归。也就是说，task8 的关键界面契约测试仍停留在根层旧形态，task9 却没有把它们纳入首批迁移或最少目录归位范围，这会削弱“本轮直接触达区域已有分层回归入口”的结论。\n\n3. task10 虽然要求校正 `开发文档/系统速查表.md` 中真实存在的路由、入口、目录、脚本路径，但它的验证命令只检查 `check_quickref_vs_routes.py` 的 HTTP 接口对比与 README 链接存在性。当前 `系统速查表.md` 已经明确写着 `web/routes/*.py`、`web/routes/scheduler.py` 这类旧路径描述；而 `check_quickref_vs_routes.py` 只比对文档中的 `GET/POST` 接口是否与 `url_map` 一致，根本不会验证这些文件路径/模块路径是否还真实存在。因此 task10 即使按现有验证命令全部通过，也仍可能保留文档路径漂移。\n\n另外，从优雅性看，task8 的“统一页面装配边界”步骤应更克制地区分“已基本达标的 route”与“仍需重构的 route”：当前 `web/routes/scheduler_analysis.py` 已经把页面上下文装配主要委托给 `build_analysis_context(...)`，不宜与 `system_logs.py` 按同一重构重量对待，否则容易制造不必要搬动。",
      "conclusionMarkdown": "批次4-6在真实问题命中度上仍然较高，但当前 plan 还不能直接作为唯一权威实施计划：task8 需要把首批试点页专项回归纳入验收，task9 需要接管仍留在根层的关键界面门禁，task10 需要补上文档文件路径/模块路径漂移的自动校验，否则界面链路、测试治理与文档治理三处都会留下“通过了计划自带验证，但仍可能残留失真”的空档。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1196,
          "lineEnd": 1215,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1292,
          "lineEnd": 1304,
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py",
          "lineStart": 11,
          "lineEnd": 16,
          "symbol": "find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_strict_numeric.py",
          "lineStart": 1,
          "lineEnd": 5,
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_import.py",
          "lineStart": 8,
          "lineEnd": 13,
          "symbol": "find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_source_row_num.py",
          "lineStart": 10,
          "lineEnd": 15,
          "symbol": "find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1333,
          "lineEnd": 1398,
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py",
          "lineStart": 7,
          "lineEnd": 10,
          "symbol": "_find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": "tests/test_ui_mode.py",
          "lineStart": 206,
          "lineEnd": 241,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1461,
          "lineEnd": 1490,
          "excerptHash": "na"
        },
        {
          "path": "tests/check_quickref_vs_routes.py",
          "lineStart": 21,
          "lineEnd": 23,
          "symbol": "main",
          "excerptHash": "na"
        },
        {
          "path": "tests/check_quickref_vs_routes.py",
          "lineStart": 41,
          "lineEnd": 52,
          "symbol": "main",
          "excerptHash": "na"
        },
        {
          "path": "开发文档/系统速查表.md",
          "lineStart": 47,
          "lineEnd": 60,
          "excerptHash": "na"
        },
        {
          "path": "web/routes/scheduler_analysis.py",
          "lineStart": 22,
          "lineEnd": 35,
          "symbol": "analysis_page",
          "excerptHash": "na"
        },
        {
          "path": "web/routes/system_logs.py",
          "lineStart": 29,
          "lineEnd": 67,
          "symbol": "logs_page",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_strict_numeric.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_import.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_source_row_num.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "开发文档/系统速查表.md"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "evidence/README.md"
        },
        {
          "path": "开发文档/开发文档.md"
        },
        {
          "path": "AGENTS.md"
        },
        {
          "path": "plugins/README.md"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "reviewedModules": [
        "任务8 页面组装、Excel 页面流程、模板树与前端协议",
        "任务9 测试目录重整与覆盖率口径",
        "任务10 文档、证据与审计轨道"
      ],
      "recommendedNextAction": "基于三轮结论修订 plan：补齐 task1/task4/task7/task8/task9/task10 的具体漏项与验证口径后，再把该 plan 视为唯一权威实施计划。",
      "findingIds": [
        "excel-pageflow-pilot-validation-misses-route-tests",
        "task9-misses-ui-contract-gates",
        "doc-path-drift-lacks-automated-validation"
      ]
    }
  ],
  "findings": [
    {
      "id": "bootstrap-governance-scope-still-incomplete",
      "severity": "medium",
      "category": "maintainability",
      "title": "bootstrap 启动链清单仍有漏项",
      "descriptionMarkdown": "任务1已经把 `web/bootstrap/` 作为重点治理对象，但显式登记名单仍未覆盖 `factory.py:_maintenance_gate_response()` 与 `web/bootstrap/paths.py:runtime_base_dir()`。前者在维护窗口响应判定中仍有裸 `except Exception: pass`，后者在运行根目录解析失败时整段静默回退；这两个点都处于启动/请求装配关键路径。如果不并入治理台账和统一门禁，批次0结束后仍会残留未受控的静默回退，导致 plan 的“启动链静默回退治理闭环”结论不够严谨。",
      "recommendationMarkdown": "把这两个函数补入任务1步骤5.5的显式清单、完成判定与专项门禁说明中，并要求与现有 `factory.py` 其余例外点采用同一台账格式管理。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 323,
          "lineEnd": 330,
          "excerptHash": "na"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 124,
          "lineEnd": 133,
          "symbol": "_maintenance_gate_response",
          "excerptHash": "na"
        },
        {
          "path": "web/bootstrap/paths.py",
          "lineStart": 14,
          "lineEnd": 25,
          "symbol": "runtime_base_dir",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/paths.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "config-sss-misses-summary-readers",
      "severity": "medium",
      "category": "maintainability",
      "title": "配置单一事实源遗漏摘要侧读取点",
      "descriptionMarkdown": "task4 的文件职责与实施步骤集中在配置服务、优化器与算法参数门面，但当前 `core/services/scheduler/schedule_summary_freeze.py` 仍直接用 `cfg_get()` 读取 `freeze_window_enabled/freeze_window_days`，并在 `int(...)` 失败时静默回退为 `0`。如果这个摘要侧读取点不并入 task4，那么冻结窗口相关字段仍会保留第二套读取/回退语义，plan 声称的“新增配置字段只需一处登记”“默认值、空值、数值规则只定义一次”就无法完全成立。",
      "recommendationMarkdown": "把 `schedule_summary_freeze.py`（以及同类摘要侧配置消费点）显式补入 task4 范围，要求统一走注册表或统一配置读取门面，不再保留独立 `cfg_get()+int()` 回退语义。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 754,
          "lineEnd": 763,
          "excerptHash": "na"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py",
          "lineStart": 10,
          "lineEnd": 18,
          "symbol": "_cfg_freeze_window_state",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "gantt-service-fallback-whitelist-unassigned",
      "severity": "medium",
      "category": "maintainability",
      "title": "Gantt 服务层静默回退仍无清零归属",
      "descriptionMarkdown": "task7 已经把 `gantt_critical_chain.py` 的 5 处异常治理列为显式步骤，但当前架构门禁白名单里还保留了 `core/services/scheduler/gantt_service.py:_critical_chain_cache_key` 与 `_get_critical_chain` 两个静默吞异常热点。plan 的 task7 没有为这两个既有白名单提供清零步骤或后续任务归属，导致 Gantt 领域在 task7 完成后仍会残留已知 `pass/continue` 型静默回退，与 plan 自己提出的“少兜底、少静默回退”目标不完全一致。",
      "recommendationMarkdown": "在 task7 中增加 `gantt_service.py` 的缓存键/缓存写回静默回退治理，或至少把这两个白名单明确绑定到 task7 的完成判定与专项回归中，避免成为未分配残项。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1113,
          "lineEnd": 1120,
          "excerptHash": "na"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 435,
          "lineEnd": 438,
          "symbol": "test_no_silent_exception_swallow",
          "excerptHash": "na"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 97,
          "lineEnd": 156,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "excel-pageflow-pilot-validation-misses-route-tests",
      "severity": "medium",
      "category": "test",
      "title": "试点页重构未绑定现成路由专项回归",
      "descriptionMarkdown": "task8 明确把 `scheduler_excel_calendar.py` 与 `process_excel_part_operation_hours.py` 作为首批试点页面，但其验证命令只跑通用 Excel/模板/UI 测试，没有把当前仓库中已经存在的试点页专项回归纳入执行。现有测试已经覆盖执行器接线、严格数值、导入语义、源行号与 append 语义等页面特有行为；若 pageflow 骨架重构后不把这些现成测试纳入 task8 验收，就无法覆盖 plan 自己在“实施前确认”里点名的差异点，容易出现骨架通过而页面特性回归失守。",
      "recommendationMarkdown": "把这几条现成的试点页专项回归显式并入 task8 的验证命令或完成判定；如果后续会迁目录，可在 task8 中先写“当前路径/迁移后路径二选一”的执行约定，但不能遗漏页面特有测试。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1196,
          "lineEnd": 1215,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1292,
          "lineEnd": 1304,
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py",
          "lineStart": 11,
          "lineEnd": 16,
          "symbol": "find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_strict_numeric.py",
          "lineStart": 1,
          "lineEnd": 5,
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_import.py",
          "lineStart": 8,
          "lineEnd": 13,
          "symbol": "find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_source_row_num.py",
          "lineStart": 10,
          "lineEnd": 15,
          "symbol": "find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_strict_numeric.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_import.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_source_row_num.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "开发文档/系统速查表.md"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "evidence/README.md"
        },
        {
          "path": "开发文档/开发文档.md"
        },
        {
          "path": "AGENTS.md"
        },
        {
          "path": "plugins/README.md"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "relatedMilestoneIds": [
        "m3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task9-misses-ui-contract-gates",
      "severity": "medium",
      "category": "test",
      "title": "测试目录重整遗漏关键界面门禁",
      "descriptionMarkdown": "task8 的验证仍直接依赖 `tests/regression_frontend_common_interactions.py` 与 `tests/test_ui_mode.py` 两条关键界面门禁，但 task9 的首批迁移与共享路径辅助覆盖范围并没有把它们纳入。前者还是根层脚本式回归，并继续使用 `os.path.join(here, \"..\")` 的固定父级仓库根定位；后者则是 `web/ui_mode.py` 运行时编排层的直接回归。这样会导致 task8 的关键界面契约在 task9 完成后仍停留在根层旧形态，削弱“本轮直接触达区域已有分层回归入口”的治理闭环。",
      "recommendationMarkdown": "把这两条测试至少纳入 task9 的首批迁移/归位范围；其中 `regression_frontend_common_interactions.py` 还应同步切到共享仓库根辅助，避免它在进入子目录后再次失效。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1298,
          "lineEnd": 1301,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1333,
          "lineEnd": 1398,
          "excerptHash": "na"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py",
          "lineStart": 7,
          "lineEnd": 10,
          "symbol": "_find_repo_root",
          "excerptHash": "na"
        },
        {
          "path": "tests/test_ui_mode.py",
          "lineStart": 206,
          "lineEnd": 241,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_strict_numeric.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_import.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_source_row_num.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "开发文档/系统速查表.md"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "evidence/README.md"
        },
        {
          "path": "开发文档/开发文档.md"
        },
        {
          "path": "AGENTS.md"
        },
        {
          "path": "plugins/README.md"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "relatedMilestoneIds": [
        "m3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "doc-path-drift-lacks-automated-validation",
      "severity": "medium",
      "category": "docs",
      "title": "文档路径漂移缺少自动校验",
      "descriptionMarkdown": "task10 要求把 `开发文档/系统速查表.md` 中真实存在的路由、入口、目录、脚本路径同步进去，但它的验证命令只跑 `check_quickref_vs_routes.py` 的 HTTP 接口对比和 README 链接断言。当前 `系统速查表.md` 已经存在 `web/routes/*.py`、`web/routes/scheduler.py` 等旧路径描述，而 `check_quickref_vs_routes.py` 只解析文档里的 `GET/POST` 接口，再与 Flask `url_map` 比较，根本不会校验这些文件路径/模块路径是否仍真实存在。因此 task10 按现有验证全部通过后，文档路径漂移依旧可能残留。",
      "recommendationMarkdown": "新增一个轻量文档漂移校验：至少对 `系统速查表.md` 中显式列出的关键文件/目录路径做存在性检查，或扩展 `check_quickref_vs_routes.py` 让它同时核对文档中的模块路径与任务3/8迁移后的真实文件位置。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1461,
          "lineEnd": 1490,
          "excerptHash": "na"
        },
        {
          "path": "tests/check_quickref_vs_routes.py",
          "lineStart": 21,
          "lineEnd": 23,
          "symbol": "main",
          "excerptHash": "na"
        },
        {
          "path": "tests/check_quickref_vs_routes.py",
          "lineStart": 41,
          "lineEnd": 52,
          "symbol": "main",
          "excerptHash": "na"
        },
        {
          "path": "开发文档/系统速查表.md",
          "lineStart": 47,
          "lineEnd": 60,
          "excerptHash": "na"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_strict_numeric.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_import.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_source_row_num.py"
        },
        {
          "path": "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "开发文档/系统速查表.md"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "evidence/README.md"
        },
        {
          "path": "开发文档/开发文档.md"
        },
        {
          "path": "AGENTS.md"
        },
        {
          "path": "plugins/README.md"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
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
    "bodyHash": "sha256:2d21f67f270db49da17abb98bf18ff7e54360a968e911ebf4dc775e894ecb42e",
    "generatedAt": "2026-04-06T07:45:55.990Z",
    "locale": "zh-CN"
  }
}
```

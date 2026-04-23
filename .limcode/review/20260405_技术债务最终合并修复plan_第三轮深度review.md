# 20260405 技术债务最终合并修复plan 第三轮深度review
- 日期: 2026-04-05
- 概述: 针对最终合并修复plan与实际代码现状的一致性、可达成性、优雅性与隐藏风险进行第三轮深度审查。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 20260405 技术债务最终合并修复plan 第三轮深度review

- 日期：2026-04-05
- 范围：`.limcode/plans/20260405_技术债务最终合并修复plan.md` 与其引用的实际实现位置
- 目标：核查该 plan 是否能真正达成治理目标，是否存在事实偏差、执行断层、过度兜底、静默回退、隐含兼容桥遗漏、验证口径失真与引用链不闭合问题
- 方法：按任务分组，结合真实代码、调用链、测试与文档约束做交叉审查；每完成一个有意义的模块审查单元，立即记录里程碑

## 初始结论
正在审查中。重点优先核查：请求级装配、调度主链、配置事实源、静态资源版本化、测试路径与文档入口链。

## 评审摘要

- 当前状态: 已完成
- 已审模块: requirements-dev.txt, .pre-commit-config.yaml, tests/test_architecture_fitness.py, tests/check_quickref_vs_routes.py, tests/generate_conformance_report.py, tests/regression_template_no_inline_event_jinja.py, tests/regression_template_urlfor_endpoints.py, web/bootstrap/, web/bootstrap/factory.py, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, web/routes/, web/viewmodels/, core/services/scheduler/config_service.py, core/algorithms/greedy/scheduler.py, core/algorithms/types.py, data/repositories/schedule_repo.py, core/services/scheduler/gantt_critical_chain.py, core/infrastructure/database.py, core/infrastructure/backup.py, templates/system/logs.html, templates/system/backup.html, web/bootstrap/static_versioning.py, web/ui_mode.py, static/js/gantt_boot.js, static/js/gantt_ui.js, web/routes/scheduler_analysis.py, web/routes/system_logs.py, 开发文档/, audit/, .limcode/plans/20260405_技术债务最终合并修复plan.md
- 当前进度: 已记录 4 个里程碑；最新：m4-task8-task10
- 里程碑总数: 4
- 已完成里程碑: 4
- 问题总数: 5
- 问题严重级别分布: 高 1 / 中 3 / 低 1
- 最新结论: 总体判断：这份 plan 的批次顺序、任务分解与大多数落点是正确的，且基本守住了 Win7 / Python 3.8 / Chrome109 / 安装包链路 / 迁移链路这些固定边界；从真实仓库状态看，任务 1—10 仍大体处于实施前阶段，因此把任务 1、任务 2、任务 5、任务 8、任务 9 作为起步优先级是合理的。但它还不能直接无修改开工，至少要先补齐 5 处会影响执行闭环的口径缺口：一，任务 1 的退出条件要显式纳入 `开发文档/README.md` 与 `audit/README.md`；二，把 `web/bootstrap/` 纳入门禁时必须同步定义分批白名单与清零节奏；三，批次 2 的退出条件要补上 `schedule_input_builder.py` 中 `_lookup_template_group_context` 的旧回退；四，任务 8 必须把 `web/ui_mode.py` 纳入双模板治理范围；五，任务 8 必须把 `install_versioned_url_for -> init_ui_mode` 的当前初始化顺序与 `ui_v2_static.static` 专项回归写成硬约束。补完这些后，本 plan 可以作为“唯一执行依据”继续推进；不补则存在入口链未闭合、兼容桥残留、双模板运行时未收口却被误判完成的实际风险。
- 下一步建议: 先修订 plan 中上述 5 处口径缺口，再按任务 1 → 任务 2 → 任务 5 → 任务 8 → 任务 9 的顺序启动首批实施；任务 3、任务 4、任务 6、任务 7 保持当前方向，但实施时要明确保留现有根层薄门面与已下沉到 `web/viewmodels/` 的成果。
- 总体结论: 有条件通过

## 评审发现

### 任务1退出条件漏列文档入口链

- ID: task1-doc-entry-exit
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: m1-baseline-task1-task9
- 说明:

  `任务 1` 的步骤 4.5 明确要求在任务完成前先建立 `开发文档/README.md` 与 `audit/README.md`，并让根 `README.md` 指向真实存在的目标；但完成判定只要求根 `README.md`、`scripts/run_quality_gate.py`、`.github/workflows/quality.yml`、`开发文档/技术债务治理台账.md` 四项同时存在，没有把这两份前置入口文档纳入退出条件。当前仓库也确实尚未存在这两个文件，如果按现有退出口径执行，任务 1 可能在入口链仍断裂时被误判完成。
- 建议:

  把 `开发文档/README.md` 与 `audit/README.md` 补入任务 1 的文件职责、完成判定和架构门禁断言，并在任务 10 沿用同一入口链。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:251-255`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:273-276`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/generate_conformance_report.py`
  - `tests/regression_template_no_inline_event_jinja.py`
  - `tests/regression_template_urlfor_endpoints.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### web/bootstrap 门禁缺少分批收紧策略

- ID: bootstrap-gate-ratchet-missing
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m1-baseline-task1-task9
- 说明:

  任务 1 计划把 `web/bootstrap/` 纳入统一质量门禁，但当前该目录内已经存在大量广义异常捕获；代表性位置包括 `web/bootstrap/factory.py` 的请求开库短路与 `web/bootstrap/static_versioning.py` 的静默吞异常。若不在任务 1 中同时定义 `web/bootstrap` 的分批白名单、退出条件与收紧节奏，执行者很容易在“门禁立刻全红”和“规则过宽形同无约束”之间摇摆，反而削弱本 plan 的治理力度。
- 建议:

  在 `开发文档/技术债务治理台账.md` 中单列 `web/bootstrap` 门禁台账，先锁定允许残留的文件与异常点位，再按批次把例外逐步清零，并把该台账接入 `tests/test_architecture_fitness.py` 或同一门禁入口下的专项测试。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:219-223`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:262-267`
  - `web/bootstrap/factory.py:263-278#_open_db`
  - `web/bootstrap/static_versioning.py:59-103`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/generate_conformance_report.py`
  - `tests/regression_template_no_inline_event_jinja.py`
  - `tests/regression_template_urlfor_endpoints.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/static_versioning.py`

### 批次2退出条件遗漏模板查找回退

- ID: batch2-exit-misses-template-lookup-bridge
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2-task2-task5
- 说明:

  任务 5 已明确把 `schedule_input_builder.py` 中 `_lookup_template_group_context` 对旧 `_get_template_and_group_for_op` 的回退纳入兼容桥清理范围，并要求在任务完成判定中一并删除；当前代码也确实在该函数内保留 `AttributeError` 回退。但批次 2 的退出条件只写“`五个已确认兼容函数` 与 `_merge_summary_warnings` 已删除或被确定性路径替代”，没有把这个模板查找回退显式列入批次退出口径。执行时存在“批次 2 被宣布完成，但旧模板查找桥仍残留”的风险。
- 建议:

  把 `_lookup_template_group_context` 的旧回退补入批次 2 的退出条件、验收说明与定向回归清单，确保批次完成口径与任务 5 的显式清理范围一致。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:709`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:737`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:764-765`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1299-1305`
  - `core/services/scheduler/schedule_input_builder.py:85-105#_lookup_template_group_context`
  - `web/bootstrap/factory.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### 任务8遗漏双模板运行时编排层

- ID: task8-misses-ui-mode-runtime
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m4-task8-task10
- 说明:

  任务 8 的文件职责与步骤已经覆盖 `web/pageflows/`、`web/viewmodels/`、模板收敛、行内脚本与 `web/bootstrap/static_versioning.py`，但没有把 `web/ui_mode.py` 纳入范围。当前双模板运行时的关键逻辑正集中在 `web/ui_mode.py`：它注册 `ui_v2_static`、创建 V2 模板叠加环境、在初始化失败时回退到 V1，并在 `render_ui_template(...)` 中决定最终模板环境与 `url_for` 注入。如果任务 8 只改模板树和静态资源版本化，而不把 `web/ui_mode.py` 同步纳入治理，实际的双模板兼容桥仍会留在验收范围之外，`C5` 与双界面漂移问题就无法真正闭环。
- 建议:

  把 `web/ui_mode.py` 增补进任务 8 的文件职责、实施步骤、验证命令与完成判定，至少显式约束 `ui_v2_static` 注册、V2 模板叠加环境、失败回退路径与渲染期 `url_for` 注入。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:993-1002`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1056-1067`
  - `web/ui_mode.py:152-205#init_ui_mode`
  - `web/ui_mode.py:359-380#render_ui_template`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `web/bootstrap/static_versioning.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `static/js/gantt_boot.js`
  - `static/js/gantt_ui.js`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### 静态资源版本化未写明初始化顺序约束

- ID: static-versioning-init-order-gap
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m4-task8-task10
- 说明:

  当前 `web/bootstrap/factory.py` 先执行 `install_versioned_url_for(app, static_dir)`，后执行 `init_ui_mode(app, base_dir)`；而 `web/bootstrap/static_versioning.py` 已经把 `ui_v2_static.static` 纳入版本化端点集合。任务 8 虽要求清单键同时覆盖 `static` 与 `ui_v2_static.static`，也要求补专项回归，但没有把“必须兼容当前初始化顺序”写成硬约束，列出的验证命令里也没有把 `static_versioning` / `ui_v2_static.static` 的专项回归写出来。若执行者在改造时把蓝图静态根解析做成启动期一次性求值，V2 资源版本化就可能在不报错的情况下失效。
- 建议:

  在任务 8 中补一条显式约束：`ui_v2_static.static` 必须在现有 `install_versioned_url_for -> init_ui_mode` 顺序下仍能工作；同时把对应专项回归列入验证命令，覆盖清单缺失、单文件缺失与 V2 静态资源版本化三个场景。
- 证据:
  - `web/bootstrap/factory.py:203-231`
  - `web/bootstrap/static_versioning.py:21-29`
  - `web/bootstrap/static_versioning.py:42-103`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1061-1067`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1077-1085`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `web/bootstrap/static_versioning.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `static/js/gantt_boot.js`
  - `static/js/gantt_ui.js`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

## 评审里程碑

### m1-baseline-task1-task9 · 工程基线与测试迁移基线核对

- 状态: 已完成
- 记录时间: 2026-04-05T17:54:11.692Z
- 已审模块: requirements-dev.txt, .pre-commit-config.yaml, tests/test_architecture_fitness.py, tests/check_quickref_vs_routes.py, tests/generate_conformance_report.py, tests/regression_template_no_inline_event_jinja.py, tests/regression_template_urlfor_endpoints.py, web/bootstrap/
- 摘要:

  已核对任务 1、任务 9、任务 10 的执行前基线：仓库根仍缺 `README.md`，`requirements-dev.txt` 仅声明 `pytest`，`.pre-commit-config.yaml` 虽已接入 `ruff`，但统一门禁脚本、托管工作流、治理台账、开发文档入口与审计入口均未落地。`tests/` 目录仍保持 318 个根层文件平铺，`tests/test_architecture_fitness.py` 仍使用基于当前文件上一级目录的仓库根定位，并在未安装 `radon` 时直接跳过复杂度检查；`tests/check_quickref_vs_routes.py`、`tests/generate_conformance_report.py`、`tests/regression_template_no_inline_event_jinja.py`、`tests/regression_template_urlfor_endpoints.py` 仍依赖固定父级定位，其中 `tests/generate_conformance_report.py` 还保留 `D:\Github` 的 Windows 专用兜底。结论：任务 1 与任务 9 基本处于实施前状态，但当前 plan 仍需要补齐退出口径与门禁收紧节奏，避免“入口链未闭合却可判完成”或“装配层门禁一上来全红”的执行偏差。
- 结论:

  任务 1、任务 9、任务 10 的方向成立，但任务 1 的退出口径与 `web/bootstrap/` 门禁治理方式仍需在 plan 中写得更硬。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:217-223`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:251-255`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:262-276`
  - `requirements-dev.txt:1-4`
  - `.pre-commit-config.yaml:1-12`
  - `tests/test_architecture_fitness.py:19-22`
  - `tests/test_architecture_fitness.py:330-340`
  - `tests/test_architecture_fitness.py:533-542`
  - `tests/check_quickref_vs_routes.py:8-13#find_repo_root`
  - `tests/generate_conformance_report.py:11-33#find_repo_root`
  - `tests/regression_template_no_inline_event_jinja.py:24-29#find_repo_root`
  - `tests/regression_template_urlfor_endpoints.py:28-33#find_repo_root`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/generate_conformance_report.py`
  - `tests/regression_template_no_inline_event_jinja.py`
  - `tests/regression_template_urlfor_endpoints.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  继续核对任务 2 与任务 5 的请求级装配、残余直接装配点与排产主链兼容桥。
- 问题:
  - [低] 文档: 任务1退出条件漏列文档入口链
  - [中] 测试: web/bootstrap 门禁缺少分批收紧策略

### m2-task2-task5 · 请求级装配与排产主链兼容桥核对

- 状态: 已完成
- 记录时间: 2026-04-05T17:54:35.253Z
- 已审模块: web/bootstrap/factory.py, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, web/routes/
- 摘要:

  已核对任务 2 与任务 5 的真实基线。`web/bootstrap/factory.py` 当前只在 `_open_db()` 中写入 `g.app_logger`、`g.db`、`g.op_logger`，尚未注入 `g.services`；`core/services/scheduler/schedule_service.py` 仍在构造器内部平铺创建 10 个仓储实例。路由层直接 `Service(g.db, ...)` 装配点依然很多，已搜索到 182 处。与此同时，排产主链中的签名探测与兼容桥仍完整存在：`_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_lookup_template_group_context` 的旧回退、`_scheduler_accepts_strict_mode`、`_schedule_with_optional_strict_mode`、`_merge_summary_warnings`，以及 `schedule_optimizer.py` 中本地配置/日期解析与 `if best is None` 兜底路径均未收口。结论：任务 2、任务 5 的优先级判断完全正确，当前仓库仍处于实施前状态；但批次 2 的退出口径需要和任务 5 的显式清理范围保持一致。
- 结论:

  任务 2 与任务 5 的治理方向准确，而且必须前置执行；当前最需要修正的是批次退出口径与任务清单之间的对齐。
- 证据:
  - `web/bootstrap/factory.py:263-289#_open_db`
  - `core/services/scheduler/schedule_service.py:49-59#_get_snapshot_with_optional_strict_mode`
  - `core/services/scheduler/schedule_service.py:78-96#ScheduleService.__init__`
  - `core/services/scheduler/schedule_input_collector.py:17-46#ScheduleRunInput`
  - `core/services/scheduler/schedule_input_collector.py:184-255`
  - `core/services/scheduler/schedule_input_collector.py:347-420#collect_schedule_run_input`
  - `core/services/scheduler/schedule_input_builder.py:85-105#_lookup_template_group_context`
  - `core/services/scheduler/schedule_optimizer_steps.py:85-115`
  - `core/services/scheduler/schedule_orchestrator.py:71-100#_merge_summary_warnings`
  - `core/services/scheduler/schedule_optimizer.py:290-357`
  - `core/services/scheduler/schedule_optimizer.py:549-582`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:301-372`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:695-778`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1299-1305`
  - `web/bootstrap/factory.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  继续核对任务 3、任务 4、任务 6、任务 7 的目录骨架、配置事实源、算法拆分与读模型拆分是否存在额外偏差。
- 问题:
  - [中] 可维护性: 批次2退出条件遗漏模板查找回退

### m3-task3-task4-task6-task7 · 目录骨架、配置事实源、算法与数据基础设施核对

- 状态: 已完成
- 记录时间: 2026-04-05T17:54:55.343Z
- 已审模块: web/routes/, web/viewmodels/, core/services/scheduler/config_service.py, core/algorithms/greedy/scheduler.py, core/algorithms/types.py, data/repositories/schedule_repo.py, core/services/scheduler/gantt_critical_chain.py, core/infrastructure/database.py, core/infrastructure/backup.py
- 摘要:

  已核对任务 3、任务 4、任务 6、任务 7 的现状。`web/routes/` 仍是 59 个根层文件平铺，`core/services/scheduler/` 仍是 45 个根层文件平铺，但 `web/routes/scheduler.py`、`process.py`、`personnel.py`、`equipment.py`、`system.py` 已经是纯导入注册的薄门面；`web/routes/scheduler_analysis.py` 与 `web/routes/system_logs.py` 也已把页面组装下沉到 `web/viewmodels/`。配置侧仍未建立 `config_field_spec.py`，`ConfigService` 继续持有 `DEFAULT_*` 与 `VALID_*`；算法侧仍未建立 `scheduler_steps.py`，`GreedyScheduler.schedule(...)` 仍保留大体量主流程，`core/algorithms/types.py` 也只有 `ScheduleResult` 与 `ScheduleSummary` 两个公开类型。数据基础设施侧仍未拆出 `schema_bootstrap.py`、`migration_runner.py`、`maintenance_window.py`、`backup_restore.py`，`data/repositories/schedule_repo.py` 继续混放多类读模型查询，`gantt_critical_chain.py:_load_rows()` 仍以 `except Exception: return []` 吞掉查询失败。结论：任务 4、任务 6、任务 7 基本仍处于实施前状态；任务 3 的“保留根层薄门面”判断是事实准确的，不应在后续实施中被过度重构回滚。
- 结论:

  任务 3、任务 4、任务 6、任务 7 的方向总体正确，其中最值得保留的是当前路由根层薄门面与已下沉到 `web/viewmodels/` 的页面组装成果。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:387-404`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:605-667`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:786-838`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:876-966`
  - `web/routes/scheduler.py:1-24`
  - `web/routes/process.py:1-30`
  - `web/routes/personnel.py:1-26`
  - `web/routes/equipment.py:1-22`
  - `web/routes/system.py:1-26`
  - `web/routes/scheduler_analysis.py:7-35`
  - `web/routes/system_logs.py:7-44`
  - `core/services/scheduler/config_service.py:17-63#ConfigService`
  - `core/algorithms/greedy/scheduler.py:36-80#GreedyScheduler`
  - `core/algorithms/types.py:10-38`
  - `data/repositories/schedule_repo.py:105-223`
  - `core/services/scheduler/gantt_critical_chain.py:49-53#_load_rows`
  - `core/infrastructure/database.py:292-378#ensure_schema`
  - `core/infrastructure/backup.py:171-230#maintenance_window`
  - `web/routes/scheduler.py`
  - `web/routes/process.py`
  - `web/routes/personnel.py`
  - `web/routes/equipment.py`
  - `web/routes/system.py`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `core/services/scheduler/config_service.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/types.py`
  - `data/repositories/schedule_repo.py`
  - `core/services/scheduler/gantt_critical_chain.py`
  - `core/infrastructure/database.py`
  - `core/infrastructure/backup.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  继续核对任务 8 与任务 10，重点看双模板运行时、静态资源版本化与文档入口链是否还有未纳入 plan 的关键风险。

### m4-task8-task10 · 界面双模板运行时、静态资源版本化与文档入口链核对

- 状态: 已完成
- 记录时间: 2026-04-05T17:55:28.757Z
- 已审模块: templates/system/logs.html, templates/system/backup.html, web/bootstrap/static_versioning.py, web/bootstrap/factory.py, web/ui_mode.py, static/js/gantt_boot.js, static/js/gantt_ui.js, web/routes/scheduler_analysis.py, web/routes/system_logs.py, 开发文档/, audit/
- 摘要:

  已核对任务 8 与任务 10 的现状。`templates/system/logs.html` 与 `templates/system/backup.html` 仍保留目标范围内的行内 `<script>`，`static/js/page_boot.js` 尚不存在，Gantt 相关脚本仍依赖 `window.__APS_GANTT__`，`web/bootstrap/static_versioning.py` 继续保留 `_mtime_version()` 的静默返回与 `except Exception: pass`。同时，当前双模板运行时的关键编排并不在任务 8 文本列出的文件中，而是在 `web/ui_mode.py`：该文件负责注册 `ui_v2_static`、创建 V2 模板叠加环境、失败时回退到 V1，并在渲染时注入版本化 `url_for`。此外，`web/bootstrap/factory.py` 先执行 `install_versioned_url_for(app, static_dir)`，后执行 `init_ui_mode(app, base_dir)`；如果后续改造成清单驱动版本化时没有把这个初始化顺序写成硬约束，`ui_v2_static.static` 很容易成为被遗漏的整合断点。结论：任务 8 当前覆盖了大部分显性前端债务，但仍漏掉 `web/ui_mode.py` 这一双模板运行时桥接层，也没有把 `ui_v2_static.static` 的初始化顺序与专项回归写成明确验收条件。任务 10 的入口链方向正确，但它依赖任务 1 先补齐根 README、开发文档入口与审计入口。
- 结论:

  任务 8 是当前 plan 中最需要再补一刀的部分：必须把 `web/ui_mode.py` 与 `ui_v2_static.static` 的初始化顺序一起纳入显式治理范围，否则双模板与静态资源版本化无法真正闭环。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:993-1002`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1044-1085`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1212-1265`
  - `templates/system/logs.html:198-209`
  - `templates/system/backup.html:291-302`
  - `web/bootstrap/static_versioning.py:21-103`
  - `web/bootstrap/factory.py:200-231`
  - `web/ui_mode.py:152-205#init_ui_mode`
  - `web/ui_mode.py:348-380#render_ui_template`
  - `static/js/gantt_boot.js:1-20`
  - `static/js/gantt_ui.js:1-12`
  - `web/routes/scheduler_analysis.py:7-35`
  - `web/routes/system_logs.py:7-44`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `web/bootstrap/static_versioning.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `static/js/gantt_boot.js`
  - `static/js/gantt_ui.js`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_logs.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  完成最终结论并收束为“可有条件执行”的总体判断，同时把任务 1、任务 2、任务 5、任务 8、任务 9 列为实施起步阶段的最高优先级。
- 问题:
  - [高] 可维护性: 任务8遗漏双模板运行时编排层
  - [中] 测试: 静态资源版本化未写明初始化顺序约束

## 最终结论

总体判断：这份 plan 的批次顺序、任务分解与大多数落点是正确的，且基本守住了 Win7 / Python 3.8 / Chrome109 / 安装包链路 / 迁移链路这些固定边界；从真实仓库状态看，任务 1—10 仍大体处于实施前阶段，因此把任务 1、任务 2、任务 5、任务 8、任务 9 作为起步优先级是合理的。但它还不能直接无修改开工，至少要先补齐 5 处会影响执行闭环的口径缺口：一，任务 1 的退出条件要显式纳入 `开发文档/README.md` 与 `audit/README.md`；二，把 `web/bootstrap/` 纳入门禁时必须同步定义分批白名单与清零节奏；三，批次 2 的退出条件要补上 `schedule_input_builder.py` 中 `_lookup_template_group_context` 的旧回退；四，任务 8 必须把 `web/ui_mode.py` 纳入双模板治理范围；五，任务 8 必须把 `install_versioned_url_for -> init_ui_mode` 的当前初始化顺序与 `ui_v2_static.static` 专项回归写成硬约束。补完这些后，本 plan 可以作为“唯一执行依据”继续推进；不补则存在入口链未闭合、兼容桥残留、双模板运行时未收口却被误判完成的实际风险。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnm1sc93-u93tj6",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T17:55:53.869Z",
  "finalizedAt": "2026-04-05T17:55:53.869Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "20260405 技术债务最终合并修复plan 第三轮深度review",
    "date": "2026-04-05",
    "overview": "针对最终合并修复plan与实际代码现状的一致性、可达成性、优雅性与隐藏风险进行第三轮深度审查。"
  },
  "scope": {
    "markdown": "# 20260405 技术债务最终合并修复plan 第三轮深度review\n\n- 日期：2026-04-05\n- 范围：`.limcode/plans/20260405_技术债务最终合并修复plan.md` 与其引用的实际实现位置\n- 目标：核查该 plan 是否能真正达成治理目标，是否存在事实偏差、执行断层、过度兜底、静默回退、隐含兼容桥遗漏、验证口径失真与引用链不闭合问题\n- 方法：按任务分组，结合真实代码、调用链、测试与文档约束做交叉审查；每完成一个有意义的模块审查单元，立即记录里程碑\n\n## 初始结论\n正在审查中。重点优先核查：请求级装配、调度主链、配置事实源、静态资源版本化、测试路径与文档入口链。"
  },
  "summary": {
    "latestConclusion": "总体判断：这份 plan 的批次顺序、任务分解与大多数落点是正确的，且基本守住了 Win7 / Python 3.8 / Chrome109 / 安装包链路 / 迁移链路这些固定边界；从真实仓库状态看，任务 1—10 仍大体处于实施前阶段，因此把任务 1、任务 2、任务 5、任务 8、任务 9 作为起步优先级是合理的。但它还不能直接无修改开工，至少要先补齐 5 处会影响执行闭环的口径缺口：一，任务 1 的退出条件要显式纳入 `开发文档/README.md` 与 `audit/README.md`；二，把 `web/bootstrap/` 纳入门禁时必须同步定义分批白名单与清零节奏；三，批次 2 的退出条件要补上 `schedule_input_builder.py` 中 `_lookup_template_group_context` 的旧回退；四，任务 8 必须把 `web/ui_mode.py` 纳入双模板治理范围；五，任务 8 必须把 `install_versioned_url_for -> init_ui_mode` 的当前初始化顺序与 `ui_v2_static.static` 专项回归写成硬约束。补完这些后，本 plan 可以作为“唯一执行依据”继续推进；不补则存在入口链未闭合、兼容桥残留、双模板运行时未收口却被误判完成的实际风险。",
    "recommendedNextAction": "先修订 plan 中上述 5 处口径缺口，再按任务 1 → 任务 2 → 任务 5 → 任务 8 → 任务 9 的顺序启动首批实施；任务 3、任务 4、任务 6、任务 7 保持当前方向，但实施时要明确保留现有根层薄门面与已下沉到 `web/viewmodels/` 的成果。",
    "reviewedModules": [
      "requirements-dev.txt",
      ".pre-commit-config.yaml",
      "tests/test_architecture_fitness.py",
      "tests/check_quickref_vs_routes.py",
      "tests/generate_conformance_report.py",
      "tests/regression_template_no_inline_event_jinja.py",
      "tests/regression_template_urlfor_endpoints.py",
      "web/bootstrap/",
      "web/bootstrap/factory.py",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_optimizer.py",
      "web/routes/",
      "web/viewmodels/",
      "core/services/scheduler/config_service.py",
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/types.py",
      "data/repositories/schedule_repo.py",
      "core/services/scheduler/gantt_critical_chain.py",
      "core/infrastructure/database.py",
      "core/infrastructure/backup.py",
      "templates/system/logs.html",
      "templates/system/backup.html",
      "web/bootstrap/static_versioning.py",
      "web/ui_mode.py",
      "static/js/gantt_boot.js",
      "static/js/gantt_ui.js",
      "web/routes/scheduler_analysis.py",
      "web/routes/system_logs.py",
      "开发文档/",
      "audit/",
      ".limcode/plans/20260405_技术债务最终合并修复plan.md"
    ]
  },
  "stats": {
    "totalMilestones": 4,
    "completedMilestones": 4,
    "totalFindings": 5,
    "severity": {
      "high": 1,
      "medium": 3,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "m1-baseline-task1-task9",
      "title": "工程基线与测试迁移基线核对",
      "status": "completed",
      "recordedAt": "2026-04-05T17:54:11.692Z",
      "summaryMarkdown": "已核对任务 1、任务 9、任务 10 的执行前基线：仓库根仍缺 `README.md`，`requirements-dev.txt` 仅声明 `pytest`，`.pre-commit-config.yaml` 虽已接入 `ruff`，但统一门禁脚本、托管工作流、治理台账、开发文档入口与审计入口均未落地。`tests/` 目录仍保持 318 个根层文件平铺，`tests/test_architecture_fitness.py` 仍使用基于当前文件上一级目录的仓库根定位，并在未安装 `radon` 时直接跳过复杂度检查；`tests/check_quickref_vs_routes.py`、`tests/generate_conformance_report.py`、`tests/regression_template_no_inline_event_jinja.py`、`tests/regression_template_urlfor_endpoints.py` 仍依赖固定父级定位，其中 `tests/generate_conformance_report.py` 还保留 `D:\\Github` 的 Windows 专用兜底。结论：任务 1 与任务 9 基本处于实施前状态，但当前 plan 仍需要补齐退出口径与门禁收紧节奏，避免“入口链未闭合却可判完成”或“装配层门禁一上来全红”的执行偏差。",
      "conclusionMarkdown": "任务 1、任务 9、任务 10 的方向成立，但任务 1 的退出口径与 `web/bootstrap/` 门禁治理方式仍需在 plan 中写得更硬。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 217,
          "lineEnd": 223
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 251,
          "lineEnd": 255
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 262,
          "lineEnd": 276
        },
        {
          "path": "requirements-dev.txt",
          "lineStart": 1,
          "lineEnd": 4
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 1,
          "lineEnd": 12
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 19,
          "lineEnd": 22
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 330,
          "lineEnd": 340
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 533,
          "lineEnd": 542
        },
        {
          "path": "tests/check_quickref_vs_routes.py",
          "lineStart": 8,
          "lineEnd": 13,
          "symbol": "find_repo_root"
        },
        {
          "path": "tests/generate_conformance_report.py",
          "lineStart": 11,
          "lineEnd": 33,
          "symbol": "find_repo_root"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py",
          "lineStart": 24,
          "lineEnd": 29,
          "symbol": "find_repo_root"
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 28,
          "lineEnd": 33,
          "symbol": "find_repo_root"
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
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/generate_conformance_report.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "requirements-dev.txt",
        ".pre-commit-config.yaml",
        "tests/test_architecture_fitness.py",
        "tests/check_quickref_vs_routes.py",
        "tests/generate_conformance_report.py",
        "tests/regression_template_no_inline_event_jinja.py",
        "tests/regression_template_urlfor_endpoints.py",
        "web/bootstrap/"
      ],
      "recommendedNextAction": "继续核对任务 2 与任务 5 的请求级装配、残余直接装配点与排产主链兼容桥。",
      "findingIds": [
        "task1-doc-entry-exit",
        "bootstrap-gate-ratchet-missing"
      ]
    },
    {
      "id": "m2-task2-task5",
      "title": "请求级装配与排产主链兼容桥核对",
      "status": "completed",
      "recordedAt": "2026-04-05T17:54:35.253Z",
      "summaryMarkdown": "已核对任务 2 与任务 5 的真实基线。`web/bootstrap/factory.py` 当前只在 `_open_db()` 中写入 `g.app_logger`、`g.db`、`g.op_logger`，尚未注入 `g.services`；`core/services/scheduler/schedule_service.py` 仍在构造器内部平铺创建 10 个仓储实例。路由层直接 `Service(g.db, ...)` 装配点依然很多，已搜索到 182 处。与此同时，排产主链中的签名探测与兼容桥仍完整存在：`_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_lookup_template_group_context` 的旧回退、`_scheduler_accepts_strict_mode`、`_schedule_with_optional_strict_mode`、`_merge_summary_warnings`，以及 `schedule_optimizer.py` 中本地配置/日期解析与 `if best is None` 兜底路径均未收口。结论：任务 2、任务 5 的优先级判断完全正确，当前仓库仍处于实施前状态；但批次 2 的退出口径需要和任务 5 的显式清理范围保持一致。",
      "conclusionMarkdown": "任务 2 与任务 5 的治理方向准确，而且必须前置执行；当前最需要修正的是批次退出口径与任务清单之间的对齐。",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 263,
          "lineEnd": 289,
          "symbol": "_open_db"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 49,
          "lineEnd": 59,
          "symbol": "_get_snapshot_with_optional_strict_mode"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 78,
          "lineEnd": 96,
          "symbol": "ScheduleService.__init__"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 17,
          "lineEnd": 46,
          "symbol": "ScheduleRunInput"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 184,
          "lineEnd": 255
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 347,
          "lineEnd": 420,
          "symbol": "collect_schedule_run_input"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py",
          "lineStart": 85,
          "lineEnd": 105,
          "symbol": "_lookup_template_group_context"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 85,
          "lineEnd": 115
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 71,
          "lineEnd": 100,
          "symbol": "_merge_summary_warnings"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 290,
          "lineEnd": 357
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 549,
          "lineEnd": 582
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 301,
          "lineEnd": 372
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 695,
          "lineEnd": 778
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1299,
          "lineEnd": 1305
        },
        {
          "path": "web/bootstrap/factory.py"
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
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "web/bootstrap/factory.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_optimizer.py",
        "web/routes/"
      ],
      "recommendedNextAction": "继续核对任务 3、任务 4、任务 6、任务 7 的目录骨架、配置事实源、算法拆分与读模型拆分是否存在额外偏差。",
      "findingIds": [
        "batch2-exit-misses-template-lookup-bridge"
      ]
    },
    {
      "id": "m3-task3-task4-task6-task7",
      "title": "目录骨架、配置事实源、算法与数据基础设施核对",
      "status": "completed",
      "recordedAt": "2026-04-05T17:54:55.343Z",
      "summaryMarkdown": "已核对任务 3、任务 4、任务 6、任务 7 的现状。`web/routes/` 仍是 59 个根层文件平铺，`core/services/scheduler/` 仍是 45 个根层文件平铺，但 `web/routes/scheduler.py`、`process.py`、`personnel.py`、`equipment.py`、`system.py` 已经是纯导入注册的薄门面；`web/routes/scheduler_analysis.py` 与 `web/routes/system_logs.py` 也已把页面组装下沉到 `web/viewmodels/`。配置侧仍未建立 `config_field_spec.py`，`ConfigService` 继续持有 `DEFAULT_*` 与 `VALID_*`；算法侧仍未建立 `scheduler_steps.py`，`GreedyScheduler.schedule(...)` 仍保留大体量主流程，`core/algorithms/types.py` 也只有 `ScheduleResult` 与 `ScheduleSummary` 两个公开类型。数据基础设施侧仍未拆出 `schema_bootstrap.py`、`migration_runner.py`、`maintenance_window.py`、`backup_restore.py`，`data/repositories/schedule_repo.py` 继续混放多类读模型查询，`gantt_critical_chain.py:_load_rows()` 仍以 `except Exception: return []` 吞掉查询失败。结论：任务 4、任务 6、任务 7 基本仍处于实施前状态；任务 3 的“保留根层薄门面”判断是事实准确的，不应在后续实施中被过度重构回滚。",
      "conclusionMarkdown": "任务 3、任务 4、任务 6、任务 7 的方向总体正确，其中最值得保留的是当前路由根层薄门面与已下沉到 `web/viewmodels/` 的页面组装成果。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 387,
          "lineEnd": 404
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 605,
          "lineEnd": 667
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 786,
          "lineEnd": 838
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 876,
          "lineEnd": 966
        },
        {
          "path": "web/routes/scheduler.py",
          "lineStart": 1,
          "lineEnd": 24
        },
        {
          "path": "web/routes/process.py",
          "lineStart": 1,
          "lineEnd": 30
        },
        {
          "path": "web/routes/personnel.py",
          "lineStart": 1,
          "lineEnd": 26
        },
        {
          "path": "web/routes/equipment.py",
          "lineStart": 1,
          "lineEnd": 22
        },
        {
          "path": "web/routes/system.py",
          "lineStart": 1,
          "lineEnd": 26
        },
        {
          "path": "web/routes/scheduler_analysis.py",
          "lineStart": 7,
          "lineEnd": 35
        },
        {
          "path": "web/routes/system_logs.py",
          "lineStart": 7,
          "lineEnd": 44
        },
        {
          "path": "core/services/scheduler/config_service.py",
          "lineStart": 17,
          "lineEnd": 63,
          "symbol": "ConfigService"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 36,
          "lineEnd": 80,
          "symbol": "GreedyScheduler"
        },
        {
          "path": "core/algorithms/types.py",
          "lineStart": 10,
          "lineEnd": 38
        },
        {
          "path": "data/repositories/schedule_repo.py",
          "lineStart": 105,
          "lineEnd": 223
        },
        {
          "path": "core/services/scheduler/gantt_critical_chain.py",
          "lineStart": 49,
          "lineEnd": 53,
          "symbol": "_load_rows"
        },
        {
          "path": "core/infrastructure/database.py",
          "lineStart": 292,
          "lineEnd": 378,
          "symbol": "ensure_schema"
        },
        {
          "path": "core/infrastructure/backup.py",
          "lineStart": 171,
          "lineEnd": 230,
          "symbol": "maintenance_window"
        },
        {
          "path": "web/routes/scheduler.py"
        },
        {
          "path": "web/routes/process.py"
        },
        {
          "path": "web/routes/personnel.py"
        },
        {
          "path": "web/routes/equipment.py"
        },
        {
          "path": "web/routes/system.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/types.py"
        },
        {
          "path": "data/repositories/schedule_repo.py"
        },
        {
          "path": "core/services/scheduler/gantt_critical_chain.py"
        },
        {
          "path": "core/infrastructure/database.py"
        },
        {
          "path": "core/infrastructure/backup.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "web/routes/",
        "web/viewmodels/",
        "core/services/scheduler/config_service.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/types.py",
        "data/repositories/schedule_repo.py",
        "core/services/scheduler/gantt_critical_chain.py",
        "core/infrastructure/database.py",
        "core/infrastructure/backup.py"
      ],
      "recommendedNextAction": "继续核对任务 8 与任务 10，重点看双模板运行时、静态资源版本化与文档入口链是否还有未纳入 plan 的关键风险。",
      "findingIds": []
    },
    {
      "id": "m4-task8-task10",
      "title": "界面双模板运行时、静态资源版本化与文档入口链核对",
      "status": "completed",
      "recordedAt": "2026-04-05T17:55:28.757Z",
      "summaryMarkdown": "已核对任务 8 与任务 10 的现状。`templates/system/logs.html` 与 `templates/system/backup.html` 仍保留目标范围内的行内 `<script>`，`static/js/page_boot.js` 尚不存在，Gantt 相关脚本仍依赖 `window.__APS_GANTT__`，`web/bootstrap/static_versioning.py` 继续保留 `_mtime_version()` 的静默返回与 `except Exception: pass`。同时，当前双模板运行时的关键编排并不在任务 8 文本列出的文件中，而是在 `web/ui_mode.py`：该文件负责注册 `ui_v2_static`、创建 V2 模板叠加环境、失败时回退到 V1，并在渲染时注入版本化 `url_for`。此外，`web/bootstrap/factory.py` 先执行 `install_versioned_url_for(app, static_dir)`，后执行 `init_ui_mode(app, base_dir)`；如果后续改造成清单驱动版本化时没有把这个初始化顺序写成硬约束，`ui_v2_static.static` 很容易成为被遗漏的整合断点。结论：任务 8 当前覆盖了大部分显性前端债务，但仍漏掉 `web/ui_mode.py` 这一双模板运行时桥接层，也没有把 `ui_v2_static.static` 的初始化顺序与专项回归写成明确验收条件。任务 10 的入口链方向正确，但它依赖任务 1 先补齐根 README、开发文档入口与审计入口。",
      "conclusionMarkdown": "任务 8 是当前 plan 中最需要再补一刀的部分：必须把 `web/ui_mode.py` 与 `ui_v2_static.static` 的初始化顺序一起纳入显式治理范围，否则双模板与静态资源版本化无法真正闭环。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 993,
          "lineEnd": 1002
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1044,
          "lineEnd": 1085
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1212,
          "lineEnd": 1265
        },
        {
          "path": "templates/system/logs.html",
          "lineStart": 198,
          "lineEnd": 209
        },
        {
          "path": "templates/system/backup.html",
          "lineStart": 291,
          "lineEnd": 302
        },
        {
          "path": "web/bootstrap/static_versioning.py",
          "lineStart": 21,
          "lineEnd": 103
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 200,
          "lineEnd": 231
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 152,
          "lineEnd": 205,
          "symbol": "init_ui_mode"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 348,
          "lineEnd": 380,
          "symbol": "render_ui_template"
        },
        {
          "path": "static/js/gantt_boot.js",
          "lineStart": 1,
          "lineEnd": 20
        },
        {
          "path": "static/js/gantt_ui.js",
          "lineStart": 1,
          "lineEnd": 12
        },
        {
          "path": "web/routes/scheduler_analysis.py",
          "lineStart": 7,
          "lineEnd": 35
        },
        {
          "path": "web/routes/system_logs.py",
          "lineStart": 7,
          "lineEnd": 44
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/gantt_ui.js"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "templates/system/logs.html",
        "templates/system/backup.html",
        "web/bootstrap/static_versioning.py",
        "web/bootstrap/factory.py",
        "web/ui_mode.py",
        "static/js/gantt_boot.js",
        "static/js/gantt_ui.js",
        "web/routes/scheduler_analysis.py",
        "web/routes/system_logs.py",
        "开发文档/",
        "audit/"
      ],
      "recommendedNextAction": "完成最终结论并收束为“可有条件执行”的总体判断，同时把任务 1、任务 2、任务 5、任务 8、任务 9 列为实施起步阶段的最高优先级。",
      "findingIds": [
        "task8-misses-ui-mode-runtime",
        "static-versioning-init-order-gap"
      ]
    }
  ],
  "findings": [
    {
      "id": "task1-doc-entry-exit",
      "severity": "low",
      "category": "docs",
      "title": "任务1退出条件漏列文档入口链",
      "descriptionMarkdown": "`任务 1` 的步骤 4.5 明确要求在任务完成前先建立 `开发文档/README.md` 与 `audit/README.md`，并让根 `README.md` 指向真实存在的目标；但完成判定只要求根 `README.md`、`scripts/run_quality_gate.py`、`.github/workflows/quality.yml`、`开发文档/技术债务治理台账.md` 四项同时存在，没有把这两份前置入口文档纳入退出条件。当前仓库也确实尚未存在这两个文件，如果按现有退出口径执行，任务 1 可能在入口链仍断裂时被误判完成。",
      "recommendationMarkdown": "把 `开发文档/README.md` 与 `audit/README.md` 补入任务 1 的文件职责、完成判定和架构门禁断言，并在任务 10 沿用同一入口链。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 251,
          "lineEnd": 255
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 273,
          "lineEnd": 276
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
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/generate_conformance_report.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m1-baseline-task1-task9"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "bootstrap-gate-ratchet-missing",
      "severity": "medium",
      "category": "test",
      "title": "web/bootstrap 门禁缺少分批收紧策略",
      "descriptionMarkdown": "任务 1 计划把 `web/bootstrap/` 纳入统一质量门禁，但当前该目录内已经存在大量广义异常捕获；代表性位置包括 `web/bootstrap/factory.py` 的请求开库短路与 `web/bootstrap/static_versioning.py` 的静默吞异常。若不在任务 1 中同时定义 `web/bootstrap` 的分批白名单、退出条件与收紧节奏，执行者很容易在“门禁立刻全红”和“规则过宽形同无约束”之间摇摆，反而削弱本 plan 的治理力度。",
      "recommendationMarkdown": "在 `开发文档/技术债务治理台账.md` 中单列 `web/bootstrap` 门禁台账，先锁定允许残留的文件与异常点位，再按批次把例外逐步清零，并把该台账接入 `tests/test_architecture_fitness.py` 或同一门禁入口下的专项测试。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 219,
          "lineEnd": 223
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 262,
          "lineEnd": 267
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 263,
          "lineEnd": 278,
          "symbol": "_open_db"
        },
        {
          "path": "web/bootstrap/static_versioning.py",
          "lineStart": 59,
          "lineEnd": 103
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
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/generate_conformance_report.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1-baseline-task1-task9"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "batch2-exit-misses-template-lookup-bridge",
      "severity": "medium",
      "category": "maintainability",
      "title": "批次2退出条件遗漏模板查找回退",
      "descriptionMarkdown": "任务 5 已明确把 `schedule_input_builder.py` 中 `_lookup_template_group_context` 对旧 `_get_template_and_group_for_op` 的回退纳入兼容桥清理范围，并要求在任务完成判定中一并删除；当前代码也确实在该函数内保留 `AttributeError` 回退。但批次 2 的退出条件只写“`五个已确认兼容函数` 与 `_merge_summary_warnings` 已删除或被确定性路径替代”，没有把这个模板查找回退显式列入批次退出口径。执行时存在“批次 2 被宣布完成，但旧模板查找桥仍残留”的风险。",
      "recommendationMarkdown": "把 `_lookup_template_group_context` 的旧回退补入批次 2 的退出条件、验收说明与定向回归清单，确保批次完成口径与任务 5 的显式清理范围一致。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 709,
          "lineEnd": 709
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 737,
          "lineEnd": 737
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 764,
          "lineEnd": 765
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1299,
          "lineEnd": 1305
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py",
          "lineStart": 85,
          "lineEnd": 105,
          "symbol": "_lookup_template_group_context"
        },
        {
          "path": "web/bootstrap/factory.py"
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
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m2-task2-task5"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task8-misses-ui-mode-runtime",
      "severity": "high",
      "category": "maintainability",
      "title": "任务8遗漏双模板运行时编排层",
      "descriptionMarkdown": "任务 8 的文件职责与步骤已经覆盖 `web/pageflows/`、`web/viewmodels/`、模板收敛、行内脚本与 `web/bootstrap/static_versioning.py`，但没有把 `web/ui_mode.py` 纳入范围。当前双模板运行时的关键逻辑正集中在 `web/ui_mode.py`：它注册 `ui_v2_static`、创建 V2 模板叠加环境、在初始化失败时回退到 V1，并在 `render_ui_template(...)` 中决定最终模板环境与 `url_for` 注入。如果任务 8 只改模板树和静态资源版本化，而不把 `web/ui_mode.py` 同步纳入治理，实际的双模板兼容桥仍会留在验收范围之外，`C5` 与双界面漂移问题就无法真正闭环。",
      "recommendationMarkdown": "把 `web/ui_mode.py` 增补进任务 8 的文件职责、实施步骤、验证命令与完成判定，至少显式约束 `ui_v2_static` 注册、V2 模板叠加环境、失败回退路径与渲染期 `url_for` 注入。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 993,
          "lineEnd": 1002
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1056,
          "lineEnd": 1067
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 152,
          "lineEnd": 205,
          "symbol": "init_ui_mode"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 359,
          "lineEnd": 380,
          "symbol": "render_ui_template"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/gantt_ui.js"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m4-task8-task10"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "static-versioning-init-order-gap",
      "severity": "medium",
      "category": "test",
      "title": "静态资源版本化未写明初始化顺序约束",
      "descriptionMarkdown": "当前 `web/bootstrap/factory.py` 先执行 `install_versioned_url_for(app, static_dir)`，后执行 `init_ui_mode(app, base_dir)`；而 `web/bootstrap/static_versioning.py` 已经把 `ui_v2_static.static` 纳入版本化端点集合。任务 8 虽要求清单键同时覆盖 `static` 与 `ui_v2_static.static`，也要求补专项回归，但没有把“必须兼容当前初始化顺序”写成硬约束，列出的验证命令里也没有把 `static_versioning` / `ui_v2_static.static` 的专项回归写出来。若执行者在改造时把蓝图静态根解析做成启动期一次性求值，V2 资源版本化就可能在不报错的情况下失效。",
      "recommendationMarkdown": "在任务 8 中补一条显式约束：`ui_v2_static.static` 必须在现有 `install_versioned_url_for -> init_ui_mode` 顺序下仍能工作；同时把对应专项回归列入验证命令，覆盖清单缺失、单文件缺失与 V2 静态资源版本化三个场景。",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 203,
          "lineEnd": 231
        },
        {
          "path": "web/bootstrap/static_versioning.py",
          "lineStart": 21,
          "lineEnd": 29
        },
        {
          "path": "web/bootstrap/static_versioning.py",
          "lineStart": 42,
          "lineEnd": 103
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1061,
          "lineEnd": 1067
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1077,
          "lineEnd": 1085
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/gantt_ui.js"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m4-task8-task10"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:ed922b5fa49503c2c46da916e4c31c99c393e012d92d985698adff7297b9c6f1",
    "generatedAt": "2026-04-05T17:55:53.869Z",
    "locale": "zh-CN"
  }
}
```

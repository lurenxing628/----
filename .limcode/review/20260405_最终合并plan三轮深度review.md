# 20260405 最终合并修复plan三轮深度review
- 日期: 2026-04-05
- 概述: 针对 .limcode/plans/20260405_技术债务最终合并修复plan.md 的三轮深审，核对真实代码引用链、验证命令有效性与反兜底约束可落地性。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 20260405 最终合并修复plan三轮深度review

## 审查对象
- `.limcode/plans/20260405_技术债务最终合并修复plan.md`

## 审查目标
1. 判断该 merged plan 在 Win7 / Python 3.8 / `Chrome109` / 现有安装包链路 / 现有数据库迁移链路边界下，是否真的可执行。
2. 判断该 plan 是否足够优雅、简洁、逻辑严谨，且不引入新的兼容桥、静默回退、过度抽象或第二事实源。
3. 结合真实代码与引用链，确认 plan 中的文件路径、函数归属、验证命令、批次顺序与当前仓库现状是否一致。

## 审查方法
- 对照 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 与真实代码逐项核对。
- 抽读调度主链、配置链、路由装配、模板/前端、数据基础设施、测试门禁与文档入口。
- 对关键验证命令做最小实际执行，确认不是纸面可运行。

## 先行结论
- 该 merged plan 相比两份原始 plan 明显更强：覆盖面完整、反兜底约束明确、整体方向正确，已经是当前仓库最适合作为唯一执行 plan 的版本。
- 但它**仍不适合原样直接开工**：当前文本还残留若干执行级硬伤，尤其是任务 5 的函数归属写错、任务 8/10 的验证口径与真实测试不完全匹配、任务 9/10 之间存在测试路径漂移。
- 结论：**有条件通过**。应先修正文档中的少数硬伤，再按批次执行；若不先修正，实施阶段会出现“按 plan 搜不到函数 / 命令跑过却没验证到目标 / 迁移后仍引用旧测试路径”的偏差。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, web/routes/, web/viewmodels/, web/bootstrap/factory.py, core/infrastructure/database.py, core/infrastructure/backup.py, templates/system/logs.html, templates/system/backup.html, templates/base.html, web_new_test/templates/base.html, templates/scheduler/gantt.html, web_new_test/templates/scheduler/gantt.html, web/bootstrap/static_versioning.py, tests/regression_template_no_inline_event_jinja.py, static/js/, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, tests/conftest.py, tests/check_quickref_vs_routes.py, tests/regression_schedule_service_facade_delegation.py, tests/test_architecture_fitness.py, web/routes/scheduler.py, web/routes/scheduler_analysis.py, web/routes/system_logs.py
- 当前进度: 已记录 3 个里程碑；最新：R3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 9
- 问题严重级别分布: 高 2 / 中 7 / 低 0
- 最新结论: 综合三轮审查，`.limcode/plans/20260405_技术债务最终合并修复plan.md` 可以作为**唯一权威执行 plan 的候选版本**，但**当前文本仍不宜原样直接开工**。它的优势是真正覆盖了已确认债务、总体结构克制、明确限制了兼容桥/静默回退/总抽象扩张，并且与 Win7 / Python 3.8 / Chrome109 / 现有安装包链路 / 现有数据库迁移链路边界总体一致。真正阻碍其“直接执行”的，不是方向错误，而是少量但关键的执行级文档缺陷：任务 5 helper 归属写错、任务 10 的速查表校验命令当前空转、任务 9/10 的测试迁移路径前后不一致、任务 2 仍沿用过时的构造器事实，以及任务 8 对现有行内脚本与静默吞异常的清理要求仍不够硬。 因此最终判定是：**有条件接受**。先修正上述文档硬伤，再执行该 merged plan；修正后，它仍然是当前仓库最值得继续使用的单一执行 plan。
- 下一步建议: 先做一次 plan 文本勘误：修正 task 2 / task 5 / task 8 / task 10 的事实与命令，再以该文件为唯一执行 plan 进入批次 0。
- 总体结论: 有条件通过

## 评审发现

### 请求级装配收口规模被低估

- ID: request-scope-rollout-underestimated
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R1
- 说明:

  任务 2 的方向是正确的，但真实代码面比文档描述更大：`web/routes/` 当前有 `182` 处直接 `Service(g.db, ...)` 构造，不只是任务 2 列出的第一批与第二批几个文件。若没有“残余直接装配点总数下降到多少、哪些允许留账、何时必须清零”的明确退出条件，执行者容易在完成样板改造后误判任务已结束。
- 建议:

  把任务 2 的完成判定补成可量化口径：例如列出初始总数、样板批次完成后的剩余总数、允许登记台账的条件与最晚清零批次。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/routes/dashboard.py`
  - `web/routes/material.py`
  - `web/routes/process_parts.py`
  - `web/routes/process_op_types.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/scheduler_config.py`
  - `web/routes/system_logs.py`
  - `web/routes/scheduler.py`
  - `web/routes/scheduler_analysis.py`
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `web/viewmodels/system_logs_vm.py`
  - `web/bootstrap/factory.py`
  - `core/infrastructure/backup.py`

### 入口链与质量门禁尚未落地

- ID: docs-and-gate-bootstrap-missing
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R1
- 说明:

  当前仓库缺少根 `README.md`、`开发文档/README.md`、`audit/README.md`、`.github/workflows/quality.yml`、`scripts/run_quality_gate.py`。这说明任务 1 与任务 10 不是普通收尾项，而是后续治理的真实前置条件。并且任务 1 要求根 `README.md` 直接链接 `开发文档/README.md`，但该文件被放到任务 10 才补齐，存在前后依赖倒置。
- 建议:

  把 `开发文档/README.md` 与 `audit/README.md` 的最小入口版前移到任务 1，或把任务 1 的根 README 链接要求改成“先链接当前已存在入口，任务 10 再补全开发文档总索引”。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/routes/dashboard.py`
  - `web/routes/material.py`
  - `web/routes/process_parts.py`
  - `web/routes/process_op_types.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/scheduler_config.py`
  - `web/routes/system_logs.py`
  - `web/routes/scheduler.py`
  - `web/routes/scheduler_analysis.py`
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `web/viewmodels/system_logs_vm.py`
  - `web/bootstrap/factory.py`
  - `core/infrastructure/backup.py`

### 数据基础设施任务对 backup 热点描述不足

- ID: backup-hotspot-plan-understated
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R1
- 说明:

  任务 7 的标题明确要拆 `database.py`、`backup.py` 热点，但步骤文本主要围绕 `database.py` 展开。真实代码中 `core/infrastructure/backup.py` 仍承载 `maintenance_window` 与 `BackupManager` 等核心职责，若 plan 不把这些符号的迁移顺序写清，执行者很容易只拆 `database.py` 而留下另一半热点原封不动。
- 建议:

  在任务 7 中显式补写：`core/infrastructure/backup.py` 的 `maintenance_window` 迁到 `maintenance_window.py`，`BackupManager`/`restore` 迁到 `backup_restore.py`，`backup.py` 最终只留薄门面或稳定导出。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/routes/dashboard.py`
  - `web/routes/material.py`
  - `web/routes/process_parts.py`
  - `web/routes/process_op_types.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/scheduler_config.py`
  - `web/routes/system_logs.py`
  - `web/routes/scheduler.py`
  - `web/routes/scheduler_analysis.py`
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `web/viewmodels/system_logs_vm.py`
  - `web/bootstrap/factory.py`
  - `core/infrastructure/backup.py`
  - `core/infrastructure/database.py`

### 模板行内脚本治理与验证口径不一致

- ID: inline-script-gate-mismatch
- 严重级别: 中
- 分类: HTML
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  task 8 目标之一是把 `templates/system/logs.html` 的行内脚本迁出，但其验证命令使用的是 `tests/regression_template_no_inline_event_jinja.py`。该测试真实职责是扫描 `on*="...{{ ... }}"` 这类 inline 事件属性 + Jinja 插值，不检查普通 `<script defer>...</script>`。因此即使 `templates/system/logs.html`、`templates/system/backup.html` 仍保留行内脚本，当前验证也可能通过。
- 建议:

  为 task 8 增加一个专门的模板门禁：显式扫描目标模板中的行内 `<script>`，并把 `templates/system/backup.html` 是否一并收口写进任务范围或台账。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `templates/base.html`
  - `web_new_test/templates/base.html`
  - `templates/scheduler/gantt.html`
  - `web_new_test/templates/scheduler/gantt.html`
  - `web/bootstrap/static_versioning.py`
  - `tests/regression_template_no_inline_event_jinja.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/common.js`

### 静态资源版本化任务未强制清理现有静默吞异常

- ID: static-versioning-silent-swallow-unspecified
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  真实代码中 `web/bootstrap/static_versioning.py` 在 `_versioned_url_for()` 和 `install_versioned_url_for()` 里仍保留 `except Exception: pass`。task 8 只写“优先读取清单；本任务不新增新的静默后备逻辑”，这不足以保证现有静默吞异常被删除，容易让最终实现只是‘在旧静默回退外面再包一层 manifest 优先’。
- 建议:

  把 task 8 的步骤 8 改成明确动作：删除 `web/bootstrap/static_versioning.py` 里的静默 `except Exception: pass`，改为可观测、确定性的失败路径或日志记录路径，并为 manifest 读取失败补专门回归。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `templates/base.html`
  - `web_new_test/templates/base.html`
  - `templates/scheduler/gantt.html`
  - `web_new_test/templates/scheduler/gantt.html`
  - `web/bootstrap/static_versioning.py`
  - `tests/regression_template_no_inline_event_jinja.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/common.js`

### 任务5兼容函数文件归属错误

- ID: task5-helper-location-mismatch
- 严重级别: 高
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  task 5 的“必须删除或收口的兼容函数”列表中，至少 3 个 helper 的文件归属与真实代码不一致：`_get_snapshot_with_optional_strict_mode` 实际位于 `core/services/scheduler/schedule_service.py`；`_build_algo_operations_with_optional_outcome` 与 `_build_freeze_window_seed_with_optional_meta` 实际都位于 `core/services/scheduler/schedule_input_collector.py`。这会直接导致执行者按 plan 搜索时定位失败，也会影响批次切分和回归补点。
- 建议:

  在实施前先修正文档中的 helper 归属，并把调用方与预期删除顺序一起写清，避免后续 task 5 执行偏离真实代码。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `tests/conftest.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/regression_schedule_service_facade_delegation.py`
  - `tests/regression_template_no_inline_event_jinja.py`

### 任务10速查表验证命令不会真正执行检查

- ID: task10-quickref-pytest-noop
- 严重级别: 高
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  `tests/conftest.py` 的自定义 pytest 收集只覆盖文件名以 `regression_` 开头、且定义 `main()` 的脚本。`tests/check_quickref_vs_routes.py` 虽然有 `main()`，但文件名前缀不是 `regression_`，因此 `python -m pytest tests/check_quickref_vs_routes.py -q` 的实际结果是 `no tests ran`。也就是说，task 10 目前列出的验证命令并不能证明速查表与路由实现的一致性。
- 建议:

  把 task 10 的验证入口改成 `python tests/check_quickref_vs_routes.py`，或把该脚本迁成 `regression_` 风格/真正的 pytest 测试后再继续使用 pytest 命令。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `tests/conftest.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/regression_schedule_service_facade_delegation.py`
  - `tests/regression_template_no_inline_event_jinja.py`

### 任务9迁移后任务10仍引用旧测试路径

- ID: task9-task10-test-path-drift
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  task 9 明确要求把 `tests/test_architecture_fitness.py` 迁到 `tests/architecture/test_architecture_fitness.py`，但 task 10 的验证命令仍写 `python -m pytest tests/test_architecture_fitness.py -q`。这意味着一旦按 task 9 落地测试分层，task 10 的命令就会成为陈旧入口，破坏 plan 自己的后续一致性。
- 建议:

  把后续所有测试命令统一切成目录入口或迁移后的新路径，至少在 task 10 中改为 `tests/architecture/test_architecture_fitness.py` 或 `tests/architecture/`。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `tests/conftest.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/regression_schedule_service_facade_delegation.py`
  - `tests/regression_template_no_inline_event_jinja.py`

### 任务2仍沿用过时的构造器事实

- ID: task2-constructor-fact-mismatch
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  task 2 把 `ScheduleService` 的起点写成“12 个仓储参数构造器”，而真实 `ScheduleService.__init__` 只有 `conn`、`logger`、`op_logger` 三个入参，并在内部创建仓储成员。这个差异会误导执行者把精力放在错误的外部签名收口上，而不是内部依赖组织方式与请求级装配收口。
- 建议:

  把 task 2 的表述从“构造器参数收口”改成“内部平铺依赖改为仓储束/组合对象”，并同步修正仓储数量描述。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `tests/conftest.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/regression_schedule_service_facade_delegation.py`
  - `tests/regression_template_no_inline_event_jinja.py`

## 评审里程碑

### R1 · 第一轮：覆盖面、边界与达成性审查

- 状态: 已完成
- 记录时间: 2026-04-05T16:04:40.335Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, web/routes/, web/viewmodels/, web/bootstrap/factory.py, core/infrastructure/database.py, core/infrastructure/backup.py
- 摘要:

  对 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 与真实仓库现状逐项对照后，结论是：该 plan 的问题覆盖面与总体批次顺序明显优于旧版，方向上可以支撑本轮治理目标；但当前基线体量比文档叙述更大，且入口链仍未就位，导致任务 1 / 任务 2 / 任务 7 / 任务 10 的前置约束比文档看起来更硬。

  关键事实：
  - `core/services/scheduler/` 当前仍有 45 个平铺文件，`web/routes/` 当前仍有 59 个平铺文件。
  - `web/routes/` 中实际存在 `182` 处直接 `Service(g.db, ...)` 构造，远超任务 2 列举的第一、第二批样本范围。
  - 根 `README.md`、`开发文档/README.md`、`audit/README.md`、`.github/workflows/quality.yml`、`scripts/run_quality_gate.py` 当前均不存在。
  - 当前代码已有部分正向进展，不能被 plan 叙述掩盖：`web/routes/scheduler.py` 已是薄门面；`web/routes/scheduler_analysis.py` + `web/viewmodels/scheduler_analysis_vm.py`、`web/routes/system_logs.py` + `web/viewmodels/system_logs_vm.py` 已经部分落实页面组装下沉。

  本轮结论：plan 的主骨架成立，但任务 1/10 应被视为真实前置条件，任务 2 与任务 7 需要把“残余清点与退出条件”写得更刚性，不能只停留在方向正确。
- 结论:

  第一轮结论：该 merged plan 覆盖面充足、边界约束正确，但其执行前提比文本表现得更严格；若不先补入口链与残余台账，后续批次会出现治理范围失真。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/routes/dashboard.py`
  - `web/routes/material.py`
  - `web/routes/process_parts.py`
  - `web/routes/process_op_types.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/scheduler_config.py`
  - `web/routes/system_logs.py`
  - `web/routes/scheduler.py`
  - `web/routes/scheduler_analysis.py`
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `web/viewmodels/system_logs_vm.py`
  - `web/bootstrap/factory.py`
  - `core/infrastructure/backup.py`
- 下一步建议:

  进入第二轮，重点审查该 plan 的实现优雅性、反兜底约束与验证口径是否与真实模板/前端/静态资源实现一致。
- 问题:
  - [中] 可维护性: 请求级装配收口规模被低估
  - [中] 文档: 入口链与质量门禁尚未落地
  - [中] 可维护性: 数据基础设施任务对 backup 热点描述不足

### R2 · 第二轮：实现优雅性、反兜底约束与前端协议审查

- 状态: 已完成
- 记录时间: 2026-04-05T16:05:06.321Z
- 已审模块: templates/system/logs.html, templates/system/backup.html, templates/base.html, web_new_test/templates/base.html, templates/scheduler/gantt.html, web_new_test/templates/scheduler/gantt.html, web/bootstrap/static_versioning.py, tests/regression_template_no_inline_event_jinja.py, static/js/
- 摘要:

  第二轮重点检查 merged plan 是否真的贯彻“少兼容桥、少静默回退、少总抽象”的治理目标。结论是：该 plan 的**设计方向是正确的**，而且比旧版更克制——`web/bootstrap/request_services.py`、`core/services/scheduler/repository_bundle.py`、`web/pageflows/excel_import_flow.py` / `excel_import_hooks.py`、`static/js/page_boot.js` + `data-page` / `data-*`、`config_field_spec.py` 这些提案都属于最小必要抽象，没有再造一个更大的容器、总控制器或全局注册表。

  但真实代码核对后，任务 8 仍有两个关键不足：
  1. **验证口径与治理目标不完全一致。** `templates/system/logs.html` 仍有行内 `<script defer>`，`templates/system/backup.html` 也有同类模式；而 task 8 给出的 `python -m pytest tests/regression_template_no_inline_event_jinja.py -q` 实际只检查“inline 事件属性 + Jinja 插值”，并不覆盖普通行内 `<script>`。
  2. **现有静默回退没有被明确要求删除。** `web/bootstrap/static_versioning.py` 仍在版本注入与 Jinja 全局安装处保留 `except Exception: pass` 级别的静默吞异常；task 8 只写了“本任务不新增新的静默后备逻辑”，但没有把“删除现有静默吞异常”写成强制动作。

  同时，前端现状也再次验证了 task 8 的方向没有问题：当前仓库仍没有 `data-page`、没有 `static/js/page_boot.js`，`window.__APS_GANTT__` / `window.__APS_COMMON__` 仍是主要启动协议；`templates/base.html` 与 `web_new_test/templates/base.html`、`templates/scheduler/gantt.html` 与 `web_new_test/templates/scheduler/gantt.html` 仍存在大段重复。因此 task 8 应保留，但需要把“证明方式”与“收口范围”写得更严。
- 结论:

  第二轮结论：merged plan 的抽象方向总体优雅、克制，符合反兜底目标；但 task 8 当前还缺少对现有行内脚本与静默吞异常的直接清理要求，容易出现‘看起来完成，实际上旧问题仍在’的假完成。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `templates/system/logs.html`
  - `templates/system/backup.html`
  - `templates/base.html`
  - `web_new_test/templates/base.html`
  - `templates/scheduler/gantt.html`
  - `web_new_test/templates/scheduler/gantt.html`
  - `web/bootstrap/static_versioning.py`
  - `tests/regression_template_no_inline_event_jinja.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/common.js`
- 下一步建议:

  进入第三轮，审查任务文本中的函数归属、验证命令、测试迁移路径与当前代码/测试收集机制是否一一对应。
- 问题:
  - [中] HTML: 模板行内脚本治理与验证口径不一致
  - [中] 可维护性: 静态资源版本化任务未强制清理现有静默吞异常

### R3 · 第三轮：逻辑严谨性、命令有效性与路径一致性审查

- 状态: 已完成
- 记录时间: 2026-04-05T16:05:46.793Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, tests/conftest.py, tests/check_quickref_vs_routes.py, tests/regression_schedule_service_facade_delegation.py, tests/regression_template_no_inline_event_jinja.py
- 摘要:

  第三轮把 merged plan 当成“执行手册”来审：不再只看方向，而是核对执行者能不能按文中路径、函数名与验证命令一步一步落地。结论是：当前版本仍有 4 个实打实的执行级问题，其中 2 个属于高严重级别。

  1. **任务 5 函数归属写错。** plan 把 `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta` 标到了错误文件，和真实代码不一致。
  2. **任务 10 的一个验证命令实际空转。** `tests/conftest.py` 只会把文件名以 `regression_` 开头、且定义 `main()` 的脚本收集为自定义 pytest 用例；`tests/check_quickref_vs_routes.py` 不满足这个规则。实际执行 `python -m pytest tests/check_quickref_vs_routes.py -q` 的结果是 `no tests ran`，这意味着 task 10 当前列出的验证命令并不能证明速查表同步真的被检查到了。
  3. **任务 9 / 任务 10 存在测试路径漂移。** task 9 明确要把 `tests/test_architecture_fitness.py` 迁到 `tests/architecture/test_architecture_fitness.py`，但 task 10 的验证命令仍指向旧路径 `tests/test_architecture_fitness.py`。如果执行到后期不修正文案，task 10 的命令会变成陈旧入口。
  4. **任务 2 的改造起点表述仍沿用旧事实。** 它要求“把 `ScheduleService.__init__` 的 12 个仓储参数搬入仓储束”，但真实构造器不是这种形态；这会误导执行拆分方式与回归设计。

  另外，第三轮也确认了一个重要正面事实：并不是 plan 中所有 `tests/regression_*.py` 验证命令都空转。由于 `tests/conftest.py` 已为 `regression_*.py + main()` 提供了自定义收集逻辑，诸如 `tests/regression_schedule_service_facade_delegation.py`、`tests/regression_template_no_inline_event_jinja.py` 的 pytest 命令是会真正执行的。问题集中在少数不满足该收集约定、却仍被 plan 写成 pytest 入口的脚本。
- 结论:

  第三轮结论：当前 merged plan 还不是严格意义上的“可直接执行手册”。在进入实施前，必须先修正函数归属、空转验证命令与迁移后的旧测试路径引用。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `tests/conftest.py`
  - `tests/check_quickref_vs_routes.py`
  - `tests/regression_schedule_service_facade_delegation.py`
  - `tests/regression_template_no_inline_event_jinja.py`
- 下一步建议:

  汇总三轮结论，给出最终 verdict 与最小必改清单，然后再决定是否将该 merged plan 作为唯一执行 plan。
- 问题:
  - [高] 文档: 任务5兼容函数文件归属错误
  - [高] 测试: 任务10速查表验证命令不会真正执行检查
  - [中] 测试: 任务9迁移后任务10仍引用旧测试路径
  - [中] 可维护性: 任务2仍沿用过时的构造器事实

## 最终结论

综合三轮审查，`.limcode/plans/20260405_技术债务最终合并修复plan.md` 可以作为**唯一权威执行 plan 的候选版本**，但**当前文本仍不宜原样直接开工**。它的优势是真正覆盖了已确认债务、总体结构克制、明确限制了兼容桥/静默回退/总抽象扩张，并且与 Win7 / Python 3.8 / Chrome109 / 现有安装包链路 / 现有数据库迁移链路边界总体一致。真正阻碍其“直接执行”的，不是方向错误，而是少量但关键的执行级文档缺陷：任务 5 helper 归属写错、任务 10 的速查表校验命令当前空转、任务 9/10 的测试迁移路径前后不一致、任务 2 仍沿用过时的构造器事实，以及任务 8 对现有行内脚本与静默吞异常的清理要求仍不够硬。

因此最终判定是：**有条件接受**。先修正上述文档硬伤，再执行该 merged plan；修正后，它仍然是当前仓库最值得继续使用的单一执行 plan。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnlybhst-etd4bt",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T16:06:01.770Z",
  "finalizedAt": "2026-04-05T16:06:01.770Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "20260405 最终合并修复plan三轮深度review",
    "date": "2026-04-05",
    "overview": "针对 .limcode/plans/20260405_技术债务最终合并修复plan.md 的三轮深审，核对真实代码引用链、验证命令有效性与反兜底约束可落地性。"
  },
  "scope": {
    "markdown": "# 20260405 最终合并修复plan三轮深度review\n\n## 审查对象\n- `.limcode/plans/20260405_技术债务最终合并修复plan.md`\n\n## 审查目标\n1. 判断该 merged plan 在 Win7 / Python 3.8 / `Chrome109` / 现有安装包链路 / 现有数据库迁移链路边界下，是否真的可执行。\n2. 判断该 plan 是否足够优雅、简洁、逻辑严谨，且不引入新的兼容桥、静默回退、过度抽象或第二事实源。\n3. 结合真实代码与引用链，确认 plan 中的文件路径、函数归属、验证命令、批次顺序与当前仓库现状是否一致。\n\n## 审查方法\n- 对照 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 与真实代码逐项核对。\n- 抽读调度主链、配置链、路由装配、模板/前端、数据基础设施、测试门禁与文档入口。\n- 对关键验证命令做最小实际执行，确认不是纸面可运行。\n\n## 先行结论\n- 该 merged plan 相比两份原始 plan 明显更强：覆盖面完整、反兜底约束明确、整体方向正确，已经是当前仓库最适合作为唯一执行 plan 的版本。\n- 但它**仍不适合原样直接开工**：当前文本还残留若干执行级硬伤，尤其是任务 5 的函数归属写错、任务 8/10 的验证口径与真实测试不完全匹配、任务 9/10 之间存在测试路径漂移。\n- 结论：**有条件通过**。应先修正文档中的少数硬伤，再按批次执行；若不先修正，实施阶段会出现“按 plan 搜不到函数 / 命令跑过却没验证到目标 / 迁移后仍引用旧测试路径”的偏差。"
  },
  "summary": {
    "latestConclusion": "综合三轮审查，`.limcode/plans/20260405_技术债务最终合并修复plan.md` 可以作为**唯一权威执行 plan 的候选版本**，但**当前文本仍不宜原样直接开工**。它的优势是真正覆盖了已确认债务、总体结构克制、明确限制了兼容桥/静默回退/总抽象扩张，并且与 Win7 / Python 3.8 / Chrome109 / 现有安装包链路 / 现有数据库迁移链路边界总体一致。真正阻碍其“直接执行”的，不是方向错误，而是少量但关键的执行级文档缺陷：任务 5 helper 归属写错、任务 10 的速查表校验命令当前空转、任务 9/10 的测试迁移路径前后不一致、任务 2 仍沿用过时的构造器事实，以及任务 8 对现有行内脚本与静默吞异常的清理要求仍不够硬。\n\n因此最终判定是：**有条件接受**。先修正上述文档硬伤，再执行该 merged plan；修正后，它仍然是当前仓库最值得继续使用的单一执行 plan。",
    "recommendedNextAction": "先做一次 plan 文本勘误：修正 task 2 / task 5 / task 8 / task 10 的事实与命令，再以该文件为唯一执行 plan 进入批次 0。",
    "reviewedModules": [
      ".limcode/plans/20260405_技术债务最终合并修复plan.md",
      "web/routes/",
      "web/viewmodels/",
      "web/bootstrap/factory.py",
      "core/infrastructure/database.py",
      "core/infrastructure/backup.py",
      "templates/system/logs.html",
      "templates/system/backup.html",
      "templates/base.html",
      "web_new_test/templates/base.html",
      "templates/scheduler/gantt.html",
      "web_new_test/templates/scheduler/gantt.html",
      "web/bootstrap/static_versioning.py",
      "tests/regression_template_no_inline_event_jinja.py",
      "static/js/",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "tests/conftest.py",
      "tests/check_quickref_vs_routes.py",
      "tests/regression_schedule_service_facade_delegation.py",
      "tests/test_architecture_fitness.py",
      "web/routes/scheduler.py",
      "web/routes/scheduler_analysis.py",
      "web/routes/system_logs.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 9,
    "severity": {
      "high": 2,
      "medium": 7,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "R1",
      "title": "第一轮：覆盖面、边界与达成性审查",
      "status": "completed",
      "recordedAt": "2026-04-05T16:04:40.335Z",
      "summaryMarkdown": "对 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 与真实仓库现状逐项对照后，结论是：该 plan 的问题覆盖面与总体批次顺序明显优于旧版，方向上可以支撑本轮治理目标；但当前基线体量比文档叙述更大，且入口链仍未就位，导致任务 1 / 任务 2 / 任务 7 / 任务 10 的前置约束比文档看起来更硬。\n\n关键事实：\n- `core/services/scheduler/` 当前仍有 45 个平铺文件，`web/routes/` 当前仍有 59 个平铺文件。\n- `web/routes/` 中实际存在 `182` 处直接 `Service(g.db, ...)` 构造，远超任务 2 列举的第一、第二批样本范围。\n- 根 `README.md`、`开发文档/README.md`、`audit/README.md`、`.github/workflows/quality.yml`、`scripts/run_quality_gate.py` 当前均不存在。\n- 当前代码已有部分正向进展，不能被 plan 叙述掩盖：`web/routes/scheduler.py` 已是薄门面；`web/routes/scheduler_analysis.py` + `web/viewmodels/scheduler_analysis_vm.py`、`web/routes/system_logs.py` + `web/viewmodels/system_logs_vm.py` 已经部分落实页面组装下沉。\n\n本轮结论：plan 的主骨架成立，但任务 1/10 应被视为真实前置条件，任务 2 与任务 7 需要把“残余清点与退出条件”写得更刚性，不能只停留在方向正确。",
      "conclusionMarkdown": "第一轮结论：该 merged plan 覆盖面充足、边界约束正确，但其执行前提比文本表现得更严格；若不先补入口链与残余台账，后续批次会出现治理范围失真。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/routes/dashboard.py"
        },
        {
          "path": "web/routes/material.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/process_op_types.py"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "web/routes/scheduler.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/viewmodels/scheduler_analysis_vm.py"
        },
        {
          "path": "web/viewmodels/system_logs_vm.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "core/infrastructure/backup.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "web/routes/",
        "web/viewmodels/",
        "web/bootstrap/factory.py",
        "core/infrastructure/database.py",
        "core/infrastructure/backup.py"
      ],
      "recommendedNextAction": "进入第二轮，重点审查该 plan 的实现优雅性、反兜底约束与验证口径是否与真实模板/前端/静态资源实现一致。",
      "findingIds": [
        "request-scope-rollout-underestimated",
        "docs-and-gate-bootstrap-missing",
        "backup-hotspot-plan-understated"
      ]
    },
    {
      "id": "R2",
      "title": "第二轮：实现优雅性、反兜底约束与前端协议审查",
      "status": "completed",
      "recordedAt": "2026-04-05T16:05:06.321Z",
      "summaryMarkdown": "第二轮重点检查 merged plan 是否真的贯彻“少兼容桥、少静默回退、少总抽象”的治理目标。结论是：该 plan 的**设计方向是正确的**，而且比旧版更克制——`web/bootstrap/request_services.py`、`core/services/scheduler/repository_bundle.py`、`web/pageflows/excel_import_flow.py` / `excel_import_hooks.py`、`static/js/page_boot.js` + `data-page` / `data-*`、`config_field_spec.py` 这些提案都属于最小必要抽象，没有再造一个更大的容器、总控制器或全局注册表。\n\n但真实代码核对后，任务 8 仍有两个关键不足：\n1. **验证口径与治理目标不完全一致。** `templates/system/logs.html` 仍有行内 `<script defer>`，`templates/system/backup.html` 也有同类模式；而 task 8 给出的 `python -m pytest tests/regression_template_no_inline_event_jinja.py -q` 实际只检查“inline 事件属性 + Jinja 插值”，并不覆盖普通行内 `<script>`。\n2. **现有静默回退没有被明确要求删除。** `web/bootstrap/static_versioning.py` 仍在版本注入与 Jinja 全局安装处保留 `except Exception: pass` 级别的静默吞异常；task 8 只写了“本任务不新增新的静默后备逻辑”，但没有把“删除现有静默吞异常”写成强制动作。\n\n同时，前端现状也再次验证了 task 8 的方向没有问题：当前仓库仍没有 `data-page`、没有 `static/js/page_boot.js`，`window.__APS_GANTT__` / `window.__APS_COMMON__` 仍是主要启动协议；`templates/base.html` 与 `web_new_test/templates/base.html`、`templates/scheduler/gantt.html` 与 `web_new_test/templates/scheduler/gantt.html` 仍存在大段重复。因此 task 8 应保留，但需要把“证明方式”与“收口范围”写得更严。",
      "conclusionMarkdown": "第二轮结论：merged plan 的抽象方向总体优雅、克制，符合反兜底目标；但 task 8 当前还缺少对现有行内脚本与静默吞异常的直接清理要求，容易出现‘看起来完成，实际上旧问题仍在’的假完成。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "web_new_test/templates/base.html"
        },
        {
          "path": "templates/scheduler/gantt.html"
        },
        {
          "path": "web_new_test/templates/scheduler/gantt.html"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/common.js"
        }
      ],
      "reviewedModules": [
        "templates/system/logs.html",
        "templates/system/backup.html",
        "templates/base.html",
        "web_new_test/templates/base.html",
        "templates/scheduler/gantt.html",
        "web_new_test/templates/scheduler/gantt.html",
        "web/bootstrap/static_versioning.py",
        "tests/regression_template_no_inline_event_jinja.py",
        "static/js/"
      ],
      "recommendedNextAction": "进入第三轮，审查任务文本中的函数归属、验证命令、测试迁移路径与当前代码/测试收集机制是否一一对应。",
      "findingIds": [
        "inline-script-gate-mismatch",
        "static-versioning-silent-swallow-unspecified"
      ]
    },
    {
      "id": "R3",
      "title": "第三轮：逻辑严谨性、命令有效性与路径一致性审查",
      "status": "completed",
      "recordedAt": "2026-04-05T16:05:46.793Z",
      "summaryMarkdown": "第三轮把 merged plan 当成“执行手册”来审：不再只看方向，而是核对执行者能不能按文中路径、函数名与验证命令一步一步落地。结论是：当前版本仍有 4 个实打实的执行级问题，其中 2 个属于高严重级别。\n\n1. **任务 5 函数归属写错。** plan 把 `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta` 标到了错误文件，和真实代码不一致。\n2. **任务 10 的一个验证命令实际空转。** `tests/conftest.py` 只会把文件名以 `regression_` 开头、且定义 `main()` 的脚本收集为自定义 pytest 用例；`tests/check_quickref_vs_routes.py` 不满足这个规则。实际执行 `python -m pytest tests/check_quickref_vs_routes.py -q` 的结果是 `no tests ran`，这意味着 task 10 当前列出的验证命令并不能证明速查表同步真的被检查到了。\n3. **任务 9 / 任务 10 存在测试路径漂移。** task 9 明确要把 `tests/test_architecture_fitness.py` 迁到 `tests/architecture/test_architecture_fitness.py`，但 task 10 的验证命令仍指向旧路径 `tests/test_architecture_fitness.py`。如果执行到后期不修正文案，task 10 的命令会变成陈旧入口。\n4. **任务 2 的改造起点表述仍沿用旧事实。** 它要求“把 `ScheduleService.__init__` 的 12 个仓储参数搬入仓储束”，但真实构造器不是这种形态；这会误导执行拆分方式与回归设计。\n\n另外，第三轮也确认了一个重要正面事实：并不是 plan 中所有 `tests/regression_*.py` 验证命令都空转。由于 `tests/conftest.py` 已为 `regression_*.py + main()` 提供了自定义收集逻辑，诸如 `tests/regression_schedule_service_facade_delegation.py`、`tests/regression_template_no_inline_event_jinja.py` 的 pytest 命令是会真正执行的。问题集中在少数不满足该收集约定、却仍被 plan 写成 pytest 入口的脚本。",
      "conclusionMarkdown": "第三轮结论：当前 merged plan 还不是严格意义上的“可直接执行手册”。在进入实施前，必须先修正函数归属、空转验证命令与迁移后的旧测试路径引用。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/regression_schedule_service_facade_delegation.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "tests/conftest.py",
        "tests/check_quickref_vs_routes.py",
        "tests/regression_schedule_service_facade_delegation.py",
        "tests/regression_template_no_inline_event_jinja.py"
      ],
      "recommendedNextAction": "汇总三轮结论，给出最终 verdict 与最小必改清单，然后再决定是否将该 merged plan 作为唯一执行 plan。",
      "findingIds": [
        "task5-helper-location-mismatch",
        "task10-quickref-pytest-noop",
        "task9-task10-test-path-drift",
        "task2-constructor-fact-mismatch"
      ]
    }
  ],
  "findings": [
    {
      "id": "request-scope-rollout-underestimated",
      "severity": "medium",
      "category": "maintainability",
      "title": "请求级装配收口规模被低估",
      "descriptionMarkdown": "任务 2 的方向是正确的，但真实代码面比文档描述更大：`web/routes/` 当前有 `182` 处直接 `Service(g.db, ...)` 构造，不只是任务 2 列出的第一批与第二批几个文件。若没有“残余直接装配点总数下降到多少、哪些允许留账、何时必须清零”的明确退出条件，执行者容易在完成样板改造后误判任务已结束。",
      "recommendationMarkdown": "把任务 2 的完成判定补成可量化口径：例如列出初始总数、样板批次完成后的剩余总数、允许登记台账的条件与最晚清零批次。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/routes/dashboard.py"
        },
        {
          "path": "web/routes/material.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/process_op_types.py"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "web/routes/scheduler.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/viewmodels/scheduler_analysis_vm.py"
        },
        {
          "path": "web/viewmodels/system_logs_vm.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "core/infrastructure/backup.py"
        }
      ],
      "relatedMilestoneIds": [
        "R1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "docs-and-gate-bootstrap-missing",
      "severity": "medium",
      "category": "docs",
      "title": "入口链与质量门禁尚未落地",
      "descriptionMarkdown": "当前仓库缺少根 `README.md`、`开发文档/README.md`、`audit/README.md`、`.github/workflows/quality.yml`、`scripts/run_quality_gate.py`。这说明任务 1 与任务 10 不是普通收尾项，而是后续治理的真实前置条件。并且任务 1 要求根 `README.md` 直接链接 `开发文档/README.md`，但该文件被放到任务 10 才补齐，存在前后依赖倒置。",
      "recommendationMarkdown": "把 `开发文档/README.md` 与 `audit/README.md` 的最小入口版前移到任务 1，或把任务 1 的根 README 链接要求改成“先链接当前已存在入口，任务 10 再补全开发文档总索引”。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/routes/dashboard.py"
        },
        {
          "path": "web/routes/material.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/process_op_types.py"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "web/routes/scheduler.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/viewmodels/scheduler_analysis_vm.py"
        },
        {
          "path": "web/viewmodels/system_logs_vm.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "core/infrastructure/backup.py"
        }
      ],
      "relatedMilestoneIds": [
        "R1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "backup-hotspot-plan-understated",
      "severity": "medium",
      "category": "maintainability",
      "title": "数据基础设施任务对 backup 热点描述不足",
      "descriptionMarkdown": "任务 7 的标题明确要拆 `database.py`、`backup.py` 热点，但步骤文本主要围绕 `database.py` 展开。真实代码中 `core/infrastructure/backup.py` 仍承载 `maintenance_window` 与 `BackupManager` 等核心职责，若 plan 不把这些符号的迁移顺序写清，执行者很容易只拆 `database.py` 而留下另一半热点原封不动。",
      "recommendationMarkdown": "在任务 7 中显式补写：`core/infrastructure/backup.py` 的 `maintenance_window` 迁到 `maintenance_window.py`，`BackupManager`/`restore` 迁到 `backup_restore.py`，`backup.py` 最终只留薄门面或稳定导出。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/routes/dashboard.py"
        },
        {
          "path": "web/routes/material.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/process_op_types.py"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": "web/routes/scheduler.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/viewmodels/scheduler_analysis_vm.py"
        },
        {
          "path": "web/viewmodels/system_logs_vm.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "core/infrastructure/backup.py"
        },
        {
          "path": "core/infrastructure/database.py"
        }
      ],
      "relatedMilestoneIds": [
        "R1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "inline-script-gate-mismatch",
      "severity": "medium",
      "category": "html",
      "title": "模板行内脚本治理与验证口径不一致",
      "descriptionMarkdown": "task 8 目标之一是把 `templates/system/logs.html` 的行内脚本迁出，但其验证命令使用的是 `tests/regression_template_no_inline_event_jinja.py`。该测试真实职责是扫描 `on*=\"...{{ ... }}\"` 这类 inline 事件属性 + Jinja 插值，不检查普通 `<script defer>...</script>`。因此即使 `templates/system/logs.html`、`templates/system/backup.html` 仍保留行内脚本，当前验证也可能通过。",
      "recommendationMarkdown": "为 task 8 增加一个专门的模板门禁：显式扫描目标模板中的行内 `<script>`，并把 `templates/system/backup.html` 是否一并收口写进任务范围或台账。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "web_new_test/templates/base.html"
        },
        {
          "path": "templates/scheduler/gantt.html"
        },
        {
          "path": "web_new_test/templates/scheduler/gantt.html"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/common.js"
        }
      ],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "static-versioning-silent-swallow-unspecified",
      "severity": "medium",
      "category": "maintainability",
      "title": "静态资源版本化任务未强制清理现有静默吞异常",
      "descriptionMarkdown": "真实代码中 `web/bootstrap/static_versioning.py` 在 `_versioned_url_for()` 和 `install_versioned_url_for()` 里仍保留 `except Exception: pass`。task 8 只写“优先读取清单；本任务不新增新的静默后备逻辑”，这不足以保证现有静默吞异常被删除，容易让最终实现只是‘在旧静默回退外面再包一层 manifest 优先’。",
      "recommendationMarkdown": "把 task 8 的步骤 8 改成明确动作：删除 `web/bootstrap/static_versioning.py` 里的静默 `except Exception: pass`，改为可观测、确定性的失败路径或日志记录路径，并为 manifest 读取失败补专门回归。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "templates/system/logs.html"
        },
        {
          "path": "templates/system/backup.html"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "web_new_test/templates/base.html"
        },
        {
          "path": "templates/scheduler/gantt.html"
        },
        {
          "path": "web_new_test/templates/scheduler/gantt.html"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/common.js"
        }
      ],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task5-helper-location-mismatch",
      "severity": "high",
      "category": "docs",
      "title": "任务5兼容函数文件归属错误",
      "descriptionMarkdown": "task 5 的“必须删除或收口的兼容函数”列表中，至少 3 个 helper 的文件归属与真实代码不一致：`_get_snapshot_with_optional_strict_mode` 实际位于 `core/services/scheduler/schedule_service.py`；`_build_algo_operations_with_optional_outcome` 与 `_build_freeze_window_seed_with_optional_meta` 实际都位于 `core/services/scheduler/schedule_input_collector.py`。这会直接导致执行者按 plan 搜索时定位失败，也会影响批次切分和回归补点。",
      "recommendationMarkdown": "在实施前先修正文档中的 helper 归属，并把调用方与预期删除顺序一起写清，避免后续 task 5 执行偏离真实代码。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/regression_schedule_service_facade_delegation.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task10-quickref-pytest-noop",
      "severity": "high",
      "category": "test",
      "title": "任务10速查表验证命令不会真正执行检查",
      "descriptionMarkdown": "`tests/conftest.py` 的自定义 pytest 收集只覆盖文件名以 `regression_` 开头、且定义 `main()` 的脚本。`tests/check_quickref_vs_routes.py` 虽然有 `main()`，但文件名前缀不是 `regression_`，因此 `python -m pytest tests/check_quickref_vs_routes.py -q` 的实际结果是 `no tests ran`。也就是说，task 10 目前列出的验证命令并不能证明速查表与路由实现的一致性。",
      "recommendationMarkdown": "把 task 10 的验证入口改成 `python tests/check_quickref_vs_routes.py`，或把该脚本迁成 `regression_` 风格/真正的 pytest 测试后再继续使用 pytest 命令。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/regression_schedule_service_facade_delegation.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task9-task10-test-path-drift",
      "severity": "medium",
      "category": "test",
      "title": "任务9迁移后任务10仍引用旧测试路径",
      "descriptionMarkdown": "task 9 明确要求把 `tests/test_architecture_fitness.py` 迁到 `tests/architecture/test_architecture_fitness.py`，但 task 10 的验证命令仍写 `python -m pytest tests/test_architecture_fitness.py -q`。这意味着一旦按 task 9 落地测试分层，task 10 的命令就会成为陈旧入口，破坏 plan 自己的后续一致性。",
      "recommendationMarkdown": "把后续所有测试命令统一切成目录入口或迁移后的新路径，至少在 task 10 中改为 `tests/architecture/test_architecture_fitness.py` 或 `tests/architecture/`。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/regression_schedule_service_facade_delegation.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task2-constructor-fact-mismatch",
      "severity": "medium",
      "category": "maintainability",
      "title": "任务2仍沿用过时的构造器事实",
      "descriptionMarkdown": "task 2 把 `ScheduleService` 的起点写成“12 个仓储参数构造器”，而真实 `ScheduleService.__init__` 只有 `conn`、`logger`、`op_logger` 三个入参，并在内部创建仓储成员。这个差异会误导执行者把精力放在错误的外部签名收口上，而不是内部依赖组织方式与请求级装配收口。",
      "recommendationMarkdown": "把 task 2 的表述从“构造器参数收口”改成“内部平铺依赖改为仓储束/组合对象”，并同步修正仓储数量描述。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        },
        {
          "path": "tests/regression_schedule_service_facade_delegation.py"
        },
        {
          "path": "tests/regression_template_no_inline_event_jinja.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:28823366c0f15787e52351e6a74c980e71add7073cbfd8b6ccb7b57af143300b",
    "generatedAt": "2026-04-05T16:06:01.770Z",
    "locale": "zh-CN"
  }
}
```

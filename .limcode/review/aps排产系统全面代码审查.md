# APS排产系统全面代码审查
- 日期: 2026-04-05
- 概述: 对 APS 排产测试系统进行端到端全面代码审查，覆盖架构、服务层、算法层、路由层及测试层。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# APS 排产系统全面代码审查

**审查日期**: 2026-04-05  
**审查范围**: 全工作区端到端审查  
**审查目标**: 识别架构问题、代码重复、可维护性风险、BUG 及安全隐患

## 审查概览

本项目是一个面向回转壳体单元的智能排产系统（APS），基于 Flask + SQLite 构建，目标运行于 Win7 单机环境。

项目采用四层分层架构：
- **模型层** (`core/models/`): 22 个数据模型
- **数据层** (`data/repositories/`): 24 个仓储类
- **服务层** (`core/services/`): 按领域划分（排产/工艺/设备/人员/物料/报表/系统）
- **路由层** (`web/routes/`): Flask 蓝图 + 视图模型

算法层 (`core/algorithms/`) 包含贪心调度、分发规则、评估函数和排序策略。

## 评审摘要

- 当前状态: 已完成
- 已审模块: app.py, app_new_ui.py, config.py, schema.sql, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_summary.py, core/algorithms/, core/infrastructure/database.py, core/infrastructure/transaction.py, web/routes/ (Excel路由组), web/routes/excel_utils.py, web/routes/normalizers.py, web/bootstrap/security.py, web/error_handlers.py, tests/ (测试套件), core/services/process/unit_excel/parser.py, core/services/scheduler/, core/infrastructure/, web/routes/, web/bootstrap/, tests/
- 当前进度: 已记录 4 个里程碑；最新：M4
- 里程碑总数: 4
- 已完成里程碑: 4
- 问题总数: 6
- 问题严重级别分布: 高 0 / 中 3 / 低 3
- 最新结论: ## 审查总结 本次基线审查识别的 6 项发现中，U-1 / U-2 / U-3 与 U-6 已完成收口并同步到统一问题映射；当前仍开放的主要技术债为 `F-SCHED-DEPS` 与 `F-TEST-STRUCT`。 ### 当前判断 - 已收口：Excel confirm 重复控制流、调度摘要上下文参数面、双入口复制、工作表类型守卫口径 - 仍开放：排产服务仓储依赖偏多、测试环境搭建重复 - 结论：项目继续维持“有条件通过”，后续可在正常迭代中处理剩余两项低优先级技术债。
- 下一步建议: 优先跟踪仍处于开放状态的 F-SCHED-DEPS 与 F-TEST-STRUCT，并在统一台账中保留 U-1 / U-2 / U-3 / U-6 的已修复验收记录。
- 总体结论: 有条件通过

## 评审发现

### 两个入口文件近乎完全重复

- ID: F-ENTRY-DUP
- 别名: app-entrypoint-duplication, U-3
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 已修复
- 相关里程碑: M1
- 说明:

  该问题已通过参数化入口主流程收口：共享启动逻辑集中到 `web/bootstrap/entrypoint.py` 的 `app_main()` / `configure_runtime_contract()`，`app.py` 与 `app_new_ui.py` 只保留界面模式差异和壳层调用。这样既保留了 `runtime_base_dir(anchor_file=__file__)` 的锚点语义，也消除了双点同步维护风险。
- 建议:

  继续保持两个壳层仅承载界面模式差异；后续若新增启动流程改动，应优先落在共享入口模块。
- 证据:
  - `web/bootstrap/entrypoint.py:133-286`
  - `app.py:29-62`
  - `app_new_ui.py:29-62`

### 排产摘要构建函数参数过多

- ID: F-SUMMARY-ARGS
- 别名: scheduler-summary-wide-context, U-2
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 已修复
- 相关里程碑: M2
- 说明:

  该问题已通过 `SummaryBuildContext` 与具名状态对象收口。`build_result_summary()` 现以 `ctx=` 作为主路径，同时保留关键字兼容层；`_build_result_summary_obj()` 与 `_algo_dict()` 也已改为消费上下文/状态对象，9 级摘要截断梯度则收敛到 `DEFAULT_TRUNCATION_TIERS`。
- 建议:

  继续将新代码统一走 `ctx=` 主路径，并保留回归用例覆盖关键字兼容入口，防止兼容层漂移。
- 证据:
  - `core/services/scheduler/schedule_summary.py:175-229`
  - `core/services/scheduler/schedule_summary.py:360-459`
  - `core/services/scheduler/schedule_summary_assembly.py:279-363`
  - `core/services/scheduler/schedule_orchestrator.py:148-183`

### 排产服务依赖多个仓储

- ID: F-SCHED-DEPS
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  ScheduleService.__init__() 初始化 10 个仓储实例（batch_repo, op_repo, part_op_repo, group_repo, machine_repo, operator_repo, operator_machine_repo, supplier_repo, schedule_repo, history_repo）。虽然 _run_schedule_impl() 已拆分为 collect → orchestrate → persist 三步，但服务类本身仍然是拀点，所有仓储都通过它传入子模块。
- 建议:

  考虑将仓储依赖分组，或采用服务定位器模式减少直接依赖。
- 证据:
  - `core/services/scheduler/schedule_service.py:132-160`
  - `core/services/scheduler/schedule_service.py`

### 路由层工具函数大量重复

- ID: F-ROUTE-DUP
- 别名: excel-import-confirm-flow-duplication, U-1
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 已修复
- 相关里程碑: M3
- 说明:

  该问题已通过 `web/routes/excel_utils.py` 的组合式公共能力收口：确认载荷解析、基线漂移守卫、错误行收集/文案拼装与导入统计提取统一下沉，而各路由继续保留自己的页面回显函数与行级校验闭包，避免了过度抽象。
- 建议:

  后续新增 Excel confirm 路由时继续复用这些小粒度公共能力，不再回到“大骨架函数”或分散复制的写法。
- 证据:
  - `web/routes/excel_utils.py:115-162`
  - `web/routes/equipment_excel_links.py:165-228`
  - `web/routes/process_excel_suppliers.py:197-292`
  - `web/routes/scheduler_excel_batches.py:266-362`

### 测试结构职责边界模糊

- ID: F-TEST-STRUCT
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  测试套件规模庞大（247 个回归测试 + 15 个冒烟测试 + 30+ 个单元测试/端到端测试），但各类测试的职责边界不够清晰：回归测试和冒烟测试都是独立脚本（带 main() 函数），运行方式不统一：回归测试经 conftest.py 自动收集，冒烟测试需手动运行。各冒烟测试内部包含大量重复的环境搞建代码（临时目录、DB 初始化、环境变量设置）。
- 建议:

  考虑将冒烟测试的通用环境搞建逻辑提取为共享 fixture，统一运行入口。

### 工作表解析器缺少类型守卫

- ID: F-PARSER-TYPE
- 别名: U-6
- 严重级别: 低
- 分类: 类型安全
- 跟踪状态: 已修复
- 相关里程碑: M4
- 说明:

  `core/services/process/unit_excel/parser.py` 现已在 `UnitExcelParser.parse()` 中对 `wb.active` / `wb[sheet_name]` 返回结果补上 `Worksheet` 类型守卫：当返回对象不是 `Worksheet` 时会直接抛出 `ValueError`。本项保留为已完成整改留痕，后续只需保持该守卫与静态检查口径一致。
- 建议:

  保持现有 `Worksheet` 类型守卫，不再回退到无类型检查的 `iter_rows()` 调用路径。
- 证据:
  - `core/services/process/unit_excel/parser.py:45-52`
  - `core/services/process/unit_excel/parser.py`

## 评审里程碑

### M1 · 入口文件与整体架构审查

- 状态: 已完成
- 记录时间: 2026-04-05T03:27:50.211Z
- 已审模块: app.py, app_new_ui.py, config.py, schema.sql
- 摘要:

  审查了 `app.py`、`app_new_ui.py`、`config.py`、`schema.sql` 及整体分层架构。

  **架构整体评估**：项目采用清晰的四层架构（模型→仓储→服务→路由），领域划分合理（排产/工艺/设备/人员/物料/报表/系统），符合 ADR-0005 的设计决策。

  **关键发现**：
  1. `app.py` 与 `app_new_ui.py` 代码重复率极高（约 99%），仅 `ui_mode` 参数不同（"default" vs "new_ui"），违反了 DRY 原则。
  2. `config.py` 设计合理，`BASE_DIR` 的 frozen/非 frozen 判断和路径兜底处理考虑周全。
  3. `schema.sql` 数据库设计完整，394 行覆盖 17 张表，索引设计充分。布尔字段统一用字符串枚举（"yes"/"no"），与 Excel 导入导出对齐，是有意识的设计选择。
  4. 排产服务层文件数量庞大（44 个文件），表明之前做过拆分，但 `schedule_service.py` 仍然是核心编排枢纽。
- 结论:

  审查了 `app.py`、`app_new_ui.py`、`config.py`、`schema.sql` 及整体分层架构。 **架构整体评估**：项目采用清晰的四层架构（模型→仓储→服务→路由），领域划分合理（排产/工艺/设备/人员/物料/报表/系统），符合 ADR-0005 的设计决策。 **关键发现**： 1. `app.py` 与 `app_new_ui.py` 代码重复率极高（约 99%），仅 `ui_mode` 参数不同（"default" vs "new_ui"），违反了 DRY 原则。 2. `config.py` 设计合理，`BASE_DIR` 的 frozen/非 frozen 判断和路径兜底处理考虑周全。 3. `schema.sql` 数据库设计完整，394 行覆盖 17 张表，索引设计充分。布尔字段统一用字符串枚举（"yes"/"no"），与 Excel 导入导出对齐，是有意识的设计选择。 4. 排产服务层文件数量庞大（44 个文件），表明之前做过拆分，但 `schedule_service.py` 仍然是核心编排枢纽。
- 问题:
  - [中] 可维护性: 两个入口文件近乎完全重复

### M2 · 排产核心服务层审查

- 状态: 已完成
- 记录时间: 2026-04-05T03:29:36.163Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_summary.py, core/algorithms/, core/infrastructure/database.py, core/infrastructure/transaction.py
- 摘要:

  审查了排产核心服务链路（ScheduleService → 输入收集 → 编排 → 持久化 → 摘要构建）和算法层。

  **积极发现**：
  1. `_run_schedule_impl()` 已从之前的 323 行"上帝方法"拆分为三步清晰的编排流程：`collect_schedule_run_input()` → `orchestrate_schedule_run()` → `persist_schedule()`，每步都提取到独立模块。
  2. `schedule_summary.py` 已拆分为 4 个子模块（assembly/freeze/degradation 以及主模块），结构比注释中描述的原始状态改善显著。
  3. 算法层设计合理：`sort_strategies.py` 使用策略模式（4 种排序策略 + 工厂类），`dispatch_rules.py` 支持 SLACK/CR/ATC 三种调度规则，`evaluation.py` 提供完整的 ScheduleMetrics 数据类。
  4. 事务管理器支持嵌套 SAVEPOINT，是健壮的设计选择。
  5. 数据库迁移系统设计完善：包含 preflight 检查、自动备份、失败回滚，适合 Win7 单机环境。

  **问题点**：
  1. `build_result_summary()` 函数签名包含 33 个参数，虽然内部拆分良好，但调用方仍需传递大量参数。
  2. `ScheduleService` 仍依赖 10 个仓储，属于"编排中心"类型，但已通过函数拆分缓解了原有的上帝类问题。
- 结论:

  审查了排产核心服务链路（ScheduleService → 输入收集 → 编排 → 持久化 → 摘要构建）和算法层。 **积极发现**： 1. `_run_schedule_impl()` 已从之前的 323 行"上帝方法"拆分为三步清晰的编排流程：`collect_schedule_run_input()` → `orchestrate_schedule_run()` → `persist_schedule()`，每步都提取到独立模块。 2. `schedule_summary.py` 已拆分为 4 个子模块（assembly/freeze/degradation 以及主模块），结构比注释中描述的原始状态改善显著。 3. 算法层设计合理：`sort_strategies.py` 使用策略模式（4 种排序策略 + 工厂类），`dispatch_rules.py` 支持 SLACK/CR/ATC 三种调度规则，`evaluation.py` 提供完整的 ScheduleMetrics 数据类。 4. 事务管理器支持嵌套 SAVEPOINT，是健壮的设计选择。 5. 数据库迁移系统设计完善：包含 preflight 检查、自动备份、失败回滚，适合 Win7 单机环境。 **问题点**： 1. `build_result_summary()` 函数签名包含 33 个参数，虽然内部拆分良好，但调用方仍需传递大量参数。 2. `ScheduleService` 仍依赖 10 个仓储，属于"编排中心"类型，但已通过函数拆分缓解了原有的上帝类问题。
- 问题:
  - [中] 可维护性: 排产摘要构建函数参数过多
  - [低] 可维护性: 排产服务依赖多个仓储

### M3 · 路由层与前端基础设施审查

- 状态: 已完成
- 记录时间: 2026-04-05T03:31:10.476Z
- 已审模块: web/routes/ (Excel路由组), web/routes/excel_utils.py, web/routes/normalizers.py, web/bootstrap/security.py, web/error_handlers.py
- 摘要:

  审查了路由层的 Excel 导入/导出文件、通用工具和安全基础设施。

  **积极发现**：
  1. `excel_utils.py` 已提供了 7 个通用函数（`parse_import_mode`、`build_preview_baseline_token`、`preview_baseline_matches`、`flash_import_result`、`ensure_unique_ids`、`read_uploaded_xlsx`、`send_excel_template_file`），说明团队已经意识到代码复用的重要性并做了部分提取。
  2. 预览基线签名机制设计良好：使用 SHA256 摘要 + `hmac.compare_digest` 安全比较，可以防止预览与确认之间数据被篡改。
  3. 安全层实现完善：`ensure_secret_key` 支持环境变量 → 文件持久化 → 运行时生成的三级策略，`SESSION_COOKIE_HTTPONLY=True` + `SAMESITE=Lax`，安全头包含 `X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Permissions-Policy`。
  4. `normalizers.py` 提供了集中的规范化函数（优先级、齐套状态、日期类型、是否布尔值、版本号解析）。
  5. 错误处理器统一处理了 `AppError`、404、413、500，并根据请求类型返回 JSON 或 HTML 页面。

  **问题点**：
  `_strict_mode_enabled()` 在 6 个路由文件中几乎完全相同地重复，`_parse_preview_rows_json()` 在 3 个文件中重复。虽然已有 `excel_utils.py` 作为提取目标，但这些函数尚未迁入。
- 结论:

  审查了路由层的 Excel 导入/导出文件、通用工具和安全基础设施。 **积极发现**： 1. `excel_utils.py` 已提供了 7 个通用函数（`parse_import_mode`、`build_preview_baseline_token`、`preview_baseline_matches`、`flash_import_result`、`ensure_unique_ids`、`read_uploaded_xlsx`、`send_excel_template_file`），说明团队已经意识到代码复用的重要性并做了部分提取。 2. 预览基线签名机制设计良好：使用 SHA256 摘要 + `hmac.compare_digest` 安全比较，可以防止预览与确认之间数据被篡改。 3. 安全层实现完善：`ensure_secret_key` 支持环境变量 → 文件持久化 → 运行时生成的三级策略，`SESSION_COOKIE_HTTPONLY=True` + `SAMESITE=Lax`，安全头包含 `X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Permissions-Policy`。 4. `normalizers.py` 提供了集中的规范化函数（优先级、齐套状态、日期类型、是否布尔值、版本号解析）。 5. 错误处理器统一处理了 `AppError`、404、413、500，并根据请求类型返回 JSON 或 HTML 页面。 **问题点**： `_strict_mode_enabled()` 在 6 个路由文件中几乎完全相同地重复，`_parse_preview_rows_json()` 在 3 个文件中重复。虽然已有 `excel_utils.py` 作为提取目标，但这些函数尚未迁入。
- 问题:
  - [中] 可维护性: 路由层工具函数大量重复

### M4 · 测试层与类型安全审查

- 状态: 已完成
- 记录时间: 2026-04-05T03:32:03.314Z
- 已审模块: tests/ (测试套件), core/services/process/unit_excel/parser.py
- 摘要:

  审查了测试层结构和类型安全问题。

  **测试规模**：
  - 247 个回归测试文件（`regression_*.py`）
  - 15 个冒烟测试文件（`smoke_*.py`）
  - 30+ 个单元/集成/端到端测试文件（`test_*.py`、`run_*.py`）
  - 总计约 290+ 个测试文件

  **积极发现**：
  1. 回归测试覆盖极其全面：命名规范统一（`regression_<功能描述>.py`），每个文件对应一个明确的回归场景。
  2. `conftest.py` 设计良好：自动将 `regression_*.py` 中的 `main()` 函数包装为 pytest 测试用例，无需修改原始文件。
  3. 冒烟测试独立性强：每个测试使用独立临时目录和数据库，避免相互污染。
  4. 存在专门的安全测试（XSS 检测、安全头验证、会话安全等）。

  **问题点**：
  1. 冒烟测试文件间存在大量重复的环境搭建代码（临时目录创建、环境变量设置、数据库初始化），可提取为共享的辅助函数。
  2. `unit_excel/parser.py` 存在类型安全问题：`wb.active` 返回的工作表类型不确定，直接调用 `iter_rows()` 在静态检查中报错。
- 结论:

  审查了测试层结构和类型安全问题。 **测试规模**： - 247 个回归测试文件（`regression_*.py`） - 15 个冒烟测试文件（`smoke_*.py`） - 30+ 个单元/集成/端到端测试文件（`test_*.py`、`run_*.py`） - 总计约 290+ 个测试文件 **积极发现**： 1. 回归测试覆盖极其全面：命名规范统一（`regression_<功能描述>.py`），每个文件对应一个明确的回归场景。 2. `conftest.py` 设计良好：自动将 `regression_*.py` 中的 `main()` 函数包装为 pytest 测试用例，无需修改原始文件。 3. 冒烟测试独立性强：每个测试使用独立临时目录和数据库，避免相互污染。 4. 存在专门的安全测试（XSS 检测、安全头验证、会话安全等）。 **问题点**： 1. 冒烟测试文件间存在大量重复的环境搭建代码（临时目录创建、环境变量设置、数据库初始化），可提取为共享的辅助函数。 2. `unit_excel/parser.py` 存在类型安全问题：`wb.active` 返回的工作表类型不确定，直接调用 `iter_rows()` 在静态检查中报错。
- 问题:
  - [低] 测试: 测试结构职责边界模糊
  - [低] 类型安全: 工作表解析器缺少类型守卫

## 最终结论

## 审查总结

本次基线审查识别的 6 项发现中，U-1 / U-2 / U-3 与 U-6 已完成收口并同步到统一问题映射；当前仍开放的主要技术债为 `F-SCHED-DEPS` 与 `F-TEST-STRUCT`。

### 当前判断

- 已收口：Excel confirm 重复控制流、调度摘要上下文参数面、双入口复制、工作表类型守卫口径
- 仍开放：排产服务仓储依赖偏多、测试环境搭建重复
- 结论：项目继续维持“有条件通过”，后续可在正常迭代中处理剩余两项低优先级技术债。
## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnl7aqyh-u4rjlu",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T07:24:21.000Z",
  "finalizedAt": "2026-04-05T07:24:21.000Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "APS排产系统全面代码审查",
    "date": "2026-04-05",
    "overview": "对 APS 排产测试系统进行端到端全面代码审查，覆盖架构、服务层、算法层、路由层及测试层。"
  },
  "scope": {
    "markdown": "# APS 排产系统全面代码审查\n\n**审查日期**: 2026-04-05  \n**审查范围**: 全工作区端到端审查  \n**审查目标**: 识别架构问题、代码重复、可维护性风险、BUG 及安全隐患\n\n## 审查概览\n\n本项目是一个面向回转壳体单元的智能排产系统（APS），基于 Flask + SQLite 构建，目标运行于 Win7 单机环境。\n\n项目采用四层分层架构：\n- **模型层** (`core/models/`): 22 个数据模型\n- **数据层** (`data/repositories/`): 24 个仓储类\n- **服务层** (`core/services/`): 按领域划分（排产/工艺/设备/人员/物料/报表/系统）\n- **路由层** (`web/routes/`): Flask 蓝图 + 视图模型\n\n算法层 (`core/algorithms/`) 包含贪心调度、分发规则、评估函数和排序策略。"
  },
  "summary": {
    "latestConclusion": "## 审查总结\n\n本次基线审查识别的 6 项发现中，U-1 / U-2 / U-3 与 U-6 已完成收口并同步到统一问题映射；当前仍开放的主要技术债为 `F-SCHED-DEPS` 与 `F-TEST-STRUCT`。\n\n### 当前判断\n\n- 已收口：Excel confirm 重复控制流、调度摘要上下文参数面、双入口复制、工作表类型守卫口径\n- 仍开放：排产服务仓储依赖偏多、测试环境搭建重复\n- 结论：项目继续维持“有条件通过”，后续可在正常迭代中处理剩余两项低优先级技术债。",
    "recommendedNextAction": "优先跟踪仍处于开放状态的 F-SCHED-DEPS 与 F-TEST-STRUCT，并在统一台账中保留 U-1 / U-2 / U-3 / U-6 的已修复验收记录。",
    "reviewedModules": [
      "app.py",
      "app_new_ui.py",
      "config.py",
      "schema.sql",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_summary.py",
      "core/algorithms/",
      "core/infrastructure/database.py",
      "core/infrastructure/transaction.py",
      "web/routes/ (Excel路由组)",
      "web/routes/excel_utils.py",
      "web/routes/normalizers.py",
      "web/bootstrap/security.py",
      "web/error_handlers.py",
      "tests/ (测试套件)",
      "core/services/process/unit_excel/parser.py",
      "core/services/scheduler/",
      "core/infrastructure/",
      "web/routes/",
      "web/bootstrap/",
      "tests/"
    ]
  },
  "stats": {
    "totalMilestones": 4,
    "completedMilestones": 4,
    "totalFindings": 6,
    "severity": {
      "high": 0,
      "medium": 3,
      "low": 3
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "入口文件与整体架构审查",
      "status": "completed",
      "recordedAt": "2026-04-05T03:27:50.211Z",
      "summaryMarkdown": "审查了 `app.py`、`app_new_ui.py`、`config.py`、`schema.sql` 及整体分层架构。\n\n**架构整体评估**：项目采用清晰的四层架构（模型→仓储→服务→路由），领域划分合理（排产/工艺/设备/人员/物料/报表/系统），符合 ADR-0005 的设计决策。\n\n**关键发现**：\n1. `app.py` 与 `app_new_ui.py` 代码重复率极高（约 99%），仅 `ui_mode` 参数不同（\"default\" vs \"new_ui\"），违反了 DRY 原则。\n2. `config.py` 设计合理，`BASE_DIR` 的 frozen/非 frozen 判断和路径兜底处理考虑周全。\n3. `schema.sql` 数据库设计完整，394 行覆盖 17 张表，索引设计充分。布尔字段统一用字符串枚举（\"yes\"/\"no\"），与 Excel 导入导出对齐，是有意识的设计选择。\n4. 排产服务层文件数量庞大（44 个文件），表明之前做过拆分，但 `schedule_service.py` 仍然是核心编排枢纽。",
      "conclusionMarkdown": "审查了 `app.py`、`app_new_ui.py`、`config.py`、`schema.sql` 及整体分层架构。 **架构整体评估**：项目采用清晰的四层架构（模型→仓储→服务→路由），领域划分合理（排产/工艺/设备/人员/物料/报表/系统），符合 ADR-0005 的设计决策。 **关键发现**： 1. `app.py` 与 `app_new_ui.py` 代码重复率极高（约 99%），仅 `ui_mode` 参数不同（\"default\" vs \"new_ui\"），违反了 DRY 原则。 2. `config.py` 设计合理，`BASE_DIR` 的 frozen/非 frozen 判断和路径兜底处理考虑周全。 3. `schema.sql` 数据库设计完整，394 行覆盖 17 张表，索引设计充分。布尔字段统一用字符串枚举（\"yes\"/\"no\"），与 Excel 导入导出对齐，是有意识的设计选择。 4. 排产服务层文件数量庞大（44 个文件），表明之前做过拆分，但 `schedule_service.py` 仍然是核心编排枢纽。",
      "evidence": [],
      "reviewedModules": [
        "app.py",
        "app_new_ui.py",
        "config.py",
        "schema.sql"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-ENTRY-DUP"
      ]
    },
    {
      "id": "M2",
      "title": "排产核心服务层审查",
      "status": "completed",
      "recordedAt": "2026-04-05T03:29:36.163Z",
      "summaryMarkdown": "审查了排产核心服务链路（ScheduleService → 输入收集 → 编排 → 持久化 → 摘要构建）和算法层。\n\n**积极发现**：\n1. `_run_schedule_impl()` 已从之前的 323 行\"上帝方法\"拆分为三步清晰的编排流程：`collect_schedule_run_input()` → `orchestrate_schedule_run()` → `persist_schedule()`，每步都提取到独立模块。\n2. `schedule_summary.py` 已拆分为 4 个子模块（assembly/freeze/degradation 以及主模块），结构比注释中描述的原始状态改善显著。\n3. 算法层设计合理：`sort_strategies.py` 使用策略模式（4 种排序策略 + 工厂类），`dispatch_rules.py` 支持 SLACK/CR/ATC 三种调度规则，`evaluation.py` 提供完整的 ScheduleMetrics 数据类。\n4. 事务管理器支持嵌套 SAVEPOINT，是健壮的设计选择。\n5. 数据库迁移系统设计完善：包含 preflight 检查、自动备份、失败回滚，适合 Win7 单机环境。\n\n**问题点**：\n1. `build_result_summary()` 函数签名包含 33 个参数，虽然内部拆分良好，但调用方仍需传递大量参数。\n2. `ScheduleService` 仍依赖 10 个仓储，属于\"编排中心\"类型，但已通过函数拆分缓解了原有的上帝类问题。",
      "conclusionMarkdown": "审查了排产核心服务链路（ScheduleService → 输入收集 → 编排 → 持久化 → 摘要构建）和算法层。 **积极发现**： 1. `_run_schedule_impl()` 已从之前的 323 行\"上帝方法\"拆分为三步清晰的编排流程：`collect_schedule_run_input()` → `orchestrate_schedule_run()` → `persist_schedule()`，每步都提取到独立模块。 2. `schedule_summary.py` 已拆分为 4 个子模块（assembly/freeze/degradation 以及主模块），结构比注释中描述的原始状态改善显著。 3. 算法层设计合理：`sort_strategies.py` 使用策略模式（4 种排序策略 + 工厂类），`dispatch_rules.py` 支持 SLACK/CR/ATC 三种调度规则，`evaluation.py` 提供完整的 ScheduleMetrics 数据类。 4. 事务管理器支持嵌套 SAVEPOINT，是健壮的设计选择。 5. 数据库迁移系统设计完善：包含 preflight 检查、自动备份、失败回滚，适合 Win7 单机环境。 **问题点**： 1. `build_result_summary()` 函数签名包含 33 个参数，虽然内部拆分良好，但调用方仍需传递大量参数。 2. `ScheduleService` 仍依赖 10 个仓储，属于\"编排中心\"类型，但已通过函数拆分缓解了原有的上帝类问题。",
      "evidence": [],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_summary.py",
        "core/algorithms/",
        "core/infrastructure/database.py",
        "core/infrastructure/transaction.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-SUMMARY-ARGS",
        "F-SCHED-DEPS"
      ]
    },
    {
      "id": "M3",
      "title": "路由层与前端基础设施审查",
      "status": "completed",
      "recordedAt": "2026-04-05T03:31:10.476Z",
      "summaryMarkdown": "审查了路由层的 Excel 导入/导出文件、通用工具和安全基础设施。\n\n**积极发现**：\n1. `excel_utils.py` 已提供了 7 个通用函数（`parse_import_mode`、`build_preview_baseline_token`、`preview_baseline_matches`、`flash_import_result`、`ensure_unique_ids`、`read_uploaded_xlsx`、`send_excel_template_file`），说明团队已经意识到代码复用的重要性并做了部分提取。\n2. 预览基线签名机制设计良好：使用 SHA256 摘要 + `hmac.compare_digest` 安全比较，可以防止预览与确认之间数据被篡改。\n3. 安全层实现完善：`ensure_secret_key` 支持环境变量 → 文件持久化 → 运行时生成的三级策略，`SESSION_COOKIE_HTTPONLY=True` + `SAMESITE=Lax`，安全头包含 `X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Permissions-Policy`。\n4. `normalizers.py` 提供了集中的规范化函数（优先级、齐套状态、日期类型、是否布尔值、版本号解析）。\n5. 错误处理器统一处理了 `AppError`、404、413、500，并根据请求类型返回 JSON 或 HTML 页面。\n\n**问题点**：\n`_strict_mode_enabled()` 在 6 个路由文件中几乎完全相同地重复，`_parse_preview_rows_json()` 在 3 个文件中重复。虽然已有 `excel_utils.py` 作为提取目标，但这些函数尚未迁入。",
      "conclusionMarkdown": "审查了路由层的 Excel 导入/导出文件、通用工具和安全基础设施。 **积极发现**： 1. `excel_utils.py` 已提供了 7 个通用函数（`parse_import_mode`、`build_preview_baseline_token`、`preview_baseline_matches`、`flash_import_result`、`ensure_unique_ids`、`read_uploaded_xlsx`、`send_excel_template_file`），说明团队已经意识到代码复用的重要性并做了部分提取。 2. 预览基线签名机制设计良好：使用 SHA256 摘要 + `hmac.compare_digest` 安全比较，可以防止预览与确认之间数据被篡改。 3. 安全层实现完善：`ensure_secret_key` 支持环境变量 → 文件持久化 → 运行时生成的三级策略，`SESSION_COOKIE_HTTPONLY=True` + `SAMESITE=Lax`，安全头包含 `X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Permissions-Policy`。 4. `normalizers.py` 提供了集中的规范化函数（优先级、齐套状态、日期类型、是否布尔值、版本号解析）。 5. 错误处理器统一处理了 `AppError`、404、413、500，并根据请求类型返回 JSON 或 HTML 页面。 **问题点**： `_strict_mode_enabled()` 在 6 个路由文件中几乎完全相同地重复，`_parse_preview_rows_json()` 在 3 个文件中重复。虽然已有 `excel_utils.py` 作为提取目标，但这些函数尚未迁入。",
      "evidence": [],
      "reviewedModules": [
        "web/routes/ (Excel路由组)",
        "web/routes/excel_utils.py",
        "web/routes/normalizers.py",
        "web/bootstrap/security.py",
        "web/error_handlers.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-ROUTE-DUP"
      ]
    },
    {
      "id": "M4",
      "title": "测试层与类型安全审查",
      "status": "completed",
      "recordedAt": "2026-04-05T03:32:03.314Z",
      "summaryMarkdown": "审查了测试层结构和类型安全问题。\n\n**测试规模**：\n- 247 个回归测试文件（`regression_*.py`）\n- 15 个冒烟测试文件（`smoke_*.py`）\n- 30+ 个单元/集成/端到端测试文件（`test_*.py`、`run_*.py`）\n- 总计约 290+ 个测试文件\n\n**积极发现**：\n1. 回归测试覆盖极其全面：命名规范统一（`regression_<功能描述>.py`），每个文件对应一个明确的回归场景。\n2. `conftest.py` 设计良好：自动将 `regression_*.py` 中的 `main()` 函数包装为 pytest 测试用例，无需修改原始文件。\n3. 冒烟测试独立性强：每个测试使用独立临时目录和数据库，避免相互污染。\n4. 存在专门的安全测试（XSS 检测、安全头验证、会话安全等）。\n\n**问题点**：\n1. 冒烟测试文件间存在大量重复的环境搭建代码（临时目录创建、环境变量设置、数据库初始化），可提取为共享的辅助函数。\n2. `unit_excel/parser.py` 存在类型安全问题：`wb.active` 返回的工作表类型不确定，直接调用 `iter_rows()` 在静态检查中报错。",
      "conclusionMarkdown": "审查了测试层结构和类型安全问题。 **测试规模**： - 247 个回归测试文件（`regression_*.py`） - 15 个冒烟测试文件（`smoke_*.py`） - 30+ 个单元/集成/端到端测试文件（`test_*.py`、`run_*.py`） - 总计约 290+ 个测试文件 **积极发现**： 1. 回归测试覆盖极其全面：命名规范统一（`regression_<功能描述>.py`），每个文件对应一个明确的回归场景。 2. `conftest.py` 设计良好：自动将 `regression_*.py` 中的 `main()` 函数包装为 pytest 测试用例，无需修改原始文件。 3. 冒烟测试独立性强：每个测试使用独立临时目录和数据库，避免相互污染。 4. 存在专门的安全测试（XSS 检测、安全头验证、会话安全等）。 **问题点**： 1. 冒烟测试文件间存在大量重复的环境搭建代码（临时目录创建、环境变量设置、数据库初始化），可提取为共享的辅助函数。 2. `unit_excel/parser.py` 存在类型安全问题：`wb.active` 返回的工作表类型不确定，直接调用 `iter_rows()` 在静态检查中报错。",
      "evidence": [],
      "reviewedModules": [
        "tests/ (测试套件)",
        "core/services/process/unit_excel/parser.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-TEST-STRUCT",
        "F-PARSER-TYPE"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-ENTRY-DUP",
      "severity": "medium",
      "category": "maintainability",
      "title": "两个入口文件近乎完全重复",
      "descriptionMarkdown": "该问题已通过参数化入口主流程收口：共享启动逻辑集中到 `web/bootstrap/entrypoint.py` 的 `app_main()` / `configure_runtime_contract()`，`app.py` 与 `app_new_ui.py` 只保留界面模式差异和壳层调用。这样既保留了 `runtime_base_dir(anchor_file=__file__)` 的锚点语义，也消除了双点同步维护风险。",
      "recommendationMarkdown": "继续保持两个壳层仅承载界面模式差异；后续若新增启动流程改动，应优先落在共享入口模块。",
      "evidence": [
        {
          "path": "web/bootstrap/entrypoint.py",
          "lineStart": 133,
          "lineEnd": 286
        },
        {
          "path": "app.py",
          "lineStart": 29,
          "lineEnd": 62
        },
        {
          "path": "app_new_ui.py",
          "lineStart": 29,
          "lineEnd": 62
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "fixed",
      "aliases": [
        "app-entrypoint-duplication",
        "U-3"
      ]
    },
    {
      "id": "F-SUMMARY-ARGS",
      "severity": "medium",
      "category": "maintainability",
      "title": "排产摘要构建函数参数过多",
      "descriptionMarkdown": "该问题已通过 `SummaryBuildContext` 与具名状态对象收口。`build_result_summary()` 现以 `ctx=` 作为主路径，同时保留关键字兼容层；`_build_result_summary_obj()` 与 `_algo_dict()` 也已改为消费上下文/状态对象，9 级摘要截断梯度则收敛到 `DEFAULT_TRUNCATION_TIERS`。",
      "recommendationMarkdown": "继续将新代码统一走 `ctx=` 主路径，并保留回归用例覆盖关键字兼容入口，防止兼容层漂移。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 175,
          "lineEnd": 229
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 360,
          "lineEnd": 459
        },
        {
          "path": "core/services/scheduler/schedule_summary_assembly.py",
          "lineStart": 279,
          "lineEnd": 363
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 148,
          "lineEnd": 183
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "fixed",
      "aliases": [
        "scheduler-summary-wide-context",
        "U-2"
      ]
    },
    {
      "id": "F-SCHED-DEPS",
      "severity": "low",
      "category": "maintainability",
      "title": "排产服务依赖多个仓储",
      "descriptionMarkdown": "ScheduleService.__init__() 初始化 10 个仓储实例（batch_repo, op_repo, part_op_repo, group_repo, machine_repo, operator_repo, operator_machine_repo, supplier_repo, schedule_repo, history_repo）。虽然 _run_schedule_impl() 已拆分为 collect → orchestrate → persist 三步，但服务类本身仍然是拀点，所有仓储都通过它传入子模块。",
      "recommendationMarkdown": "考虑将仓储依赖分组，或采用服务定位器模式减少直接依赖。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 132,
          "lineEnd": 160
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-ROUTE-DUP",
      "severity": "medium",
      "category": "maintainability",
      "title": "路由层工具函数大量重复",
      "descriptionMarkdown": "该问题已通过 `web/routes/excel_utils.py` 的组合式公共能力收口：确认载荷解析、基线漂移守卫、错误行收集/文案拼装与导入统计提取统一下沉，而各路由继续保留自己的页面回显函数与行级校验闭包，避免了过度抽象。",
      "recommendationMarkdown": "后续新增 Excel confirm 路由时继续复用这些小粒度公共能力，不再回到“大骨架函数”或分散复制的写法。",
      "evidence": [
        {
          "path": "web/routes/excel_utils.py",
          "lineStart": 115,
          "lineEnd": 162
        },
        {
          "path": "web/routes/equipment_excel_links.py",
          "lineStart": 165,
          "lineEnd": 228
        },
        {
          "path": "web/routes/process_excel_suppliers.py",
          "lineStart": 197,
          "lineEnd": 292
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 266,
          "lineEnd": 362
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "fixed",
      "aliases": [
        "excel-import-confirm-flow-duplication",
        "U-1"
      ]
    },
    {
      "id": "F-TEST-STRUCT",
      "severity": "low",
      "category": "test",
      "title": "测试结构职责边界模糊",
      "descriptionMarkdown": "测试套件规模庞大（247 个回归测试 + 15 个冒烟测试 + 30+ 个单元测试/端到端测试），但各类测试的职责边界不够清晰：回归测试和冒烟测试都是独立脚本（带 main() 函数），运行方式不统一：回归测试经 conftest.py 自动收集，冒烟测试需手动运行。各冒烟测试内部包含大量重复的环境搞建代码（临时目录、DB 初始化、环境变量设置）。",
      "recommendationMarkdown": "考虑将冒烟测试的通用环境搞建逻辑提取为共享 fixture，统一运行入口。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-PARSER-TYPE",
      "severity": "low",
      "category": "other",
      "title": "工作表解析器缺少类型守卫",
      "descriptionMarkdown": "`core/services/process/unit_excel/parser.py` 现已在 `UnitExcelParser.parse()` 中对 `wb.active` / `wb[sheet_name]` 返回结果补上 `Worksheet` 类型守卫：当返回对象不是 `Worksheet` 时会直接抛出 `ValueError`。本项保留为已完成整改留痕，后续只需保持该守卫与静态检查口径一致。",
      "recommendationMarkdown": "保持现有 `Worksheet` 类型守卫，不再回退到无类型检查的 `iter_rows()` 调用路径。",
      "evidence": [
        {
          "path": "core/services/process/unit_excel/parser.py",
          "lineStart": 45,
          "lineEnd": 52
        },
        {
          "path": "core/services/process/unit_excel/parser.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "fixed",
      "aliases": [
        "U-6"
      ]
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:cbf950be5bb843fec4d75afff0328e1a8f2e7045980e6f7f24bf36f6b8d7d144",
    "generatedAt": "2026-04-05T07:24:21.000Z",
    "locale": "zh-CN"
  }
}
```

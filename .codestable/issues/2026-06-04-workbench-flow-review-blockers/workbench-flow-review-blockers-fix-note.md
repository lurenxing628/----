---
doc_type: issue-fix
issue: 2026-06-04-workbench-flow-review-blockers
status: fixed
path: fast-track
fix_date: 2026-06-04
tags: [aps, workbench, migration, plan-identity, review-loop]
---

# 工作台主流程复审阻塞修复记录

## 1. 问题描述

工作台主流程实现进入 SubAgent 对抗复审后，连续暴露出几类会让系统“看起来正常、实际在撒谎”的阻塞：

- 历史正式方案在显示层可能被当成当前正式方案展示，用户看不出它已经不是现行版本。
- `SchemaVersion=19` 但真实表结构仍停在旧契约时，启动路径可能不报错。
- 只有 `SchemaVersion=19`、没有业务表的空壳坏库，会先被 `schema.sql` 补齐，再通过当前契约检查。
- 低版本坏库缺少整表时，迁移预检和真实迁移仍可能用当前 `schema.sql` 把缺表补出来，再把坏库推进到当前版本。
- v16 会把早期坏的现场事件自动补成“其他原因 / 中等严重程度 / 清空失效资源引用”，让不完整历史事实看起来合法。
- `SchemaVersion>=15` 但 `OperationExecutionEvents` 缺失时，后续迁移会重新建表并把坏库推进到当前版本。
- 事件表只靠仓库层校验计划身份，直接 SQL 或迁移可写入 `schedule_version`、`schedule_id`、`op_id`、`batch_id` 互相不一致的事件。
- 事件表允许 `finish + processing` 这类事件类型和上报状态互相矛盾的组合，状态聚合会信任坏状态。
- 事件表和读模型允许 `event_time='not-a-date'` 这类坏时间进入现场事实，状态聚合会把它当成正常“加工中”状态展示。
- 当前版本结构契约报错只剩泛化文案，无法告诉用户到底是缺表、坏索引、坏外键还是坏探针被放行。
- 甘特图和周计划页面绕开 `plan_resolution.user_label`，把历史正式方案显示成“正式采用方案”。
- 报表坏数据的用户可见错误里曾暴露内部字段名。
- 审计 / 体检文档和 feature 实现混在同一个暂存提交里，提交边界不清楚。
- 本地生成的全景图 HTML 被用户可见文档测试扫到，里面带有内部字段名。
- `ensure_schema()` 行号变化后，技术债务治理台账里的静默回退登记需要同步。
- 文档把 dirty quality gate 预跑写得像最终绑定通过，和 manifest 的 `passed_but_unbound` 状态不一致。
- `.gitignore` 里的生成物边界需要讲清楚：`.drift-cache/` 是语义雷达机器缓存，`.playwright-cli/` 是浏览器工具本地快照，不能和 `.codestable/audits`、`.codestable/checkup` 这些审计证据混为一谈。
- 网络恢复后重跑长门禁时，真实浏览器几何测试在串行分片里卡住：页面检查结果已经完整写到 stdout，但 Node 探针进程没有退出，导致 full-test-debt 把它记成候选失败。
- 周计划所选版本摘要仍可能把未知 `strategy` 原样显示出来；二级降级提示也可能在缺少中文标签时显示内部 `code`。
- 排产分析方案对比表把候选方案 `metrics` 原值直接放进展示行，`bad_metric_value` 这类坏指标可能进入普通页面；摘要卡又会把同一类坏值说成“暂无数据”。
- 优化过程和诊断区的数字解析没有拒绝布尔值，`True/False` 会被当成 `1/0`，让坏数据看起来像正常数字。
- 现场事件 schema、repo 写入和反馈服务已挡住非当前正式方案，但状态聚合入口只校验事件类型、状态和时间；如果坏事件对象绕过数据库进入内存，仍可能被聚合成正常现场状态。

## 2. 根因

- 计划身份的读写链路没有在所有入口上都坚持“当前可执行正式方案”这一层语义，显示和写入曾经各自兜底。
- 数据库启动链路先用 `has_no_user_tables()` 判断是否补表；这个判断会排除 `SchemaVersion`，所以“只有版本表”的坏库会被当成无业务表新库。
- 当前版本结构契约检查原来放在补表之后；一旦先补表，坏库就被改成好库，检查自然看不见问题。
- 迁移执行器的 `_prepare_probe_schema()` 和 `_apply_migrations()` 在正式迁移前补缺失整表，把“低版本正常迁移”和“坏库缺表”混成同一种路径。
- v16 的历史事件复制表达式为了让数据塞进新表约束，主动补默认业务值或清空外键，掩盖了旧事件本身不完整。
- `OperationExecutionEvents` 在 v15 已经引入，版本号大于等于 15 却缺这张表，说明旧迁移已完成但结构丢了；v16/v18/v19 原来把这种坏库当成“缺表可创建”处理。
- 现场事件身份一致性只在 `OperationExecutionEventRepo.insert_event()` 里查 `Schedule JOIN BatchOperations`，数据库表结构没有组合外键，迁移和直接 SQL 会绕开仓库。
- `event_type` 和 `reported_status` 只有各自枚举检查，没有成对约束，读模型又优先相信 `reported_status`。
- `event_time` 只有非空要求，服务层、仓库层、模型层和状态聚合层各自解析时间；状态聚合遇到坏时间时返回 `None`，等于把坏数据悄悄降级成“无法计算时长但状态正常”。
- SQLite 的 `datetime()` 会接受部分日历上不可能的日期，所以只靠表 CHECK 不够；当前版本库里已经存在的坏事件也必须在启动契约里扫描出来。
- `detect_schema_is_current()` 和事件表合同函数都只返回 bool，失败原因在抛错前已经丢失。
- 甘特图 / 周计划模板用了 `selected_label`；这个字段只表示选择的角色，不表示这版方案是否已被更新版本替代。
- 诊断页的重点影响样本只有内部 `op_id`，显示层把它拼成“工序 1”，等于把内部编号伪装成用户可理解的工序名。
- 资源派工、工作台跳转禁用原因和报表计划状态三个出口直接拼 `schedule_result_status` 或 `result_summary_parse_reason`，会把 `failed`、`json_decode_error` 这类内部码显示给用户。
- 周计划版本下拉和所选版本摘要对未知 `result_status` 使用 raw fallback，会把未登记的内部状态值显示给用户。
- 报表数字转换异常把内部 key 拼进了给用户看的中文提示。
- 浏览器几何探针每页检查完只调用 CDP WebSocket 的 `close()`，没有等待关闭完成；结果写出后又继续依赖 Node 自然清空事件循环，一旦 WebSocket 或 Chrome 收尾句柄没有自然释放，探针就会在结果已产出的情况下继续挂住。
- 周计划 route 只给版本下拉调用了 `decorate_history_version_options()`，所选版本详情来自 `ScheduleHistory.to_dict()`，没有补 `strategy_label`；模板又写了 raw fallback。
- 候选方案对比行把 `_candidate_metric()` 的返回值直接塞进表格字段，底层函数只“取值”，没有把候选指标先解析成安全展示值。
- `scheduler_analysis_trends._metric_float_state()`、`_int_state()` 和诊断 `safe_int/safe_float()` 都走 Python 数字转换，Python 会把布尔值当成整数的子类。
- `OperationExecutionScope` 是多个只读上下文复用的身份描述对象，不能在它的构造函数里直接拒绝候选/模拟方案；真正应该 fail-fast 的位置是事件模型、事件 repo 写入和状态聚合入口。
- 审计计划和调用图快照属于独立工作流，不能混进工作台 feature 的 scoped commit。

## 3. 修复方案

- 工作台和现场记录链路统一使用当前正式方案身份：历史、缺失、坏摘要、非正式方案只能显示中文原因，不能冒充当前正式方案。
- `OperationExecutionEvents` 契约升级到 v19：去掉方案身份默认值，状态修订唯一约束纳入版本、排程行、批次和方案身份。
- `ensure_schema()`、迁移预检和迁移执行在补表前先检查当前版本结构契约；当前版本坏库直接 fail-fast。
- 迁移执行器取消用当前 `schema.sql` 预补缺失整表；缺表由对应版本迁移显式创建，版本迁移返回 skipped 时按残缺结构报错。
- v16/v18/v19 发现 v15 后应存在的事件表缺失时返回 skipped，由迁移入口报残缺结构；v14 及更早旧库仍允许 v15 正常创建事件表。
- v16 迁移先检查缺原因、缺严重程度、失效资源引用、非法重排建议和事件/状态矛盾的历史事件，发现后直接阻断并列出事件 id，不再自动补成合法值。
- `schema.sql` 和 v15 事件表定义下沉组合外键：事件的 `schedule_id/schedule_version/op_id` 必须匹配 `Schedule`，`op_id/batch_id` 必须匹配 `BatchOperations`。
- 事件表增加 `event_type` 与 `reported_status` 成对 CHECK，`finish` 只能是 `completed`，`pause` 只能是 `paused`。
- `core/models/operation_execution_event.py` 增加唯一的现场事件时间、事件类型和上报状态校验出口；服务、仓库、读模型和 v16 迁移都复用它，坏时间或坏状态组合直接报错，新库 schema 也用 `datetime(event_time) IS NOT NULL` 挡住明显坏值。
- `core/infrastructure/operation_execution_event_data_contract.py` 扫描当前库里已经存在的现场事件，发现日历上不可能的时间、事件/状态矛盾或外键孤儿数据时，让当前 schema 契约 fail-fast。
- 当前结构检测保留原 bool 接口，同时增加 issues 明细；当前版本坏库报错会列出 `missing_table`、`missing_column`、`bad_index`、`bad_fk`、`bad_probe` 等具体问题。
- 新增 `core/services/scheduler/schedule_plan_option_display.py`，把计划角色下拉的用户可见文案集中到同一个公共出口：历史正式方案统一显示为“历史正式方案（已被新版本替代）”，候选名相同时不再拼出重复标签。
- 甘特图、周计划、报表下拉、资源派工和新 UI 甘特模板统一读取公共展示字段，显示层不再各自拼“正式采用方案”。
- 分析诊断页的 graph score 样本不再展示内部 `op_id`；没有公开工序名称时，只展示“重点影响样本”和影响信息。
- 新增 `web/viewmodels/scheduler_plan_guardrail_messages.py`，把排产结果状态和排产摘要失败原因统一翻成公开中文；登记过的原因显示中文解释，没登记的原因只显示“当前排产摘要结构无法安全解析”，不再原样吐内部码或调试细节。
- 周计划版本下拉和所选版本摘要改为使用已有中文状态标签；没有可识别状态时显示“结果状态未知”，不再把 raw `result_status` 放进页面。
- 报表公开错误保留中文业务文案，内部字段只留在异常对象的 `field/details` 里。
- 浏览器几何探针把 CDP 客户端关闭改成可等待的收尾流程：每页检查结束后等待 WebSocket 关闭并移出活跃列表；探针输出 stdout/stderr 时先等待写入完成，最后按明确退出码结束一次性 Node 进程，避免结果已写出但事件循环不退出。
- 周计划所选版本详情在 route 层补 `strategy_display_label()`，模板只显示公开标签或“历史记录异常”，不再读 raw `strategy`；二级提示缺中文标签时只显示“提示”。
- 候选方案指标增加“安全数值 + 解析失败标记”结构，方案对比表和摘要卡统一展示“记录异常 / 无法安全对比”，不再把坏指标原文或“暂无数据”当成正常展示。
- 优化过程数值解析拒绝布尔值，走页面已有“记录异常”分支；诊断区遇到布尔值抛出诊断异常块，不再显示 `1 个 / 0 个`。
- `validate_current_official_execution_scope()` 保留为事件闸门；`OperationExecutionScope` 保持中性身份对象，`OperationExecutionEvent.from_row()`、`OperationExecutionEventRepo.insert_event()` 和 `build_operation_execution_state()` 主动调用事件闸门，防止非当前正式方案事件被写入或聚合。
- audit/checkup 文件保留在工作区，但从本次 feature 暂存提交中移出，后续单独提交。
- 全景图 HTML/CSS/JS 明确作为本地生成物忽略；用户可见文档扫描同步跳过这些生成物。
- `.drift-cache/` 只作为语义雷达机器缓存忽略，`.playwright-cli/` 只作为浏览器工具本地快照忽略；审计和体检证据目录保持可见，继续单独提交。
- 使用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 受控刷新技术债务治理台账，再用 `check` 校验。
- CodeStable 文档明确记录 dirty quality gate 的 run_id、16 个 receipt 和 `passed_but_unbound`，不把它写成最终 clean proof。

## 4. 改动文件清单

- `core/infrastructure/database.py`：补表前增加当前版本契约检查。
- `core/infrastructure/migration_runner.py`：迁移预检和迁移执行取消当前 schema 缺表预补，并阻断 v15 后缺事件表的坏库。
- `core/infrastructure/migration_state.py`、`core/infrastructure/migration_operation_execution_contract.py`、`core/infrastructure/operation_execution_event_data_contract.py`：集中维护当前版本契约错误、结构问题明细和当前库坏事件扫描。
- `core/infrastructure/migrations/v15.py`、`core/infrastructure/migrations/v16.py`、`core/infrastructure/migrations/v18.py`、`core/infrastructure/migrations/v19.py`、`schema.sql`：落地现场记录身份契约、事件状态组合契约和坏历史事件 fail-fast。
- `core/models/operation_execution_event.py`、`data/repositories/operation_execution_event_repo.py`、`data/repositories/operation_execution_state_builder.py`、`core/services/scheduler/operation_execution_feedback_service.py`、`core/services/scheduler/operation_execution_feedback_support.py`：把现场事件时间和事件/状态组合收口到模型层校验，写入前标准化，读状态时遇到坏历史事件直接暴露错误。
- `templates/scheduler/gantt.html`、`templates/scheduler/week_plan.html`、`web_new_test/templates/scheduler/gantt.html`：历史正式方案使用用户可见身份标签展示。
- `web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py`：重点影响样本不再把内部 `op_id` 展示成“工序 N”。
- `web/viewmodels/scheduler_plan_guardrail_messages.py`、`web/viewmodels/scheduler_resource_dispatch.py`、`web/viewmodels/scheduler_workbench_links.py`、`web/routes/reports_plan_template_fields.py`：资源派工、工作台链接和报表计划状态统一使用公开中文护栏文案，不把 `failed`、`json_decode_error` 等内部码显示给用户。
- `templates/scheduler/week_plan.html`、`tests/regression_web_silent_fallback_contract.py`：周计划版本下拉和所选版本摘要不再 raw fallback 到未知 `result_status`。
- `web/viewmodels/*`、`web/routes/*`、`core/services/scheduler/*`：串起工作台、甘特、资源派工、报表和现场记录的身份护栏。
- `tests/regression_*`、`tools/test_registry_*`：补回归测试和质量门禁登记；把 schema 合同检测拆到 `tests/regression_migration_schema_contract.py`，避免单个测试文件继续超过 500 行。
- `tests/regression_frontend_offline_static_assets.py`、`.gitignore`：让本地生成全景图不再污染正式用户文档扫描，并只忽略语义雷达机器缓存和浏览器工具本地快照。
- `tests/ui_geometry_probe.mjs`、`tests/ui_geometry_cdp_client.mjs`：真实浏览器几何探针等待 CDP 连接关闭、等待输出写完，并在清理 Chrome/profile 后明确退出。
- `web/routes/domains/scheduler/scheduler_week_plan.py`、`templates/scheduler/week_plan.html`：所选历史版本排产方式只使用公开标签，降级提示不再 raw fallback 到内部 code。
- `web/viewmodels/scheduler_analysis_candidate_helpers.py`、`web/viewmodels/scheduler_analysis_candidates.py`、`templates/scheduler/analysis_parts/_candidate_comparison.html`：候选指标统一走安全数值解析和解析失败标记。
- `web/viewmodels/scheduler_analysis_trends.py`、`web/viewmodels/scheduler_analysis_diagnostic_helpers.py`：优化过程和诊断数值拒绝布尔值。
- `core/models/operation_execution_scope.py`、`core/models/operation_execution_event.py`、`data/repositories/operation_execution_event_repo.py`、`data/repositories/operation_execution_state_builder.py`：现场事件身份闸门下沉到模型、repo 写入和状态聚合入口，同时保持通用 scope 不破坏只读候选/模拟方案查看。
- `开发文档/技术债务治理台账.md`：先通过 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 同步质量门禁自动字段，再把受控 JSON 块机械压回现有 500 行门禁形态；台账存储结构根治留给独立质量门禁工具重构。
- `.codestable/features/2026-06-02-workbench-flow-regression-suite/`、`.codestable/roadmap/aps-frontend-workbench/`：记录 feature 范围和 roadmap 状态。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_database_high_version_failfast.py tests/regression_migration_schema_contract.py tests/regression_operation_execution_migration_v16_contract.py tests/regression_scheduler_historical_plan_label_contract.py tests/regression_quality_gate_registry_split_scope_contract.py`：36 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_migrations.py tests/regression_migration_schema_contract.py tests/regression_operation_execution_migration_v16_contract.py tests/regression_operation_execution_migration_v18_contract.py tests/regression_operation_execution_migration_v19_contract.py`：28 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_reports_workbench_backlink_contract.py tests/regression_reports_workbench_navigation_contract.py tests/regression_aps_workbench_flow_contract.py tests/regression_aps_workbench_report_row_links_contract.py`：37 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_state_flow.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_feedback_guard_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_exception_plan_guard.py tests/regression_operation_execution_scope_read_contract.py tests/regression_resource_dispatch_actual_records.py tests/regression_resource_dispatch_actual_import.py tests/regression_resource_dispatch_actual_import_plan_guard.py tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_resource_dispatch_workbench_lane_contract.py`：120 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_dashboard_workbench_contract.py tests/regression_dashboard_workspace_layout_contract.py tests/regression_dashboard_overdue_count_tolerance.py tests/regression_execution_review_identity_guardrail.py tests/regression_gantt_task_detail_panel_contract.py tests/regression_gantt_task_detail_js_contract.py tests/regression_scheduler_workbench_links_contract.py tests/regression_scheduler_workbench_link_guardrails.py tests/regression_web_silent_fallback_contract.py tests/regression_quality_gate_registry_split_scope_contract.py tests/test_ui_geometry_html_contract.py`：71 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：治理台账刷新并校验通过；受控 JSON 块随后机械压缩，复跑 `check` 仍通过，文件 54 行。
- in-app Browser 烟测：报表中心、甘特和周计划均能打开；v12 被 v13 替代后，下拉和页面提示展示历史正式方案信号；报表页不再出现“复盘正式方案”；下拉不再出现“正式采用方案 · 正式采用方案”；截图保存到 `output/playwright/workbench-flow-regression-suite-reports-history-iab.png`。
- `scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache --no-resume`：run_id `c2aa7501ca2dc5ccfd2e64006094f584e2c1089b:2026-06-04T20:01:20`，16 条命令全部完成，failed 0；manifest 状态为 `passed_but_unbound`，只能作为 dirty 工作区预跑证据，最终 clean proof 需要等 scoped commit 边界干净后执行。
- 新增的迁移、schema 合同和历史方案显示测试会继续进入下一轮 SubAgent 复审核对。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_event_time_contract.py tests/regression_operation_execution_migration_v16_contract.py tests/regression_migration_schema_contract.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_flow.py`：51 passed，覆盖坏时间模型拒绝、仓库标准化、直接 SQL 拦截、状态聚合 fail-fast 和 v16 旧库阻断。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_records.py tests/regression_resource_dispatch_actual_import.py tests/regression_migrations.py`：42 passed，确认服务层标准化没有破坏现场反馈、异常反馈、现场导入和迁移主流程。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_event_time_contract.py tests/regression_migration_schema_contract.py tests/regression_scheduler_analysis_diagnostic_graph_score_contract.py tests/regression_quality_gate_registry_split_scope_contract.py tests/regression_aps_three_gap_docs_quality_gate.py`：42 passed，覆盖当前库坏事件扫描、诊断页内部 `op_id` 不外露、门禁注册和开发文档清单。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`、`tools/scan_py38plus_syntax.py --fail-on-hit ...`、`tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77`：均通过；`tests/test_architecture_fitness.py::test_file_size_limit` 通过，新增/拆分文件均低于 500 行，既有历史长聚合文件 `tools/quality_gate_shared.py` 本轮只同步真实门禁命令和工具路径。
- `./.venv/bin/python -m pytest -q tests/regression_scheduler_workbench_link_guardrails.py tests/regression_web_silent_fallback_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_workbench_links_contract.py`：28 passed，确认公开护栏文案不再泄露 `json_decode_error`，资源派工、工作台链接、报表计划状态三个出口都走中文解释。
- `./.venv/bin/python -m pytest -q tests/regression_web_silent_fallback_contract.py tests/regression_scheduler_historical_plan_label_contract.py tests/regression_scheduler_week_plan_summary_observability.py::test_week_plan_page_renders_simulated_completion_status_label`：17 passed，确认周计划结果状态 fallback 不回吐 raw code，历史方案标签和模拟排产状态文案仍正常。
- `./.venv/bin/python -m pytest -q tests/regression_scheduler_reschedule_execution_facts.py tests/regression_scheduler_reschedule_execution_minimum_guardrails.py tests/regression_gantt_adjustment_publish_execution_revision.py tests/regression_gantt_task_detail_panel_contract.py tests/regression_gantt_task_detail_js_contract.py`：35 passed，补上 SubAgent 复审时因 `networkx==3.1` 依赖环境未对齐导致的证据不足。
- `./.venv/bin/python -m pytest -q tests/regression_scheduler_workbench_link_guardrails.py tests/regression_web_silent_fallback_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_workbench_links_contract.py tests/regression_quality_gate_registry_split_scope_contract.py tests/regression_aps_three_gap_docs_quality_gate.py tests/test_run_quality_gate.py::test_repository_pyright_tools_config_matches_quality_gate_tool_paths tests/test_architecture_fitness.py::test_file_size_limit`：55 passed，确认公开文案、门禁登记、文档清单、pyright 工具路径和 500 行门禁一起通过。
- `./.venv/bin/python -m pytest tests/test_ui_browser_geometry_env.py tests/regression_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser -q --tb=short -ra -p no:cacheprovider`：10 passed，确认浏览器探针环境契约和真实几何探针不再在结果写出后卡住。
- `./.venv/bin/python -m pytest tests/regression_shared_runtime_state.py::regression_shared_runtime_state tests/regression_startup_host_portfile.py::regression_startup_host_portfile tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui tests/regression_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser -q --tb=short -ra -p no:cacheprovider`：4 passed，确认 startup 串行邻居不会再污染真实浏览器几何测试。
- `./.venv/bin/python tools/check_full_test_debt.py --sharded --shard-count 3 --allow-dirty-worktree-proof`：4032 collected，unexpected_failure_count 0，collection_error_count 0，full-test-debt proof passed。
- `./.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache --no-resume`：run_id `c2aa7501ca2dc5ccfd2e64006094f584e2c1089b:2026-06-04T22:21:34`，16 个门禁步骤全部跑完，failed 0；由于工作区仍非干净，manifest 仍是 `passed_but_unbound`，不能当 clean proof。
- `./.venv/bin/python -m py_compile core/models/operation_execution_scope.py core/models/operation_execution_event.py data/repositories/operation_execution_event_repo.py data/repositories/operation_execution_state_builder.py web/viewmodels/scheduler_analysis_candidate_helpers.py web/viewmodels/scheduler_analysis_candidates.py web/viewmodels/scheduler_analysis_trends.py web/viewmodels/scheduler_analysis_diagnostic_helpers.py web/routes/domains/scheduler/scheduler_week_plan.py tests/regression_web_silent_fallback_contract.py tests/regression_operation_execution_event_time_contract.py`：语法和导入编译通过。
- `./.venv/bin/python -m pytest tests/regression_web_silent_fallback_contract.py tests/regression_operation_execution_event_time_contract.py tests/regression_scheduler_analysis_diagnostic_graph_score_contract.py -q --tb=short -ra -p no:cacheprovider`：18 passed，覆盖候选坏指标、布尔值数值、周计划策略标签和现场事件身份闸门。
- `./.venv/bin/python -m pytest tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_flow.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_feedback_guard_routes.py tests/regression_operation_execution_scope_read_contract.py tests/regression_operation_execution_exception_plan_guard.py tests/regression_operation_execution_event_time_contract.py -q --tb=short -ra -p no:cacheprovider`：66 passed，确认只读候选/模拟方案仍返回业务护栏，不再因 scope 过度收紧变成 500。
- `./.venv/bin/python -m pytest tests/regression_web_silent_fallback_contract.py tests/test_schedule_summary_observability.py tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_analysis_diagnostic_graph_score_contract.py tests/regression_scheduler_workbench_link_guardrails.py tests/regression_scheduler_historical_plan_label_contract.py tests/regression_scheduler_data_route_error_contract.py -q --tb=short -ra -p no:cacheprovider`：42 passed，确认排产分析、周计划和公开护栏没有回退。
- `git diff --check && git diff --cached --check`：无输出；关键新改文件复核均低于 500 行，`data/repositories/operation_execution_event_repo.py` 当前 479 行。
- Claude Code review_round_5 delegate 启动并按要求提示其 SubAgent 使用 `model:"opus"`，日志显示曾启动 4 个 Claude 子代理且 5 个 agent finished，但本轮最终 StopFailure，transcript reader 只返回 socket/API 错误；按 `claude-code-bridge` 规则不能算有效复审证据，已停止该 delegate，后续必须重新开 fresh delegate。

## 6. 遗留事项

- `.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/` 和 `.codestable/checkup/latest/callgraph/` 保留为独立工作流材料，单独提交，不能和本 feature 混在同一个提交里。
- 完整 `scripts/run_quality_gate.py --require-clean-worktree` 需要在 feature 提交和 audit/checkup 提交都完成、工作区干净后运行，作为分支整体收尾证据。

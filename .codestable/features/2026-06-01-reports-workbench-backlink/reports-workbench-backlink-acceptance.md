---
doc_type: feature-acceptance
feature: 2026-06-01-reports-workbench-backlink
requirement: scheduler-daily-workbench
roadmap: aps-frontend-workbench
roadmap_item: reports-workbench-backlink
status: accepted
accepted_at: 2026-06-02
summary: 报表中心和四类报表明细已能带同一计划上下文回到甘特、资源派工和正式方案复盘，并把已支持的筛选真正下推到页面和导出数据。
tags: [aps, reports, workbench, backlinks, scheduler]
---

# reports-workbench-backlink 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-02
> 关联方案 doc：`.codestable/features/2026-06-01-reports-workbench-backlink/reports-workbench-backlink-design.md`

## 1. 接口契约核对

- [x] `ReportsWorkbenchCard`：报表中心四张入口卡和页面级回跳由 `web/viewmodels/scheduler_reports_workbench.py` 统一生成，模板只渲染中文标题、能回答的问题、不能证明的事情和 `WorkbenchLink`。
- [x] `ReportsWorkbenchRowActions`：超期、资源负荷、计划和现场实际、停机影响的行级动作都从批次、设备、人员这些业务对象生成，可继续回甘特、资源派工或正式方案复盘，不把 `op_id`、`schedule_id` 作为公开定位字段。
- [x] `NavigationLinks`：排产主导航、报表顶部导航、全局计划工作台导航和报表筛选隐藏字段由 `web/viewmodels/scheduler_navigation_links.py` 统一生成，模板只循环渲染，不再手拼查询参数。
- [x] `ReportEngine` 报表接口：超期、资源负荷、计划和现场实际、停机影响都支持 `batch_id`、`resource_type`、`resource_id` 过滤；Excel 导出复用同一过滤链，不只改 URL；底层超期查询 service 和 repository 也拒绝未知维度、只有资源编号没类型、只有资源类型没编号这些半截资源筛选；resource/scope/machine/operator 这些资源别名互相冲突时也会直接报错。
- [x] 流程图核对：路由解析查询条件，`ReportEngine` 取数，`scheduler_reports_workbench` 装配入口和回跳，模板渲染中文说明，用户再回甘特、资源派工或复盘，代码落点完整。

## 2. 行为与决策核对

- [x] 报表中心不再只是列表，四张卡片都说明“能回答什么”和“不能证明什么”，并提供页面级甘特、资源派工和正式方案复盘入口，保留版本、正式方案、计划身份、返回地址、日期、查询日、周期、批次和资源上下文。
- [x] 超期、资源负荷、计划和现场实际、停机影响都不是死胡同，页面级和行级入口能继续回到甘特、资源派工或正式方案复盘。
- [x] 甘特入口不会跨视角串资源编号：机器上下文切人员甘特图不带机器号，人员上下文切设备甘特图不带人员号。
- [x] 计划和现场实际只复盘正式采用方案；非正式方案或模拟预览上下文里，报表导航展示禁用态，不生成可点击复盘入口。
- [x] 资源派工页的正式方案复盘链接只在路由入口读取 `back_to`，`_workbench_context()` 和 `_execution_review_link()` 只接收显式参数；底层链接判断不会偷偷依赖 Flask 请求对象，单独调用也能触发同一套服务端护栏。
- [x] 资源派工页发布全局工作台导航上下文时使用完整 `filters` 里的服务端计划身份字段，避免公开剥离版 `plan_identity` 丢掉 `is_comparison`、`is_superseded_by_newer_version` 等护栏字段后把复盘顶导误启用。
- [x] 报表当前只支持设备和人员资源筛选；遇到 `resource_type=team`、未知资源维度、只有资源编号没有资源类型、只有资源类型没有资源编号、资源主参数和别名互相冲突这些情况时直接给用户看得懂的错误，不静默扩大成全量数据；只有 `machine_id` 或只有 `operator_id` 的明确单一别名会推断成对应维度。
- [x] 工作台链接遇到班组资源上下文时，所有会吃 `resource_type/resource_id` 主资源筛选的目标都会展示禁用原因，不生成会跳到 400 的可点击 URL；资源派工目标仍保留 `scope_type=team/scope_id/team_id`；甘特图不带班组筛选。
- [x] 排产分析、甘特和周计划发布全局导航上下文时，会保留服务端解析出的完整方案护栏字段；旧正式版本、对比方案、模拟预览不会在顶部导航里误生成“计划和现场实际”可点击入口。
- [x] 从报表行进入甘特、排产分析或周计划后，顶部导航继续保留批次和资源上下文，不会把用户刚定位的 `batch_id/resource_type/resource_id` 扩大成全量范围。
- [x] 从报表行进入甘特或周计划后，后台取数也按同一批次和资源范围执行：甘特 JSON 不再返回整版任务，筛选后关键链基于同一批计划行计算，周计划页面预览和 Excel 导出都不会混入别的批次或资源。
- [x] 甘特页二次操作不会丢范围：切周、重新查询和同视角刷新继续保留 `gantt_batch/gantt_resource`；切到另一个视角时只保留批次，不把设备号塞进人员视图或把人员号塞进设备视图；周计划查询表单也保留同一批次和资源范围。
- [x] 甘特任务条、任务详情和关键链边上的公开任务名称使用同一套规则；当没有工序号、工序名、图号或零件名但有 `piece_id` 时，关键链和甘特任务都显示同一个件号，不再一个地方显示件号、另一个地方显示“某批次 工序”。
- [x] 资源派工页的现场实际写入地址由后端按归一化后的 `filters` 生成；外部入口只有 `date_from/date_to`、没有 `query_date` 时，也会补齐写入接口要求的查询日和日期范围，不生成“能点但第一次保存就 400”的入口。
- [x] 模拟预览上下文不会在筛选表单里误绑：超期、资源负荷、停机影响、甘特、周计划和资源派工在同一方案身份下保留当前 `scenario_id`；如果用户把排产版本或排产方案改成别的值，本地脚本会清掉旧模拟方案编号，切回原版本和原方案时会恢复旧模拟编号，避免旧模拟方案和新版本或新方案误绑，也避免模拟预览静默变成正式方案。
- [x] 报表数字解析不吞错：空值按业务语义保留空或 0；资源负荷页面和 Excel 导出、停机汇总、执行复盘暂停时长、工序编号、延期诊断小时/天数遇到坏字符串、无限值或非数字会抛 `ValidationError`，不会悄悄按 0、原样写进 Excel 或裸系统错误处理；导出行数和导出阈值额外拒绝负数和小数。
- [x] 停机影响第一版只做设备级说明和设备级入口；任务级停机影响没有混进本轮。
- [x] 路由复杂度被压回展示接线：导出路由拆到 `web/routes/reports_export_routes.py`，公共请求和导出辅助拆到 support 文件，`web/routes/reports.py` 保持 500 行以内。
- [x] 挂载点反向核对完成：新增和修改点都落在 design 第 2.3 节列出的报表 ViewModel、报表路由、报表模板、宏拆分、测试和登记文件内。

## 3. 验收场景核对

- [x] 输入带版本、正式方案、日期范围的 `/reports/`，四张入口卡和页面级入口都能保留上下文继续进入报表、甘特、资源派工和正式方案复盘。
- [x] 输入带 `plan_id` 和 `back_to` 的报表页，报表顶部导航、页面级回跳、全局工作台“首页值班台”、导出链接和筛选隐藏字段都会保留返回上下文。
- [x] 超期清单按批次回甘特、资源派工、正式方案复盘或延期说明，导出也只包含目标批次。
- [x] 资源负荷设备行和人员行能按资源回跳到资源派工、甘特、相关超期和正式方案复盘；同资源不同批次的测试证明导出不会把别的批次混进来。
- [x] 计划和现场实际页面和导出都按 `resource_type/resource_id/batch_id` 过滤，且仍固定正式采用方案。
- [x] 停机影响无数据时使用“当前没有停机记录或尚未维护停机数据”，没有误写成系统确认没有停机。
- [x] 页面、普通 HTML 属性、公开 payload 和 Excel 表头不出现 `source_table`、`candidate_id`、`op_id`、`schedule_id` 这些内部字段名。
- [x] 浏览器几何烟测覆盖 `/reports/` 和关键报表明细页，已通过真实浏览器烟测。
- [x] 上一轮定向回归曾通过：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_web_silent_fallback_contract.py tests/regression_scheduler_workbench_links_contract.py tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_reports_workbench_navigation_contract.py tests/regression_reports_workbench_backlink_contract.py tests/regression_report_context_filters_contract.py tests/regression_report_export_size_mode_selection.py tests/regression_report_export_large_scope_rejects_need_async.py tests/regression_scheduler_candidate_analysis_links_contract.py tests/regression_scheduler_candidate_display_contract.py tests/regression_quality_gate_registry_split_scope_contract.py tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions tests/test_long_gate_manifest.py::test_required_groups_cover_required_registry tests/test_architecture_fitness.py`，结果 `106 passed`；第 20 轮新增修复后，这个数字不再作为最终证据，最终以提交前重跑记录为准。
- [x] 真实浏览器烟测：`test_ui_pages_do_not_create_body_level_overflow_in_real_browser` 和 `test_ui_browser_geometry_smoke_covers_scheduler_run_page` 共 2 个用例通过。
- [x] pyright 工具扫描自检：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py::test_repository_pyright_tools_config_matches_quality_gate_tool_paths tests/test_long_gate_manifest.py::test_pyright_tools_config_include_matches_quality_gate_tool_paths`，结果 `2 passed`。
- [x] 干净暂存树完整质量门禁：按当前暂存树生成临时提交，在临时 worktree 里运行 `PYTHONDONTWRITEBYTECODE=1 /Users/lurenxing/Documents/GitHub/----/.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume`，16 步全部通过；全量测试债务 collected_count=3900、unexpected_failure_count=0，required regressions verified targets=161，运行时回归 `126 passed`，quickref 路由对照 OK。临时 worktree 里的 `.venv` 是被 git 忽略的运行环境软链接，只用于让 pyright 按项目配置找到依赖，不进入提交。
- [x] 第 18 轮对抗发现的阻塞已关闭：资源派工顶导使用完整服务端计划身份、班组上下文不再生成报表可点击 URL、资源负荷坏数字导出不再原样吞掉、新增报表上下文和候选分析回归已进入质量门禁登记。
- [x] 第 19 轮本地盲审发现的模拟预览筛选表单丢 `scenario_id` 已关闭：`report_plan_filter.js` 负责切换方案身份时清理旧模拟编号，模板筛选表单保留同一模拟预览上下文；相关回归 `35 passed`。
- [x] 第 19 轮 Claude Code 对抗发现的两个阻塞已关闭：班组资源上下文不再只禁用报表目标，而是覆盖首页值班台、排产分析、周计划和报表类主资源筛选目标；排产分析、甘特和周计划发布导航上下文时复制完整方案护栏字段，历史正式方案不会误启用计划实际复盘。相关回归 `48 passed`。
- [x] 第 19 轮本地盲审发现的门禁证据阻塞已关闭：`.gitignore` 明确列出的 QualityGate manifest、receipts、logs、long_gate、nodeid、债务快照、pyright/ruff/quickref 等运行产物不作为本轮可提交最终证据；最终证据以提交前当前暂存树重跑的门禁命令、关键断言和终端结果为准。
- [x] 第 20 轮本地盲审发现的资源派工写入阻塞已关闭：实际情况写入模板改由后端按服务端 filters 生成，前端看到模板自带查询串时不再追加浏览器地址栏原始查询串。
- [x] 第 20 轮本地盲审发现的排产页导航范围丢失阻塞已关闭：甘特、排产分析和周计划发布导航上下文时继续保留批次和资源范围。
- [x] 第 20 轮测试登记阻塞已关闭：候选分析旧合同测试进入 required guard 和 scheduler 分组；报表回跳 helper 改为 `tests/reports_workbench_backlink_helpers.py` 并登记 test-only helper 影响范围；`silent_fallback_inventory_acceptance/` 运行产物已纳入 git hook 黑名单。
- [x] 第 21 轮本地盲审发现的后台取数范围阻塞已关闭：`GanttService` 接收并下传批次/资源过滤，甘特数据接口保留 `gantt_batch/gantt_resource` 到数据 URL，周计划页面和导出复用同一套筛选参数；定向回归新增 `test_gantt_data_scope_filters_are_applied_by_backend` 和 `test_week_plan_preview_and_export_scope_filters_are_applied_by_backend`，中等范围回归结果 `122 passed`。
- [x] 第 21 轮本地盲审发现的二次操作和关键链标签阻塞已关闭：甘特视图按钮、周切换和查询表单保留当前筛选范围，周计划查询表单保留 `batch_id/resource_type/resource_id`，`gantt_task_labels.py` 统一甘特任务和关键链公开标签；相关定向回归 `3 passed`、关键链标签回归 `1 passed`、甘特/导航中等回归 `42 passed`。
- [x] 第 22 轮本地盲审发现的页面内链接同步阻塞已关闭：用户在甘特页内修改批次或资源筛选后，`static/js/gantt_ui.js` 会同步页面上的甘特视图链接和加载表单隐藏字段；同视角保留 `gantt_resource`，跨视角只保留 `gantt_batch`。相关甘特前端回归 `5 passed`，`static/js/gantt_contract.js` 已压到 500 行。
- [x] 第 22 轮本地盲审发现的半截资源筛选阻塞已关闭：`web/request_resource_context.py` 只要收到任意资源相关参数就进入严格归一化，周计划页面和导出遇到只有 `scope_type`、没有 `scope_id` 的坏入口会直接报错，不会静默查全量；相关定向回归 `3 passed`。
- [x] 第 22 轮用户指出的旧正式版本展示误导已关闭：计划和现场实际页不再使用固定“正式采用方案”字典，而是走真实 `PlanIdentity`；被新版本替代的旧正式版本显示“历史正式方案（已被新版本替代）”和只读提示，不靠写入层单独兜底；相关定向回归 `4 passed`。
- [x] 第 22/23 轮本地盲审发现的旧模拟方案误绑阻塞已关闭：所有带 `scenario_id` 的筛选表单按版本和方案身份同步旧模拟编号，身份变了就临时清掉，身份切回初始值就恢复；甘特、周计划、资源派工和三个报表页共用同一脚本；相关定向回归 `3 passed`，registry 回归 `6 passed`。
- [x] 第 23 轮质量门禁暴露的收尾阻塞已关闭：资源派工最小测试 app 补齐真实生产路由端点，Gantt 任务标签保留 `seq=0`，新增标签合同测试同时进入 required 总清单和 scheduler 分组；Gantt data URL helper 解决 pyright `url_for(**query)` 类型问题；技术债务治理台账只同步既有条目的 `line_start/line_end`，没有新增或删除静默回退事实。

## 4. 术语一致性

- 报表入口卡、行级动作、工作台链接、正式采用方案、停机影响这些术语和 design 一致。
- 用户可见位置继续使用中文业务名；内部字段只允许留在 URL、隐藏参数、请求参数和服务端日志中。
- 反向锁词已覆盖页面正文、公开属性和导出列，本轮没有新增外露内部字段。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md` 已补入“报表工作台回跳”现状，说明报表入口卡和行级动作由 `scheduler_reports_workbench.py` 统一装配，过滤由 `ReportEngine` 和查询仓储承接。
- [x] 架构总入口已记录约束：计划和现场实际只复盘正式采用方案，停机影响第一版只做设备级说明，内部字段不进入正文、表头和公开 payload。

## 6. requirement 回写

- [x] `.codestable/requirements/scheduler-daily-workbench.md` 已补入报表中心和报表明细作为风险处理入口的用户故事。
- [x] 需求边界已补充：报表回跳不替用户处理风险，不写现场事实，不把停机影响扩大成任务级明细。
- [x] 变更日志已记录本轮报表回跳能力。

## 7. roadmap 回写

- [x] `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml` 中 `reports-workbench-backlink` 已标成 `done`。
- [x] `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md` 子 feature 表已标成 `done`，变更日志记录最终质量门禁通过。
- [x] YAML 校验通过。

## 8. attention.md 候选盘点

- [x] 本 feature 未暴露需要补入 `.codestable/attention.md` 的新环境、命令或工作流规则。

## 9. 遗留

- 后续增强：`downtime-task-impact-detail` 继续承接停机影响任务级明细，本轮只完成设备级说明和回跳。
- 提交边界：本轮不会提交 `.codestable/refactors/2026-06-01-test-gate-cleanup/` 和 `scripts/build_test_inventory.py`，它们属于另一个重构任务。
- 提交边界：`开发文档/技术债务治理台账.md` 是既有超长历史台账，本轮只纳入 `sync_debt_ledger.py check` 要求的 12 个既有条目行号同步，没有新增或删除台账条目；该文件后续如需结构性拆分，应单独开治理任务处理。
- 非阻塞观察：后续可以给导出日志补充 batch/resource 筛选维度，方便人工追查导出来源；本轮数据过滤和页面行为已闭环。

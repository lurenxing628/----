---
doc_type: decision
category: architecture
date: 2026-09-18
slug: legacy-route-layer-removal
status: active
area: web
tags: [web, legacy, workbench, routes, viewmodels, python38]
---

## 背景与授权

工作台（`/workbench` + `/api/workbench`）已是唯一业务入口，旧 HTML 页面自 2026-09 起只靠 `legacy_dispatch` 把 GET 换成跳转或 410，但整套旧路由、视图模型、请求级服务容器仍挂在 `create_app` 上，约 2.8 万行产品代码没有任何用户可达路径，POST/JSON/导出接口也仍在线。2026-09-18 用户裁决“备份一下然后按方案 A 执行”：先做备份，再删掉旧路由层产品代码。备份：标签 `backup/pre-plan-a-legacy-routes-2026-09-18`、分支 `backup/pre-plan-a-legacy-routes`（均已推到远端）、本地 bundle `~/aps-backups/aps-pre-plan-a-2026-09-18.bundle`。

## 决定

1. **删除旧 HTML 页面层**：`web/routes` 下 dashboard/equipment/excel_demo/material/personnel/process/reports/system/scheduler 九个旧蓝图及 `domains/`、`helpers/`，`web/viewmodels` 除 `page_manuals*` 外全部视图模型，`web/bootstrap/request_services.py`（`g.services` 容器）、`template_globals.py`、`web/navigation_context.py`、`web/request_resource_context.py`，`templates/workbench/print.html`、`legacy_result.html` 与空模板目录。工厂不再挂 `g.services`，请求上下文只提供 `g.db` / `g.op_logger` / `g.app_logger`。
2. **旧 URL 只保留策略页 GET 占位规则**：`web/routes/workbench/legacy_blueprints.py` 用原蓝图名重新声明 9 个 Blueprint，按 `LEGACY_PAGE_RULES` 给 51 个策略端点挂占位视图，`install_legacy_retirement` 照旧在启动期换成跳转/410 适配器；端点名不变，`url_for("scheduler.batches_page")` 之类调用照常可用。旧 POST、JSON 数据、Excel 预览/确认/模板/导出接口一律不再存在（404）。
3. **保留的三块真实处理器**：说明书页 `web/routes/workbench/manual_page.py`（端点 `scheduler.config_manual_page` / `config_manual_download`，工作台 help_url 仍指向它）；运行时接口 `web/routes/workbench/system_runtime.py`（`system.health`、`system.runtime_shutdown`，启动器依赖）；方案上下文令牌 `web/plan_context_token.py`（从 `web/routes/domains/scheduler/scheduler_plan_context_token.py` 平移）。
4. **周派工单打印页改为退役**：`scheduler.week_plan_print_page` 由 restyle 改 retired。它在工作台里没有任何入口，却要拖住 `GanttService`、`scheduler_week_plan_query`、`navigation_context` 一整片旧层；退役页给出明确文案，`week_plan_print_sheet` 等核心模块随之删除。若日后需要打印周计划，应基于工作台数据源重做，而不是恢复旧页。
5. **退役页不再提供“按原条件下载旧报表”链接**：旧报表导出接口已删，`legacy_navigation` 去掉 `_REPORT_EXPORTS`/`_download_links`，退役文案改为“原来的数据都还在”。
6. **随之失去调用方的核心模块一并删除**（按 import 图 + 符号级 grep 双重确认在 `core`/`web`/`data`/`plugins`/入口文件里无引用）：五个旧 Excel 导入服务、`unit_excel_converter`、`external_group_service`、`resource_dispatch_excel`、`week_plan_excel`/`week_plan_print_sheet`/`week_plan_daily_summary`、`report_number_parsing`、`schedule_diagnostic_contract`、`batch_query_service`/`part_operation_query_service`/`machine_downtime_query_service`、`resource_dispatch_execution_tokens`、`toggle_values` 及 `history_summary_parser`、`graph/ready_queue`、`execution_ledger_legacy|quality|totals` 兼容垫片。`excel_audit`（调用图工具样例）与 `excel_backend_factory`（插件 `excel_backend.*` 能力入口）虽无产品调用方，暂留。
7. **配套同步**：`build_win7_onedir.bat` 去掉旧路由 hidden-import；`tools/test_registry_*`、`tools/quality_gate_shared.py`、`pyrightconfig.tools.json`、`tools/browser_lane_files.py`、`tools/ui_copy_glossary.json` 去掉指向已删文件的登记；`开发文档/系统速查表.md` 删掉 149 条已不存在的接口；`开发文档/技术债务治理台账.md` 去掉指向已删文件的静默回退登记并刷新行号；`docs/dev/aps_three_gap_quality_gate.md` 与 `.codestable/architecture/*.md` 标注旧层已删除。

## 测试处理

只测旧页面/旧视图模型/旧服务容器的测试文件删除，混合文件裁掉旧层用例（`/tmp` 里的 AST 裁剪脚本），元测试里的样例路径改指向仍存在且已登记的文件。判定口径与方案 B 相同：看被测模块从 `core/services/workbench`、`web/routes/workbench`、`web/bootstrap` 是否可达。全套收集 15856 → 15156。

## 验证

- `create_app` 冒烟：URL 规则 368 → 219（workbench 164 + static 1 + 策略页占位 51 + 说明书页/下载 2 + 健康/关停 2）。
- 全套非浏览器测试：并行车道 12724 passed（最后 3 处失败与 7 处夹具错误已修并单独复跑通过），串行车道 2026 passed 1 skipped；全套收集 15156。
- ruff、pyright tools 0 errors、`tools.scan_import_cycles --include-tests` 退出 0（残留环均为既有）、`python -m tools.browser_lane_files --check` 127 files、`tests/gate_meta/check_quickref_vs_routes.py` OK、`scripts/sync_debt_ledger.py check` 通过。
- 日常门禁随 pre-push 钩子执行，结果见会话汇报；未跑正式全量门禁与浏览器车道实跑。
- 规模：web/ 由约 4.7 万行降到约 2.0 万行；连同核心死模块与测试，共删除约 290 个文件、5.4 万行。

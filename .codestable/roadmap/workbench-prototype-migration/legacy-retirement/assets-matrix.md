# 旧 UI 资源与候选交付树矩阵

- 状态：设计未应用。只在 Main 批准 18 后裁剪新的候选交付树；不删除当前源码、既有包、离线归档或旧 preview。
- 实读 73 个 HTML 模板、59 个非 workbench 静态文件、现行 manifest 的 210 个新资源。详细每文件 SHA256、引用及 POST 依赖见 `assets-matrix.json`。以下引用均是现读源码位置，不由文件名推定用途。
- 候选移除目标为 68 个旧模板，包含打印与帮助的旧呈现；3 个 workbench 模板和 2 个通用错误模板保留。通用错误页使用独立 error_base，不依赖 base.html，不可将它们随旧布局删除。
- 旧静态载荷为 9 CSS、45 JS、2 SVG、2 文档和 1 元数据文件。CSS/JS/SVG 的移除均有消费者前置条件；2 个打印共享 CSS 不可先删。`.DS_Store` 仅不纳入新候选清单，不执行源文件清理。

## 1. 模板逐文件去向

| 文件 | 待应用动作 | 现读引用 / 保留原因 |
| --- | --- | --- |
| `templates/base.html` | 页面去向及所有引用迁完后移除 | `templates/dashboard.html:1`；`templates/equipment/detail.html:1`；`templates/equipment/downtime_batch.html:1`；其余见 JSON |
| `templates/components/_plan_context_capsule.html` | 页面去向及所有引用迁完后移除 | `templates/base.html:113` |
| `templates/components/excel_action_cards.html` | 页面去向及所有引用迁完后移除 | `templates/equipment/list.html:3`；`templates/personnel/list.html:3`；`templates/process/list.html:3`；其余见 JSON |
| `templates/components/excel_import.html` | 页面去向及所有引用迁完后移除 | `templates/equipment/excel_import_machine.html:19`；`templates/equipment/excel_import_machine_operator.html:22`；`templates/excel/demo.html:3`；其余见 JSON |
| `templates/components/manual_macros.html` | 页面去向及所有引用迁完后移除 | `templates/components/ui_macros.html:5` |
| `templates/components/reports_nav_macros.html` | 页面去向及所有引用迁完后移除 | `templates/reports/downtime.html:3`；`templates/reports/execution_review.html:3`；`templates/reports/index.html:3`；其余见 JSON |
| `templates/components/ui_macros.html` | 页面去向及所有引用迁完后移除 | `templates/base.html:55`；`templates/components/reports_nav_macros.html:1`；`templates/dashboard.html:2`；其余见 JSON |
| `templates/components/workbench_nav_macros.html` | 页面去向及所有引用迁完后移除 | `templates/components/ui_macros.html:6` |
| `templates/dashboard.html` | 页面去向及所有引用迁完后移除 | `web/routes/dashboard.py:450` |
| `templates/equipment/detail.html` | 页面去向及所有引用迁完后移除 | `web/routes/equipment_pages.py:223` |
| `templates/equipment/downtime_batch.html` | 页面去向及所有引用迁完后移除 | `web/routes/equipment_downtimes.py:26` |
| `templates/equipment/excel_import_machine.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/equipment_excel_machines.py:164`；仍有 2 个 POST 呈现依赖 |
| `templates/equipment/excel_import_machine_operator.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/equipment_excel_links.py:83`；仍有 2 个 POST 呈现依赖 |
| `templates/equipment/list.html` | 页面去向及所有引用迁完后移除 | `web/routes/equipment_pages.py:153` |
| `templates/error.html` | 保留错误能力；只换独立样式 | `web/error_boundary.py:357 (template_name 默认值)` |
| `templates/error_base.html` | 保留错误能力；只换独立样式 | `templates/error.html:1` |
| `templates/excel/demo.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/excel_demo.py:57`；仍有 2 个 POST 呈现依赖 |
| `templates/material/batch_materials.html` | 页面去向及所有引用迁完后移除 | `web/routes/material.py:133` |
| `templates/material/materials.html` | 页面去向及所有引用迁完后移除 | `web/routes/material.py:29` |
| `templates/personnel/calendar.html` | 页面去向及所有引用迁完后移除 | `web/routes/personnel_calendar_pages.py:62` |
| `templates/personnel/detail.html` | 页面去向及所有引用迁完后移除 | `web/routes/personnel_pages.py:144` |
| `templates/personnel/excel_import_operator.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/personnel_excel_operators.py:74`；仍有 2 个 POST 呈现依赖 |
| `templates/personnel/excel_import_operator_calendar.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/personnel_excel_operator_calendar.py:112`；仍有 2 个 POST 呈现依赖 |
| `templates/personnel/excel_import_operator_machine.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/personnel_excel_links.py:100`；仍有 2 个 POST 呈现依赖 |
| `templates/personnel/list.html` | 页面去向及所有引用迁完后移除 | `web/routes/personnel_pages.py:110` |
| `templates/personnel/teams.html` | 页面去向及所有引用迁完后移除 | `web/routes/personnel_teams.py:32` |
| `templates/process/detail.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_parts.py:153` |
| `templates/process/excel_import_op_types.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/process_excel_op_types.py:61`；仍有 2 个 POST 呈现依赖 |
| `templates/process/excel_import_part_operation_hours.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/process_excel_part_operation_hours.py:224`；仍有 2 个 POST 呈现依赖 |
| `templates/process/excel_import_routes.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/process_excel_routes.py:82`；仍有 2 个 POST 呈现依赖 |
| `templates/process/excel_import_suppliers.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/process_excel_suppliers.py:63`；仍有 2 个 POST 呈现依赖 |
| `templates/process/excel_part_ops_export.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_excel_part_operations.py:22` |
| `templates/process/list.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_parts.py:84` |
| `templates/process/op_type_detail.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_op_types.py:48` |
| `templates/process/op_types_list.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_op_types.py:23` |
| `templates/process/supplier_detail.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_suppliers.py:85` |
| `templates/process/suppliers_list.html` | 页面去向及所有引用迁完后移除 | `web/routes/process_suppliers.py:44` |
| `templates/reports/downtime.html` | 页面去向及所有引用迁完后移除 | `web/routes/reports.py:41` |
| `templates/reports/execution_review.html` | 页面去向及所有引用迁完后移除 | `web/routes/reports.py:36` |
| `templates/reports/index.html` | 页面去向及所有引用迁完后移除 | `web/routes/reports.py:21` |
| `templates/reports/overdue.html` | 页面去向及所有引用迁完后移除 | `web/routes/reports.py:26` |
| `templates/reports/utilization.html` | 页面去向及所有引用迁完后移除 | `web/routes/reports.py:31` |
| `templates/scheduler/_config_switches.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/config.html:296` |
| `templates/scheduler/_run_panel.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/batches.html:117` |
| `templates/scheduler/analysis.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_analysis.py:125` |
| `templates/scheduler/analysis_parts/_action_hub.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:27` |
| `templates/scheduler/analysis_parts/_candidate_comparison.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:29` |
| `templates/scheduler/analysis_parts/_diagnostic_sections.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:30` |
| `templates/scheduler/analysis_parts/_metric_cards.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:31` |
| `templates/scheduler/analysis_parts/_optimization_process.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:32` |
| `templates/scheduler/analysis_parts/_selected_overview.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:26` |
| `templates/scheduler/analysis_parts/_summary_warnings.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:28` |
| `templates/scheduler/analysis_parts/_trend_charts.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:35` |
| `templates/scheduler/analysis_parts/_version_picker.html` | 页面去向及所有引用迁完后移除 | `templates/scheduler/analysis.html:17` |
| `templates/scheduler/batch_detail.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_batch_detail.py:428` |
| `templates/scheduler/batches.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_batches.py:125` |
| `templates/scheduler/batches_manage.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_batches.py:173` |
| `templates/scheduler/calendar.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_calendar_pages.py:32` |
| `templates/scheduler/config.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_config.py:339` |
| `templates/scheduler/config_manual.html` | 先新样式帮助，再移除旧模板 | `web/routes/domains/scheduler/scheduler_config.py:271` |
| `templates/scheduler/excel_import_batches.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/domains/scheduler/scheduler_excel_batches.py:98`；仍有 2 个 POST 呈现依赖 |
| `templates/scheduler/excel_import_calendar.html` | 先迁移 POST 结果呈现，再移除 | `web/routes/domains/scheduler/scheduler_excel_calendar.py:86`；仍有 2 个 POST 呈现依赖 |
| `templates/scheduler/gantt.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_gantt.py:281` |
| `templates/scheduler/resource_dispatch.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_resource_dispatch.py:240` |
| `templates/scheduler/week_plan.html` | 页面去向及所有引用迁完后移除 | `web/routes/domains/scheduler/scheduler_week_plan.py:324` |
| `templates/scheduler/week_plan_print.html` | 先新样式打印，再移除旧模板 | `web/routes/domains/scheduler/scheduler_week_plan_print.py:139` |
| `templates/system/backup.html` | 页面去向及所有引用迁完后移除 | `web/routes/system_backup.py:93` |
| `templates/system/history.html` | 页面去向及所有引用迁完后移除 | `web/routes/system_history.py:122` |
| `templates/system/logs.html` | 页面去向及所有引用迁完后移除 | `web/routes/system_logs.py:65` |
| `templates/system/runtime_logs.html` | 页面去向及所有引用迁完后移除 | `web/routes/system_runtime_logs.py:65` |
| `templates/workbench/index.html` | 保留新工作台模板 | `web/routes/workbench/pages.py:70` |
| `templates/workbench/recovery.html` | 保留新工作台模板 | `web/bootstrap/workbench_system_restore_view.py:69 (独立模板读取)` |
| `templates/workbench/unavailable.html` | 保留新工作台模板 | `web/routes/workbench/pages.py:53`；`web/routes/workbench/pages.py:58` |

## 2. 旧静态文件逐一去向

| 文件 | 待应用动作 | 当前实际引用 |
| --- | --- | --- |
| `static/.DS_Store` | 不纳入新候选；不清理源文件 | 非页面载荷；仅正向清单不收录 |
| `static/css/00-tokens.css` | 共同依赖，打印新呈现就绪前不能删 | `templates/base.html:42`；`templates/scheduler/week_plan_print.html:12` |
| `static/css/aps_gantt.css` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:6`；`templates/scheduler/resource_dispatch.html:6` |
| `static/css/calendar_picker.css` | 消费者迁完后从新候选排除 | `templates/personnel/calendar.html:4`；`templates/scheduler/calendar.html:4` |
| `static/css/compatibility.css` | 消费者迁完后从新候选排除 | `templates/base.html:44` |
| `static/css/frappe-gantt.css` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:5`；`templates/scheduler/resource_dispatch.html:5` |
| `static/css/print.css` | 共同依赖，打印新呈现就绪前不能删 | `templates/base.html:46`；`templates/scheduler/week_plan_print.html:13` |
| `static/css/resource_dispatch.css` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:7` |
| `static/css/style.css` | 消费者迁完后从新候选排除 | `templates/base.html:43` |
| `static/css/ui_contract.css` | 消费者迁完后从新候选排除 | `templates/base.html:45` |
| `static/docs/aps_three_gap_user_guide.md` | 保留文档内容及下载 | `未找到当前运行引用，不等于获得删除文档授权` |
| `static/docs/scheduler_manual.md` | 保留文档内容及下载 | `web/routes/domains/scheduler/scheduler_config.py:59` |
| `static/favicon.svg` | 消费者迁完后从新候选排除 | `templates/base.html:7` |
| `static/icons.svg` | 消费者迁完后从新候选排除 | `templates/components/ui_macros.html:26`；`templates/components/ui_macros.html:40`；其余见 JSON |
| `static/js/batch_detail_linkage.js` | 消费者迁完后从新候选排除 | `templates/scheduler/batch_detail.html:372` |
| `static/js/calendar_picker.js` | 消费者迁完后从新候选排除 | `templates/personnel/calendar.html:170`；`templates/scheduler/calendar.html:151` |
| `static/js/common.js` | 消费者迁完后从新候选排除 | `templates/base.html:166` |
| `static/js/common_confirm.js` | 消费者迁完后从新候选排除 | `templates/base.html:172` |
| `static/js/common_draft.js` | 消费者迁完后从新候选排除 | `templates/base.html:174` |
| `static/js/common_flash.js` | 消费者迁完后从新候选排除 | `templates/base.html:169` |
| `static/js/common_manual_popover.js` | 消费者迁完后从新候选排除 | `templates/base.html:167` |
| `static/js/common_prefetch.js` | 消费者迁完后从新候选排除 | `templates/base.html:175` |
| `static/js/common_required.js` | 消费者迁完后从新候选排除 | `templates/base.html:168` |
| `static/js/common_table.js` | 消费者迁完后从新候选排除 | `templates/base.html:173` |
| `static/js/common_theme.js` | 消费者迁完后从新候选排除 | `templates/base.html:170` |
| `static/js/common_toast.js` | 消费者迁完后从新候选排除 | `templates/base.html:171` |
| `static/js/config_manual.js` | 消费者迁完后从新候选排除 | `templates/scheduler/config_manual.html:126` |
| `static/js/downtime_batch.js` | 消费者迁完后从新候选排除 | `templates/equipment/downtime_batch.html:73` |
| `static/js/excel_handler.js` | 消费者迁完后从新候选排除 | `templates/equipment/excel_import_machine.html:53`；`templates/equipment/excel_import_machine_operator.html:58`；其余见 JSON |
| `static/js/frappe-gantt.min.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:283`；`templates/scheduler/resource_dispatch.html:434` |
| `static/js/gantt.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:284` |
| `static/js/gantt_adapter.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:286` |
| `static/js/gantt_boot.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:301` |
| `static/js/gantt_chain_walk.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:297` |
| `static/js/gantt_color.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:287` |
| `static/js/gantt_contract.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:289` |
| `static/js/gantt_decorations.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:296` |
| `static/js/gantt_help.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:290` |
| `static/js/gantt_holidays.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:294` |
| `static/js/gantt_legend.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:293` |
| `static/js/gantt_load_strip.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:295` |
| `static/js/gantt_outline.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:288` |
| `static/js/gantt_popup.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:292` |
| `static/js/gantt_popup_fit.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:291`；`templates/scheduler/resource_dispatch.html:435` |
| `static/js/gantt_render.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:298` |
| `static/js/gantt_ui.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:300` |
| `static/js/gantt_zoom.js` | 消费者迁完后从新候选排除 | `templates/scheduler/gantt.html:285` |
| `static/js/report_plan_filter.js` | 消费者迁完后从新候选排除 | `templates/reports/downtime.html:156`；`templates/reports/overdue.html:187`；其余见 JSON |
| `static/js/resource_dispatch_boot.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:445` |
| `static/js/resource_dispatch_core.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:438` |
| `static/js/resource_dispatch_shared.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:437` |
| `static/js/resource_execution.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:444` |
| `static/js/resource_execution_actual.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:442` |
| `static/js/resource_execution_cards.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:441` |
| `static/js/resource_execution_context.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:439` |
| `static/js/resource_execution_import.js` | 消费者迁完后从新候选排除 | `templates/scheduler/resource_dispatch.html:443` |
| `static/js/scheduler_form_feedback.js` | 消费者迁完后从新候选排除 | `templates/equipment/list.html:198`；`templates/personnel/list.html:175`；其余见 JSON |
| `static/js/scheduler_run.js` | 消费者迁完后从新候选排除 | `templates/scheduler/batches.html:290` |
| `static/js/table_resize.js` | 消费者迁完后从新候选排除 | `templates/base.html:176` |

## 3. 必须保留的新资源与构建边界

- 新 manifest 的 210 项全部在 `assets-matrix.json.workbench_assets` 逐项列出：真实文件 hash 全匹配，dependency 均在该 manifest 中。凡路径在此闭包内的 JS、CSS、字体、React/ReactDOM、license、图标均保留，不能因为名称含 prototype/foundation/旧组件而删除。`scripts/workbench/build-order.json` 的 foundation 明确消费 `_ds_bundle.js` 的组件声明，这不是旧路由继续运行的证据。
- `templates/workbench/index.html:7` / `:9` / `:16` 从 manifest 读取 theme/styles/scripts；新 CSS/字体使用 `workbench/prototype/...` 的复制资产，与 `static/css/...` 不是同一文件。所有许可来源继续随新 manifest 交付。
- 当前 `static/workbench/asset-manifest.json` build_id=`67229ad0b232830132f049095e8c8c8b80ba29296df7b3668a128af1ebec5c78`，是旧预览资源。只读检查发现 inputs 中 theme.js、FieldFiles.jsx、main.jsx、build-order.json 共 4 项与当前源码不一致，不能用于最新终验。
- round1 离线 build_id=`eaa69eec9bf98dbecac97b6be1baa322ff34c2a5df4ca1264ddd0bd4548bf8bf` 的 inputs 仍有 theme.js、main.jsx、build-order.json 共 3 项不匹配。该记录不能冒充本轮重新构建或浏览器验收。
- `static/workbench/assets/foundation-c6054c2ae97a14f0.js` 是目录里存在但现行 manifest 未列入的额外文件。仅在全新 candidate 按最终 manifest 正向收录时不带入；不清旧 static、不改旧 manifest、不把它误称旧 Jinja UI。
- 必须保留：`templates_excel/` 模板及真实下载来源、`static/docs/` 文档、`schema.sql`、迁移/服务/仓储/插件与 runtime 依赖。旧 UI 退役不是后端死代码清理授权。

## 4. 必须联动但本任务不修改

- `build_win7_onedir.bat:66` / `:93` 目前整体收录 templates/static；只改 workbench manifest 不会自动排除旧文件。Main 以后让构建入口消费经审查的 candidate 正向清单，或等价地先构造只含允许资源的树。本轮不运行或修改 Win7 打包。
- `validate_dist_exe.py:41` / `:42` 与 `tests/app_runtime/test_validate_dist_static_payload.py:57` 仍要求旧 `css/style.css`、`js/common.js`。后续换成最终 manifest + 新入口的真实字节/哈希检查，并新增移除资源 HTTP 不可取；不能为满足旧断言把旧资源夹带回包。
- `templates/base.html` 的 url_for、macros、旧 JS 消费者只在旧呈现退役后才能一起移除。打印的 `00-tokens.css` / `print.css` 已明确找到保留消费者，替代样式完成前不能删。
- source backup 放 Web 根目录和 candidate 外；candidate 不含 `source.tar.gz`、`restore-check`、`.git`、测试/临时数据、浏览器 profile。此处只规定清单，不执行任何移除。

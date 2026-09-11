# 旧路由逐项处置矩阵

- 现读真实注册 356 条：51 条旧页面 GET（35 条条件重定向、14 条明确说明、2 条保留打印/帮助能力并改呈现）、39 条旧非页面 GET、113 条旧 POST、152 条 workbench、1 条静态规则。
- 完整 endpoint + method + 实际函数位置 + 文件 SHA256 在 `routes-matrix.json`，不以 URL 字面或文件名推定可删。正向查询和下载的实际呈现调用依据在 `assets-matrix.json.render_calls`。这不是 HTTP 验收结果。
- 以下目标是逻辑工作区/对象，不是已经实现的额外 URL。R 的规范地址基础是 `/workbench?view=<view>`，trial 使用已有 `/workbench/trial`；context 进入 URL、boot 和目标组件的严格承接合同见 `minimum-design.md`。有不等价参数时 R 必须改走 N，不能部分扔掉筛选。

## 1. 页面 GET：51 条不漏

| 原规则 / endpoint | 待应用处置 | 目标 / 说明项 | 上下文组 | 实际函数 |
| --- | --- | --- | --- | --- |
| `/` / `dashboard.index` | R：满足等价子集才重定向 | dashboard | P,D,R | `web/routes/dashboard.py:341` |
| `/equipment/` / `equipment.list_page` | R：满足等价子集才重定向 | process/machine | L,M | `web/routes/equipment_pages.py:119` |
| `/equipment/<machine_id>` / `equipment.detail_page` | R：满足等价子集才重定向 | process/machine/detail | M | `web/routes/equipment_pages.py:199` |
| `/equipment/downtimes/batch` / `equipment.downtime_batch_page` | N：新样式退役说明 | LEG-055 | M | `web/routes/equipment_downtimes.py:15` |
| `/equipment/excel/links` / `equipment.excel_link_page` | N：新样式退役说明 | LEG-052 | X | `web/routes/equipment_excel_links.py:101` |
| `/equipment/excel/machines` / `equipment.excel_machine_page` | R：满足等价子集才重定向 | process/machine/import | X | `web/routes/equipment_excel_machines.py:182` |
| `/excel-demo/` / `excel_demo.index` | N：新样式退役说明 | Excel 演示入口 | X | `web/routes/excel_demo.py:88` |
| `/material/` / `material.index` | R：满足等价子集才重定向 | process/material | M | `web/routes/material.py:16` |
| `/material/batches` / `material.batch_materials_page` | N：新样式退役说明 | LEG-060 | M | `web/routes/material.py:101` |
| `/material/materials` / `material.materials_page` | R：满足等价子集才重定向 | process/material | L,M | `web/routes/material.py:21` |
| `/personnel/` / `personnel.list_page` | R：满足等价子集才重定向 | process/operator | L,M | `web/routes/personnel_pages.py:89` |
| `/personnel/<operator_id>` / `personnel.detail_page` | R：满足等价子集才重定向 | process/operator/detail | M | `web/routes/personnel_pages.py:140` |
| `/personnel/<operator_id>/calendar` / `personnel.operator_calendar_page` | N：新样式退役说明 | LEG-056 | D,M | `web/routes/personnel_calendar_pages.py:33` |
| `/personnel/excel/links` / `personnel.excel_link_page` | N：新样式退役说明 | LEG-052 | X | `web/routes/personnel_excel_links.py:118` |
| `/personnel/excel/operator_calendar` / `personnel.excel_operator_calendar_page` | N：新样式退役说明 | LEG-056 | X | `web/routes/personnel_excel_operator_calendar.py:161` |
| `/personnel/excel/operators` / `personnel.excel_operator_page` | R：满足等价子集才重定向 | process/operator/import | X | `web/routes/personnel_excel_operators.py:105` |
| `/personnel/teams` / `personnel.teams_page` | N：新样式退役说明 | LEG-054 | L,M | `web/routes/personnel_teams.py:18` |
| `/process/` / `process.list_parts` | R：满足等价子集才重定向 | process/part | L,M | `web/routes/process_parts.py:61` |
| `/process/excel/op-types` / `process.excel_op_type_page` | R：满足等价子集才重定向 | process/op_type/import | X | `web/routes/process_excel_op_types.py:143` |
| `/process/excel/part-operation-hours` / `process.excel_part_op_hours_page` | R：满足等价子集才重定向 | process/part/hours-import | X | `web/routes/process_excel_part_operation_hours.py:243` |
| `/process/excel/part-operations` / `process.excel_part_ops_page` | N：新样式退役说明 | 工序明细导出旧外壳；保留真实 XLSX | M | `web/routes/process_excel_part_operations.py:20` |
| `/process/excel/routes` / `process.excel_routes_page` | R：满足等价子集才重定向 | process/part/route-import | X | `web/routes/process_excel_routes.py:152` |
| `/process/excel/suppliers` / `process.excel_supplier_page` | R：满足等价子集才重定向 | process/supplier/import | X | `web/routes/process_excel_suppliers.py:123` |
| `/process/op-types` / `process.op_types_page` | R：满足等价子集才重定向 | process/op_type | L,M | `web/routes/process_op_types.py:17` |
| `/process/op-types/<op_type_id>` / `process.op_type_detail` | R：满足等价子集才重定向 | process/op_type/detail | M | `web/routes/process_op_types.py:44` |
| `/process/parts/<part_no>` / `process.part_detail` | R：满足等价子集才重定向 | process/part/detail | M | `web/routes/process_parts.py:123` |
| `/process/suppliers` / `process.suppliers_page` | R：满足等价子集才重定向 | process/supplier | L,M | `web/routes/process_suppliers.py:24` |
| `/process/suppliers/<supplier_id>` / `process.supplier_detail` | R：满足等价子集才重定向 | process/supplier/detail | M | `web/routes/process_suppliers.py:77` |
| `/reports/` / `reports.index` | R：满足等价子集才重定向 | reports/catalog | P,D,R | `web/routes/reports.py:19` |
| `/reports/downtime` / `reports.downtime_page` | R：满足等价子集才重定向 | reports/catalog:downtime | P,D,R | `web/routes/reports.py:39` |
| `/reports/execution-review` / `reports.execution_review_page` | R：满足等价子集才重定向 | reports/catalog:official-review | P,D,R | `web/routes/reports.py:34` |
| `/reports/overdue` / `reports.overdue_page` | R：满足等价子集才重定向 | reports/catalog:overdue | P,R | `web/routes/reports.py:24` |
| `/reports/utilization` / `reports.utilization_page` | R：满足等价子集才重定向 | reports/catalog:utilization | P,D,R | `web/routes/reports.py:29` |
| `/scheduler/` / `scheduler.batches_page` | R：满足等价子集才重定向 | run | P,L,X | `web/routes/domains/scheduler/scheduler_batches.py:67` |
| `/scheduler/analysis` / `scheduler.analysis_page` | R：满足等价子集才重定向 | analysis | P,D,R | `web/routes/domains/scheduler/scheduler_analysis.py:71` |
| `/scheduler/batches` / `scheduler.batches_manage_page` | R：满足等价子集才重定向 | batches | L,M | `web/routes/domains/scheduler/scheduler_batches.py:132` |
| `/scheduler/batches/<batch_id>` / `scheduler.batch_detail` | R：满足等价子集才重定向 | batches/detail | P,M | `web/routes/domains/scheduler/scheduler_batch_detail.py:382` |
| `/scheduler/calendar` / `scheduler.calendar_page` | R：满足等价子集才重定向 | process/calendar | D,M | `web/routes/domains/scheduler/scheduler_calendar_pages.py:12` |
| `/scheduler/config` / `scheduler.config_page` | N：新样式退役说明 | LEG-011,018..034 | X | `web/routes/domains/scheduler/scheduler_config.py:315` |
| `/scheduler/config/manual` / `scheduler.config_manual_page` | S：保留能力，重做呈现 | workbench/manual (拟新增呈现) | H | `web/routes/domains/scheduler/scheduler_config.py:244` |
| `/scheduler/excel/batches` / `scheduler.excel_batches_page` | R：满足等价子集才重定向 | batches/import | X | `web/routes/domains/scheduler/scheduler_excel_batches.py:139` |
| `/scheduler/excel/calendar` / `scheduler.excel_calendar_page` | N：新样式退役说明 | LEG-058 | X,D | `web/routes/domains/scheduler/scheduler_excel_calendar.py:138` |
| `/scheduler/gantt` / `scheduler.gantt_page` | R：满足等价子集才重定向 | gantt | P,D,R,U | `web/routes/domains/scheduler/scheduler_gantt.py:158` |
| `/scheduler/resource-dispatch` / `scheduler.resource_dispatch_page` | N：新样式退役说明 | LEG-068,070 | P,D,R,U | `web/routes/domains/scheduler/scheduler_resource_dispatch.py:216` |
| `/scheduler/week-plan` / `scheduler.week_plan_page` | N：新样式退役说明 | LEG-009；保留导出/打印链接 | P,D,R | `web/routes/domains/scheduler/scheduler_week_plan.py:258` |
| `/scheduler/week-plan/print` / `scheduler.week_plan_print_page` | S：保留能力，重做呈现 | workbench/print (拟新增呈现) | P,D,R,U | `web/routes/domains/scheduler/scheduler_week_plan_print.py:106` |
| `/system/` / `system.index` | R：满足等价子集才重定向 | system | S | `web/routes/system_backup.py:74` |
| `/system/backup` / `system.backup_page` | R：满足等价子集才重定向 | system/backups | S | `web/routes/system_backup.py:79` |
| `/system/history` / `system.history_page` | N：新样式退役说明 | LEG-075 | P,L | `web/routes/system_history.py:49` |
| `/system/logs` / `system.logs_page` | R：满足等价子集才重定向 | system/operations | S | `web/routes/system_logs.py:30` |
| `/system/runtime-logs` / `system.runtime_logs_page` | R：满足等价子集才重定向 | system/runtime | S | `web/routes/system_runtime_logs.py:39` |

## 2. 必须保留的非页面 GET：39 条

这些入口仍执行原领域查询/下载/健康合同，不能被 HTML 退役器、通用 410 或 SPA fallback 覆盖。导出失败原本返回页面时，该错误结果要进入新说明/新回执，不留旧模板。下载成功必须核对 MIME、Disposition、真实非空字节及业务内容。

| 原规则 | endpoint | 实际函数 |
| --- | --- | --- |
| `/equipment/excel/links/export` | `equipment.excel_link_export` | `web/routes/equipment_excel_links.py:283` |
| `/equipment/excel/links/template` | `equipment.excel_link_template` | `web/routes/equipment_excel_links.py:237` |
| `/equipment/excel/machines/export` | `equipment.excel_machine_export` | `web/routes/equipment_excel_machines.py:438` |
| `/equipment/excel/machines/template` | `equipment.excel_machine_template` | `web/routes/equipment_excel_machines.py:393` |
| `/excel-demo/template` | `excel_demo.download_template` | `web/routes/excel_demo.py:215` |
| `/personnel/excel/links/export` | `personnel.excel_link_export` | `web/routes/personnel_excel_links.py:289` |
| `/personnel/excel/links/template` | `personnel.excel_link_template` | `web/routes/personnel_excel_links.py:243` |
| `/personnel/excel/operator_calendar/export` | `personnel.excel_operator_calendar_export` | `web/routes/personnel_excel_operator_calendar.py:409` |
| `/personnel/excel/operator_calendar/template` | `personnel.excel_operator_calendar_template` | `web/routes/personnel_excel_operator_calendar.py:364` |
| `/personnel/excel/operators/export` | `personnel.excel_operator_export` | `web/routes/personnel_excel_operators.py:338` |
| `/personnel/excel/operators/template` | `personnel.excel_operator_template` | `web/routes/personnel_excel_operators.py:291` |
| `/process/excel/op-types/export` | `process.excel_op_type_export` | `web/routes/process_excel_op_types.py:330` |
| `/process/excel/op-types/template` | `process.excel_op_type_template` | `web/routes/process_excel_op_types.py:284` |
| `/process/excel/part-operation-hours/export` | `process.excel_part_op_hours_export` | `web/routes/process_excel_part_operation_hours.py:445` |
| `/process/excel/part-operation-hours/template` | `process.excel_part_op_hours_template` | `web/routes/process_excel_part_operation_hours.py:399` |
| `/process/excel/part-operations/export` | `process.excel_part_ops_export` | `web/routes/process_excel_part_operations.py:31` |
| `/process/excel/routes/export` | `process.excel_routes_export` | `web/routes/process_excel_routes.py:346` |
| `/process/excel/routes/template` | `process.excel_routes_template` | `web/routes/process_excel_routes.py:300` |
| `/process/excel/suppliers/export` | `process.excel_supplier_export` | `web/routes/process_excel_suppliers.py:380` |
| `/process/excel/suppliers/template` | `process.excel_supplier_template` | `web/routes/process_excel_suppliers.py:334` |
| `/reports/downtime/export` | `reports.downtime_export` | `web/routes/reports_export_routes.py:129` |
| `/reports/execution-review/export` | `reports.execution_review_export` | `web/routes/reports_export_routes.py:98` |
| `/reports/overdue/export` | `reports.overdue_export` | `web/routes/reports_export_routes.py:28` |
| `/reports/utilization/export` | `reports.utilization_export` | `web/routes/reports_export_routes.py:56` |
| `/scheduler/config/manual/download` | `scheduler.config_manual_download` | `web/routes/domains/scheduler/scheduler_config.py:289` |
| `/scheduler/excel/batches/export` | `scheduler.excel_batches_export` | `web/routes/domains/scheduler/scheduler_excel_batches.py:392` |
| `/scheduler/excel/batches/template` | `scheduler.excel_batches_template` | `web/routes/domains/scheduler/scheduler_excel_batches.py:347` |
| `/scheduler/excel/calendar/export` | `scheduler.excel_calendar_export` | `web/routes/domains/scheduler/scheduler_excel_calendar.py:388` |
| `/scheduler/excel/calendar/template` | `scheduler.excel_calendar_template` | `web/routes/domains/scheduler/scheduler_excel_calendar.py:343` |
| `/scheduler/gantt/data` | `scheduler.gantt_data` | `web/routes/domains/scheduler/scheduler_gantt.py:315` |
| `/scheduler/resource-dispatch/data` | `scheduler.resource_dispatch_data` | `web/routes/domains/scheduler/scheduler_resource_dispatch.py:252` |
| `/scheduler/resource-dispatch/execution/<int:op_id>/events` | `scheduler.resource_dispatch_execution_events` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:61` |
| `/scheduler/resource-dispatch/execution/actual-template` | `scheduler.resource_dispatch_actual_template` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:242` |
| `/scheduler/resource-dispatch/execution/data` | `scheduler.resource_dispatch_execution_data` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:48` |
| `/scheduler/resource-dispatch/execution/tasks/<task_key>/events` | `scheduler.resource_dispatch_execution_events_by_task` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:95` |
| `/scheduler/resource-dispatch/export` | `scheduler.resource_dispatch_export` | `web/routes/domains/scheduler/scheduler_resource_dispatch.py:264` |
| `/scheduler/week-plan/export` | `scheduler.week_plan_export` | `web/routes/domains/scheduler/scheduler_week_plan.py:370` |
| `/system/health` | `system.health` | `web/routes/system_health.py:15` |
| `/system/runtime-logs/diagnostic-package` | `system.runtime_logs_diagnostic_package` | `web/routes/system_runtime_logs.py:89` |

## 3. 必须保留的 POST：113 条

不改命令、schema、服务、事务、校验、文件/日志保留和返回成功/失败语义。同模块 AST 正向追踪找到至少 24 个 POST 仍能 render 旧 Excel 模板；这些 helper 必须迁到新样式结果呈现后才可删模板。表内“未命中同模块”不是全程序无旧 UI 证明，最终还须调用链和真 HTTP 检查。

| 原规则 | endpoint | 实际函数 | 已证实 HTML 模板依赖 |
| --- | --- | --- | --- |
| `/equipment/<machine_id>/delete` | `equipment.delete_machine` | `web/routes/equipment_pages.py:279` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/downtimes/<int:downtime_id>/cancel` | `equipment.cancel_downtime` | `web/routes/equipment_downtimes.py:86` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/downtimes/create` | `equipment.create_downtime` | `web/routes/equipment_downtimes.py:67` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/link/add` | `equipment.add_link` | `web/routes/equipment_pages.py:363` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/link/remove` | `equipment.remove_link` | `web/routes/equipment_pages.py:388` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/link/update` | `equipment.update_link` | `web/routes/equipment_pages.py:372` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/status` | `equipment.set_status` | `web/routes/equipment_pages.py:268` | 未命中同模块直接/具名 helper render |
| `/equipment/<machine_id>/update` | `equipment.update_machine` | `web/routes/equipment_pages.py:245` | 未命中同模块直接/具名 helper render |
| `/equipment/bulk/delete` | `equipment.bulk_delete` | `web/routes/equipment_pages.py:328` | 未命中同模块直接/具名 helper render |
| `/equipment/bulk/status` | `equipment.bulk_set_status` | `web/routes/equipment_pages.py:290` | 未命中同模块直接/具名 helper render |
| `/equipment/create` | `equipment.create_machine` | `web/routes/equipment_pages.py:171` | 未命中同模块直接/具名 helper render |
| `/equipment/downtimes/batch/create` | `equipment.downtime_batch_create` | `web/routes/equipment_downtimes.py:35` | 未命中同模块直接/具名 helper render |
| `/equipment/excel/links/confirm` | `equipment.excel_link_confirm` | `web/routes/equipment_excel_links.py:170` | `equipment/excel_import_machine_operator.html` @ 83 |
| `/equipment/excel/links/preview` | `equipment.excel_link_preview` | `web/routes/equipment_excel_links.py:114` | `equipment/excel_import_machine_operator.html` @ 83 |
| `/equipment/excel/machines/confirm` | `equipment.excel_machine_confirm` | `web/routes/equipment_excel_machines.py:292` | `equipment/excel_import_machine.html` @ 164 |
| `/equipment/excel/machines/preview` | `equipment.excel_machine_preview` | `web/routes/equipment_excel_machines.py:196` | `equipment/excel_import_machine.html` @ 164 |
| `/excel-demo/confirm` | `excel_demo.confirm` | `web/routes/excel_demo.py:144` | `excel/demo.html` @ 57 |
| `/excel-demo/preview` | `excel_demo.preview` | `web/routes/excel_demo.py:101` | `excel/demo.html` @ 57 |
| `/material/batches/<batch_id>/requirements/add` | `material.batch_material_add` | `web/routes/material.py:145` | 未命中同模块直接/具名 helper render |
| `/material/materials/<material_id>/delete` | `material.materials_delete` | `web/routes/material.py:82` | 未命中同模块直接/具名 helper render |
| `/material/materials/<material_id>/update` | `material.materials_update` | `web/routes/material.py:60` | 未命中同模块直接/具名 helper render |
| `/material/materials/create` | `material.materials_create` | `web/routes/material.py:38` | 未命中同模块直接/具名 helper render |
| `/material/requirements/<int:bm_id>/delete` | `material.batch_material_delete` | `web/routes/material.py:185` | 未命中同模块直接/具名 helper render |
| `/material/requirements/<int:bm_id>/update` | `material.batch_material_update` | `web/routes/material.py:164` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/calendar/upsert` | `personnel.operator_calendar_upsert` | `web/routes/personnel_calendar_pages.py:75` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/delete` | `personnel.delete_operator` | `web/routes/personnel_pages.py:176` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/link/add` | `personnel.add_link` | `web/routes/personnel_pages.py:263` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/link/remove` | `personnel.remove_link` | `web/routes/personnel_pages.py:289` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/link/update` | `personnel.update_link` | `web/routes/personnel_pages.py:272` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/status` | `personnel.set_status` | `web/routes/personnel_pages.py:165` | 未命中同模块直接/具名 helper render |
| `/personnel/<operator_id>/update` | `personnel.update_operator` | `web/routes/personnel_pages.py:152` | 未命中同模块直接/具名 helper render |
| `/personnel/bulk/delete` | `personnel.bulk_delete` | `web/routes/personnel_pages.py:227` | 未命中同模块直接/具名 helper render |
| `/personnel/bulk/status` | `personnel.bulk_set_status` | `web/routes/personnel_pages.py:188` | 未命中同模块直接/具名 helper render |
| `/personnel/create` | `personnel.create_operator` | `web/routes/personnel_pages.py:122` | 未命中同模块直接/具名 helper render |
| `/personnel/excel/links/confirm` | `personnel.excel_link_confirm` | `web/routes/personnel_excel_links.py:175` | `personnel/excel_import_operator_machine.html` @ 100 |
| `/personnel/excel/links/preview` | `personnel.excel_link_preview` | `web/routes/personnel_excel_links.py:132` | `personnel/excel_import_operator_machine.html` @ 100 |
| `/personnel/excel/operator_calendar/confirm` | `personnel.excel_operator_calendar_confirm` | `web/routes/personnel_excel_operator_calendar.py:264` | `personnel/excel_import_operator_calendar.html` @ 112 |
| `/personnel/excel/operator_calendar/preview` | `personnel.excel_operator_calendar_preview` | `web/routes/personnel_excel_operator_calendar.py:174` | `personnel/excel_import_operator_calendar.html` @ 112 |
| `/personnel/excel/operators/confirm` | `personnel.excel_operator_confirm` | `web/routes/personnel_excel_operators.py:197` | `personnel/excel_import_operator.html` @ 74 |
| `/personnel/excel/operators/preview` | `personnel.excel_operator_preview` | `web/routes/personnel_excel_operators.py:120` | `personnel/excel_import_operator.html` @ 74 |
| `/personnel/teams/<team_id>/delete` | `personnel.delete_team` | `web/routes/personnel_teams.py:66` | 未命中同模块直接/具名 helper render |
| `/personnel/teams/<team_id>/update` | `personnel.update_team` | `web/routes/personnel_teams.py:54` | 未命中同模块直接/具名 helper render |
| `/personnel/teams/create` | `personnel.create_team` | `web/routes/personnel_teams.py:41` | 未命中同模块直接/具名 helper render |
| `/process/excel/op-types/confirm` | `process.excel_op_type_confirm` | `web/routes/process_excel_op_types.py:208` | `process/excel_import_op_types.html` @ 61 |
| `/process/excel/op-types/preview` | `process.excel_op_type_preview` | `web/routes/process_excel_op_types.py:157` | `process/excel_import_op_types.html` @ 61 |
| `/process/excel/part-operation-hours/confirm` | `process.excel_part_op_hours_confirm` | `web/routes/process_excel_part_operation_hours.py:314` | `process/excel_import_part_operation_hours.html` @ 224 |
| `/process/excel/part-operation-hours/preview` | `process.excel_part_op_hours_preview` | `web/routes/process_excel_part_operation_hours.py:256` | `process/excel_import_part_operation_hours.html` @ 224 |
| `/process/excel/routes/confirm` | `process.excel_routes_confirm` | `web/routes/process_excel_routes.py:224` | `process/excel_import_routes.html` @ 82 |
| `/process/excel/routes/preview` | `process.excel_routes_preview` | `web/routes/process_excel_routes.py:167` | `process/excel_import_routes.html` @ 82 |
| `/process/excel/suppliers/confirm` | `process.excel_supplier_confirm` | `web/routes/process_excel_suppliers.py:226` | `process/excel_import_suppliers.html` @ 63 |
| `/process/excel/suppliers/preview` | `process.excel_supplier_preview` | `web/routes/process_excel_suppliers.py:137` | `process/excel_import_suppliers.html` @ 63 |
| `/process/op-types/<op_type_id>/delete` | `process.delete_op_type` | `web/routes/process_op_types.py:62` | 未命中同模块直接/具名 helper render |
| `/process/op-types/<op_type_id>/update` | `process.update_op_type` | `web/routes/process_op_types.py:51` | 未命中同模块直接/具名 helper render |
| `/process/op-types/create` | `process.create_op_type` | `web/routes/process_op_types.py:32` | 未命中同模块直接/具名 helper render |
| `/process/parts/<part_no>/delete` | `process.delete_part` | `web/routes/process_parts.py:187` | 未命中同模块直接/具名 helper render |
| `/process/parts/<part_no>/groups/<group_id>/delete` | `process.delete_group` | `web/routes/process_parts.py:296` | 未命中同模块直接/具名 helper render |
| `/process/parts/<part_no>/groups/<group_id>/mode` | `process.set_group_mode` | `web/routes/process_parts.py:263` | 未命中同模块直接/具名 helper render |
| `/process/parts/<part_no>/ops/<int:seq>/hours` | `process.update_internal_hours` | `web/routes/process_parts.py:253` | 未命中同模块直接/具名 helper render |
| `/process/parts/<part_no>/reparse` | `process.reparse_part` | `web/routes/process_parts.py:230` | 未命中同模块直接/具名 helper render |
| `/process/parts/<part_no>/update` | `process.update_part` | `web/routes/process_parts.py:176` | 未命中同模块直接/具名 helper render |
| `/process/parts/bulk/delete` | `process.bulk_delete_parts` | `web/routes/process_parts.py:198` | 未命中同模块直接/具名 helper render |
| `/process/parts/create` | `process.create_part` | `web/routes/process_parts.py:97` | 未命中同模块直接/具名 helper render |
| `/process/suppliers/<supplier_id>/delete` | `process.delete_supplier` | `web/routes/process_suppliers.py:117` | 未命中同模块直接/具名 helper render |
| `/process/suppliers/<supplier_id>/update` | `process.update_supplier` | `web/routes/process_suppliers.py:96` | 未命中同模块直接/具名 helper render |
| `/process/suppliers/create` | `process.create_supplier` | `web/routes/process_suppliers.py:55` | 未命中同模块直接/具名 helper render |
| `/scheduler/batches/<batch_id>/delete` | `scheduler.delete_batch` | `web/routes/domains/scheduler/scheduler_batches.py:232` | 未命中同模块直接/具名 helper render |
| `/scheduler/batches/<batch_id>/generate-ops` | `scheduler.generate_ops` | `web/routes/domains/scheduler/scheduler_batches.py:401` | 未命中同模块直接/具名 helper render |
| `/scheduler/batches/bulk/copy` | `scheduler.bulk_copy_batches` | `web/routes/domains/scheduler/scheduler_batches.py:334` | 未命中同模块直接/具名 helper render |
| `/scheduler/batches/bulk/delete` | `scheduler.bulk_delete_batches` | `web/routes/domains/scheduler/scheduler_batches.py:250` | 未命中同模块直接/具名 helper render |
| `/scheduler/batches/bulk/update` | `scheduler.bulk_update_batches` | `web/routes/domains/scheduler/scheduler_batches.py:368` | 未命中同模块直接/具名 helper render |
| `/scheduler/batches/create` | `scheduler.create_batch` | `web/routes/domains/scheduler/scheduler_batches.py:189` | 未命中同模块直接/具名 helper render |
| `/scheduler/calendar/upsert` | `scheduler.calendar_upsert` | `web/routes/domains/scheduler/scheduler_calendar_pages.py:42` | 未命中同模块直接/具名 helper render |
| `/scheduler/config` | `scheduler.update_config` | `web/routes/domains/scheduler/scheduler_config.py:470` | 未命中同模块直接/具名 helper render |
| `/scheduler/config/default` | `scheduler.restore_config_default` | `web/routes/domains/scheduler/scheduler_config.py:480` | 未命中同模块直接/具名 helper render |
| `/scheduler/config/preset/apply` | `scheduler.preset_apply` | `web/routes/domains/scheduler/scheduler_config.py:361` | 未命中同模块直接/具名 helper render |
| `/scheduler/config/preset/delete` | `scheduler.preset_delete` | `web/routes/domains/scheduler/scheduler_config.py:412` | 未命中同模块直接/具名 helper render |
| `/scheduler/config/preset/save` | `scheduler.preset_save` | `web/routes/domains/scheduler/scheduler_config.py:385` | 未命中同模块直接/具名 helper render |
| `/scheduler/excel/batches/confirm` | `scheduler.excel_batches_confirm` | `web/routes/domains/scheduler/scheduler_excel_batches.py:238` | `scheduler/excel_import_batches.html` @ 98 |
| `/scheduler/excel/batches/preview` | `scheduler.excel_batches_preview` | `web/routes/domains/scheduler/scheduler_excel_batches.py:155` | `scheduler/excel_import_batches.html` @ 98 |
| `/scheduler/excel/calendar/confirm` | `scheduler.excel_calendar_confirm` | `web/routes/domains/scheduler/scheduler_excel_calendar.py:220` | `scheduler/excel_import_calendar.html` @ 86 |
| `/scheduler/excel/calendar/preview` | `scheduler.excel_calendar_preview` | `web/routes/domains/scheduler/scheduler_excel_calendar.py:159` | `scheduler/excel_import_calendar.html` @ 86 |
| `/scheduler/gantt/adjustments/create-draft` | `scheduler.create_gantt_adjustment_draft` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:14` | 未命中同模块直接/具名 helper render |
| `/scheduler/gantt/adjustments/discard-draft` | `scheduler.discard_gantt_adjustment_draft` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:76` | 未命中同模块直接/具名 helper render |
| `/scheduler/gantt/adjustments/publish-scenario` | `scheduler.publish_gantt_adjustment_scenario` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:134` | 未命中同模块直接/具名 helper render |
| `/scheduler/gantt/adjustments/record-resource-change` | `scheduler.record_gantt_adjustment_resource_change` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:55` | 未命中同模块直接/具名 helper render |
| `/scheduler/gantt/adjustments/record-time-change` | `scheduler.record_gantt_adjustment_time_change` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:33` | 未命中同模块直接/具名 helper render |
| `/scheduler/gantt/adjustments/save-scenario` | `scheduler.save_gantt_adjustment_scenario` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:109` | 未命中同模块直接/具名 helper render |
| `/scheduler/gantt/adjustments/validate-simulate` | `scheduler.validate_gantt_adjustment` | `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:92` | 未命中同模块直接/具名 helper render |
| `/scheduler/ops/<int:op_id>/update` | `scheduler.update_op` | `web/routes/domains/scheduler/scheduler_ops.py:37` | 未命中同模块直接/具名 helper render |
| `/scheduler/ops/update-token/<token>` | `scheduler.update_op_by_token` | `web/routes/domains/scheduler/scheduler_ops.py:44` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/<int:op_id>/actual` | `scheduler.resource_dispatch_execution_actual` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:128` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/<int:op_id>/finish` | `scheduler.resource_dispatch_execution_finish` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:222` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/<int:op_id>/pause` | `scheduler.resource_dispatch_execution_pause` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:227` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/<int:op_id>/report-exception` | `scheduler.resource_dispatch_execution_report_exception` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:237` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/<int:op_id>/resume` | `scheduler.resource_dispatch_execution_resume` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:232` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/<int:op_id>/start` | `scheduler.resource_dispatch_execution_start` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:217` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/import` | `scheduler.resource_dispatch_actual_import` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:280` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/import/confirm` | `scheduler.resource_dispatch_actual_import_confirm` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:293` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/import/preview` | `scheduler.resource_dispatch_actual_import_preview` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:267` | 未命中同模块直接/具名 helper render |
| `/scheduler/resource-dispatch/execution/tasks/<task_key>/actual` | `scheduler.resource_dispatch_execution_actual_by_task` | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:144` | 未命中同模块直接/具名 helper render |
| `/scheduler/run` | `scheduler.run_schedule` | `web/routes/domains/scheduler/scheduler_run.py:38` | 未命中同模块直接/具名 helper render |
| `/scheduler/simulate` | `scheduler.simulate_schedule` | `web/routes/domains/scheduler/scheduler_week_plan.py:433` | 未命中同模块直接/具名 helper render |
| `/system/backup/cleanup` | `system.backup_cleanup` | `web/routes/system_backup.py:299` | 未命中同模块直接/具名 helper render |
| `/system/backup/create` | `system.backup_create` | `web/routes/system_backup.py:111` | 未命中同模块直接/具名 helper render |
| `/system/backup/delete` | `system.backup_delete` | `web/routes/system_backup.py:188` | 未命中同模块直接/具名 helper render |
| `/system/backup/delete-batch` | `system.backup_delete_batch` | `web/routes/system_backup.py:219` | 未命中同模块直接/具名 helper render |
| `/system/backup/restore` | `system.backup_restore` | `web/routes/system_backup.py:331` | 未命中同模块直接/具名 helper render |
| `/system/backup/settings` | `system.backup_settings` | `web/routes/system_backup.py:163` | 未命中同模块直接/具名 helper render |
| `/system/logs/delete` | `system.logs_delete` | `web/routes/system_logs.py:105` | 未命中同模块直接/具名 helper render |
| `/system/logs/delete-batch` | `system.logs_delete_batch` | `web/routes/system_logs.py:124` | 未命中同模块直接/具名 helper render |
| `/system/logs/settings` | `system.logs_settings` | `web/routes/system_logs.py:90` | 未命中同模块直接/具名 helper render |
| `/system/plugins/toggle` | `system.plugin_toggle` | `web/routes/system_plugins.py:14` | 未命中同模块直接/具名 helper render |
| `/system/runtime/shutdown` | `system.runtime_shutdown` | `web/routes/system_health.py:30` | 未命中同模块直接/具名 helper render |

## 4. 参数分组与不得丢失的语义

| 组 | 必须逐项解释的字段 | 等价/拒绝规则 |
| --- | --- | --- |
| P 计划身份 | version、plan_role、scenario_id、plan_context_token；已有请求身份和有效身份 | 使用现有只读身份解析与永久 plan_ref；不默认 adopted/latest。旧 token 失效明确提示，不改选其他身份 |
| D 时间 | start_date/end_date、date_from/date_to、week_start/offset、day、month、start_dt | 各自是计划交集/事件发生/周历/单次开始等不同语义；按旧规则解析后只转可等价字段。日期/时分/跨夜不能丢 |
| R 业务范围 | batch_id、resource_type/resource_id、scope_type/scope_id、team_axis/team_id、back_to | 仅稳定 ref 精确承接；不得用名称搜索代替对象范围、把班组当显示组、把返回链接当业务对象；返回目标同本机允许路径 |
| U 旧查看态 | view=machine/operator、gantt_zoom/vm/color/batch/resource/overdue/external/deps/hcc，group_by | 先与新 view 命名分离；纯旧偏好在 N 列明，不能改排程或 silently 丢掉资源/批次范围 |
| L 列表 | q/search/status/only_ready/category/team_id/page/per_page/limit 及旧函数实际认可字段 | 搜索、分页、状态、齐套分开；不同枚举或无法同域过滤时 N。不能随便让 page=99 变成 page=1 |
| M 主数据 | path 中真实 part_no/machine_id/operator_id/supplier_id/op_type_id/batch_id；详情节点 | 用唯一活跃实体映射；缺 ref/对象不存在不补建、不跳列表。隐藏字段保留 |
| X 导入/配置 | mode、strict_mode、auto_generate_ops、preset_name/custom、单次/全局运行参数 | 有旧控件不代表 query 会执行命令。GET 只定位/说明，绝不触发导入、重建、预设应用或恢复默认 |
| S 系统 | file/level/q、start_time/end_time/log_level、module/action/limit、filename、详情/来源 | 操作日志与文件日志分开；system 当前不接 initialContext，须增加承接或 N。不得自动删除/恢复/清理/启停 |
| H 帮助 | src/page 及文档锚点 | 保留现有规范化、允许返回地址、原文下载、不可读错误与 noscript；不加外链依赖 |

- 本表 P/D/R 等是需要审查的语义组，不是所有 route 都接受组内每个字段；实际接受集合以该 route 现行 parser 为准，未知/重复字段明确拒绝，不用宽泛 allowlist 吞掉差异。
- `plan_context_token` 当前是进程内 12 小时 URL 脱敏引用，并非权限。成功转换后以永久 ref 支撑新入口刷新/同版本重启；尚未转换的旧 token 在重启后失效须诚实显示，不能伪造永久有效或回退 latest。
- API 的非正式/历史拒绝边界仍在新接口保留。既有旧下载允许某些历史/候选读，不构成放宽新报工/执行分析 guard 的理由。

## 5. 明确不能用的实现

- 不移除整个 scheduler/reports/system 等 blueprint；不按 `/scheduler/*`、`/process/*` 或 `/system/*` 一刀切。
- 不做全局 render_template 猴补丁，不根据 TESTING、环境变量、测试路径或特殊 query 允许旧 HTML 回来；不把所有旧 POST 改成成功提示或空响应。
- 不仅换首页：新导航、原书签、错误返回、POST 预览/失败回执、打印、手册、无 JS/资源缺失、恢复维护态都在终验范围内。

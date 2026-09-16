---
doc_type: issue-report
issue: 2026-09-16-full-gate-only-tests-red-after-batch
status: resolved
resolved: 2026-09-16
severity: P2
created: 2026-09-16
source: 2026-09-16 提交批次收尾时，拆分高复杂度函数的子代理按 grep 扩跑相关测试顺带发现
tags: [gate, full-gate, frontend-copy, manual, utilization, report]
---

# 日常门禁之外的用例随本批转红（初报 10 个，累计 14 个）

## 现象

下列用例不在 `scripts/run_daily_quality_gate.py` 的必跑组里，日常门禁与 pre-push 不会执行它们，
只有全量门禁 `scripts/run_quality_gate.py` 会跑。基线 `7034b873` 的只读快照上 9 个非浏览器用例
全部通过；当前 HEAD 上全部失败，属于本批引入。

| 用例 | HEAD 上的失败点 | 初步归类 |
|---|---|---|
| `tests/web_pages/test_frontend_ui_language_polish.py::test_scheduler_config_and_batch_hints_are_user_facing_chinese` | 断言的旧文案字符串只剩测试文件里有 | 文案整改后的过期断言 |
| `tests/web_pages/test_frontend_ui_language_polish.py::test_process_excel_current_tables_render_chinese_display_fields` | 断言 `window.APSProcessContract.sourceLabel(row.source)` 已不在前端脚本 | 前端重写后的过期断言 |
| `tests/web_pages/test_frontend_ui_language_polish.py::test_frontend_scripts_keep_internal_details_out_of_user_messages` | 浏览器探针合同断言，读取前端脚本 | 待查（可能受 Chromium 运行时影响） |
| `tests/web_pages/test_frontend_ui_language_polish.py::test_reports_and_v2_batch_templates_match_public_manual_contracts` | 断言 `("utilization_percent", "计划利用率（%）")` 与 `report_catalog.py` docstring | 利用率新口径 / 手册整改后的过期断言 |
| `tests/web_pages/test_page_manual_registry.py::test_page_manual_registry_contract` | 页面手册登记合同 | 手册整改后的过期断言 |
| `tests/web_pages/test_page_manual_registry.py::test_user_corrected_manual_semantic_contracts` | 断言手册里的 `计划甘特现在是` 等语句 | 手册整改后的过期断言 |
| `tests/gantt/test_gantt_load_strip_js_contract.py::test_top5_truncation_with_more_notice_and_order_preserved` | 甘特负荷条 JS 合同 | 待查（疑为文案整改） |
| `tests/web_pages/test_reports_export_version_default_latest.py::test_reports_export_version_default_latest` | `设备负荷小时` 得 0，期望 4.0 | 利用率新口径 `available_occupancy_v1`：该列现在是班表内占用；需先确认 0 是口径结果还是夹具缺班表 |
| `tests/workbench/test_final_execution_reports.py::test_full_main_reports_all_download_bytes_scope_sql_and_real_restart` | `sheets["设备负荷"][1][2:] != (132, 66, 8, 1650)` | 同上，设备负荷表列语义随口径变化 |
| `tests/app_runtime/test_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser` | 真机浏览器几何 smoke | 未在基线复跑（需 Chromium 运行时）；先排除 `/tmp` Chromium109 被清理的运行时原因 |

## 为什么现在才发现

- 用户明令不跑全量门禁（耗时数小时），本批只以日常门禁为准；这些文件不在任何必跑组里。
- 日常门禁的并行车道转绿后，串行车道和 focused 步骤才第一次执行，同样只覆盖必跑组。

## 建议处理

1. 文案 / 手册 / 前端重写类（6 个）：按 2026-09-16 用户裁决「以本轮整改为准，改旧测试」更新断言，
   更新前用 `python -m tools.scan_ui_copy` 确认新文案合规。
2. 利用率口径类（2 个）：先在夹具库上分别读出班表内占用、累计负荷、班表外占用三列，判断 0 是否合理；
   如是口径结果就改列索引与期望值，如夹具本就有班表则回到 `core/services/report/utilization.py` 查根因。
3. 浏览器类（2 个）：先按 `~/.cache/aps-chromium109-assessment` 恢复运行时再跑，排除运行时原因后再归因。
4. 处理完成后考虑把 `test_frontend_ui_language_polish.py`、`test_page_manual_registry.py` 登进对应必跑组，
   避免文案整改再次只在全量门禁里暴露。

## 处理（2026-09-16，用户裁决“先修这 10 个，再开 PR”）

实跑发现同一文件里还有 3 个同因失败（`test_form_run_option_checkbox_layout_contract.py` 的三个 strict 开关用例，
基线 5 passed、HEAD 4 failed），一并处理，共 13 个用例、8 个测试文件：

- 文案 / 手册 / 前端重写类：`test_frontend_ui_language_polish.py`（预检规则、批次详情刷新、工艺来源标签移到
  ProcessDetail、缩放档位收进页面说明、报表列名）、`test_page_manual_registry.py`（4 条总说明书语义片段改为
  手册现行措辞；“系统不会自动跳过这些批次继续排其它批次”是两个合同都要求的原句，改为补回手册两处齐套说明）、
  `test_gantt_load_strip_js_contract.py`（负荷页说明改为“占用率 = 班表内已占时间 ÷ 可用时间”）、
  `test_form_run_option_checkbox_layout_contract.py`（批次详情不再有逐批 strict 勾选框、文件导入直接确认、
  新增零件提示）、`ui_geometry_contract_data.py`（批次导入提示、批次详情勾选框数 0）。
- 利用率口径类：`test_reports_export_version_default_latest.py` 改为断言班表内 + 班表外两列之和（v7 排在默认休息的
  周六，班表内为 0）；`reports_review_browser_oracle.py` 的设备/人员负荷行按 available_occupancy_v1 实际值重写，
  并在注释里写清 66 条任务同窗叠放、设备扣 0.5 小时停机的推导。
- 浏览器类：几何 smoke 在真 Chrome 上复跑，失败点是过期文案与已移除的勾选框，不是运行时问题。
- 顺带修正：导出表头“计算口径版本”含词表禁词“口径”（导出模块不在扫描器范围内所以此前没被扫到），改为
  “计算方式版本”；手册 9.2 的设备/人员负荷列表仍写旧口径列名，按新导出列重写。

验证：8 个测试文件 71 passed；`test_final_execution_reports` 与浏览器几何 smoke 各 1 passed；文案扫描器 0 命中；全仓 ruff 通过。

### 补记：pyright 门禁复查时再发现 1 个文件（6 个用例）

`tests/algorithm/test_sgs_graph_failure_bookkeeping_contract.py` 的 6 个用例在 HEAD 上全部报
`AttributeError: core.algorithms.greedy.dispatch.sgs has no attribute '_schedule_op'`。根因是本批
0350742b「SGS 解码提速」把 `_schedule_op` 移到 `batch_order.py`，由 `sgs_dispatch_step.py` 再导入并在
派工时从自己的模块全局读取；测试仍打桩旧模块名 `sgs._schedule_op`。基线 7034b873 上 6 passed，属本批引入。
处理：打桩目标改到 `sgs_dispatch_step._schedule_op`（与运行时读取点一致），并在测试里注明原因；
产品代码不动。累计 14 个用例、9 个测试文件。验证：该文件 6 passed。

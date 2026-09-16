---
doc_type: issue-report
issue: 2026-09-16-full-gate-only-tests-red-after-batch
status: open
severity: P2
created: 2026-09-16
source: 2026-09-16 提交批次收尾时，拆分高复杂度函数的子代理按 grep 扩跑相关测试顺带发现
tags: [gate, full-gate, frontend-copy, manual, utilization, report]
---

# 日常门禁之外的 10 个用例随本批转红

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

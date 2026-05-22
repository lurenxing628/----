---
doc_type: feature-acceptance
feature: 2026-05-23-scenario-preview-secondary-outputs
status: accepted
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-scenario-preview-secondary-outputs
---

# scenario-preview-secondary-outputs acceptance

## 验收结论

已完成。

周计划、资源排班和报表现在都支持按 `scenario_id` 显式预览已保存的 Scenario 模拟方案。不带 `scenario_id` 时仍然读取正式版本或原有候选方案口径。

## 已落地范围

- 周计划页面、查询表单、导出 URL、导出日志和导出文件名都保留 Scenario 身份。
- 资源排班页面、data 接口、导出接口、Excel 查询摘要和导出文件名都保留 Scenario 身份。
- 报表页面的超期清单、资源负荷与利用率、停机影响统计都按 Scenario 行计算。
- 报表导出在 Scenario 预览态明确拒绝，提示先正式采用生成新版本后再导出。
- Scheduler 主导航和报表导航在 Scenario 预览态保留 `version / plan_role / scenario_id`，不会一跳页就掉回正式计划。
- 坏 `scenario_id` 会报错，不会自动清掉编号后展示正式计划。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scenario_preview_secondary_outputs.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scenario_preview_secondary_outputs.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_reports_page_version_default_latest.py tests/regression_reports_export_version_default_latest.py tests/regression_reports_layout_contract.py tests/regression_week_plan_filename_uses_normalized_version.py tests/regression_gantt_draft_save_and_preview.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_frontend_ui_language_polish.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_known_oversize_entries_still_exceed_limit`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/fast_static_precheck.py`
- `git diff --check`

## 未做

- 报表预览态导出 Excel 暂不开放。原因是模拟方案不是正式版本，Excel 离开系统后容易被误当正式计划。
- 不新增拖动保存入口，不写 `Schedule`、`ScheduleHistory`、`ScheduleVersionSeq` 或 `ScheduleCandidate*`。

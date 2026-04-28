---
doc_type: feature-acceptance
feature: 2026-04-28-batches-page-viewmodel
status: accepted
roadmap: p1-scheduler-debt-cleanup
roadmap_item: batches-page-viewmodel
accepted_at: 2026-04-28
---

# batches_page() viewmodel 验收

## 1. 验收结论

PR-8 已完成。`/scheduler/` 批次首页的页面数据整理已经从 `batches_page()` route 搬到 `web/viewmodels/scheduler_batches_page.py`；route 现在只负责读请求、取服务、分页、保留原有最近历史读取失败日志边界、调用 viewmodel 并渲染页面。

本轮没有改 `/scheduler/run`、批次管理页、Excel 批次页、配置保存链路、页面说明 registry、route wrapper 或共享 summary 展示规则。执行中复审发现 `?status=` 已表示“全部状态”，但状态下拉框没有“全部”选项；本轮只补齐这个已有页面合同的模板选项，没有新增业务判断、fallback、兜底、静默吞错、新 reason 或新 details。

## 2. 合同核对

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 默认没有 `status` 时只看待排批次 | 通过 | `tests/test_scheduler_batches_page_viewmodel.py::test_batches_page_defaults_to_pending_status_and_renders_pending_rows` |
| 显式 `?status=` 表示全部状态 | 通过 | `test_batches_page_empty_status_lists_all_statuses_without_run_controls` |
| `status=scheduled` 不显示执行排产控件 | 通过 | `test_batches_page_scheduled_status_hides_run_controls` |
| `only_ready` 三态过滤 | 通过 | `test_batches_page_only_ready_filters_visible_rows` |
| 批次行中文字段 | 通过 | `test_batch_rows_filter_ready_and_add_public_labels` |
| 配置降级只显示公开中文提示 | 通过 | `test_batches_page_renders_config_degraded_public_messages` |
| 没有最近历史时显示空历史文案 | 通过 | `test_batches_page_without_latest_history_renders_empty_history_message` |
| 最近 summary 解析失败仍显示历史版本和公开提示 | 通过 | `test_batches_page_latest_summary_parse_failed_renders_history_and_warning` |
| 最近算法快照显示目标中文名和自动回写资源状态 | 通过 | `test_batches_page_latest_algo_config_snapshot_renders_public_snapshot_state` |
| route 使用页面 viewmodel 装配页面状态 | 通过 | `test_scheduler_batches_route_uses_page_view_model` |

## 3. 债务口径

- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已移除 `complexity:web-routes-domains-scheduler-scheduler_batches-batches_page` 登记。
- `scripts/sync_debt_ledger.py check` 显示 `complexity_count=37`，说明 P1-19 对应的复杂度事实源已关闭。
- `tools/check_full_test_debt.py` 显示 `active_xfail_count=5`、`collected_count=766`、`unexpected_failure_count=0`。
- 本轮只关闭 P1-19 的复杂度登记并补页面合同测试，不声明 full-test-debt 减少。

## 4. 复审结论

已调用多路只读复审，覆盖页面合同、无新增兜底、共享层和邻近模块影响、测试口径、CodeStable 回填和债务口径。

复审发现并已处理的问题：

- 状态下拉框缺少“全部”选项，已在 `templates/scheduler/batches.html` 和 `web_new_test/templates/scheduler/batches.html` 补齐。
- 空 status 测试原本可能被齐套下拉框误伤通过，已改为只检查状态下拉框。
- 非 pending 状态控件隐藏覆盖偏窄，已补 `status=scheduled` 页面测试。
- 原源码字符串测试偏脆，已改成运行时 patch route 构建器，确认 route 实际调用 viewmodel。
- source-map、roadmap、items 和 checklist 的状态已按最终结果回填。

## 5. 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_scheduler_batches_page_viewmodel.py` | 11 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_batches_degraded_visibility.py tests/test_schedule_summary_observability.py` | 18 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_system_history_route_contract.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_scheduler_config_route_contract.py tests/regression_sp05_followup_contracts.py` | 47 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_run_no_reschedulable_flash.py tests/regression_scheduler_route_enforce_ready_tristate.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py` | 18 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sp05_path_topology_contract.py tests/regression_page_manual_registry.py tests/regression_manual_entry_scope.py tests/regression_scheduler_excel_batches_helper_injection_contract.py tests/regression_scheduler_excel_batches_preview_baseline_precision.py` | 23 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold` | 3 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/routes/domains/scheduler/scheduler_batches.py web/viewmodels/scheduler_batches_page.py tests/test_scheduler_batches_page_viewmodel.py tests/regression_manual_entry_scope.py tests/regression_scheduler_batches_degraded_visibility.py` | passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright web/routes/domains/scheduler/scheduler_batches.py web/viewmodels/scheduler_batches_page.py tests/test_scheduler_batches_page_viewmodel.py` | 0 errors |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` | passed, active_xfail_count=5, collected_count=766 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check` | passed, complexity_count=37 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup` | 3 passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/features/2026-04-28-batches-page-viewmodel` | 2 passed |
| `git diff --check` | passed |

最终干净工作区门禁会在提交后再跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`。

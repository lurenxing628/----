---
doc_type: feature-acceptance
feature: 2026-04-28-freeze-window-disabled-contract
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-28
roadmap: p1-scheduler-debt-cleanup
roadmap_item: freeze-window-disabled-contract
---

# 冻结窗口状态合同验收补录

## 1. 验收结论

M2 已完成冻结窗口状态合同收口。本文件是补录验收记录，用来补齐 CodeStable feature 追踪链；真实代码实现来自提交 `8c23c94`，分析页展示修复来自提交 `da30364`，roadmap/items 回填来自提交 `d941a1b` 和本次文档补录。

本次完成：

- 冻结窗口普通 disabled 原因已拆开记录。
- 配置读取降级已归入 `degraded`，strict 模式继续 fail closed。
- Summary 不把 `config_degraded` 伪装成普通 disabled。
- 分析页已按冻结窗口状态展示，`enabled=no + freeze_state=degraded` 不再显示成普通未启用。
- P1-15 已从 `needs-recheck` 改为 `evidence-locked-by-M2`。

本次没有关闭：

- P1-14：`build_freeze_window_seed` 复杂度仍为 26/15。
- full-test-debt：active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 代码和页面改动

- `core/services/scheduler/run/freeze_window.py`：记录 `freeze_disabled_reason`，并把冻结窗口配置读取降级识别为 `degraded`。
- `core/services/scheduler/summary/schedule_summary_assembly.py`：只在真正 disabled 时透传安全原因字段。
- `templates/scheduler/analysis.html`：分析页按 `freeze_state` 展示冻结窗口状态，不用 `enabled` 遮住降级状态。

## 3. 测试改动

- `tests/regression_freeze_window_fail_closed_contract.py`：覆盖普通 disabled 原因、配置降级 relaxed/strict、上一版本行问题和 seed 边界。
- `tests/regression_schedule_summary_freeze_state_contract.py`：覆盖 summary 对 `freeze_disabled_reason` 和 degraded 的公开形状。
- `tests/regression_analysis_page_version_default_latest.py`：覆盖真实页面渲染中 `enabled=no + freeze_state=degraded` 必须显示已降级。

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_analysis_page_version_default_latest.py tests/regression_freeze_window_fail_closed_contract.py::test_freeze_window_enabled_config_degraded_relaxed_mode_surfaces_unapplied_status tests/regression_schedule_summary_freeze_state_contract.py::test_schedule_summary_config_degraded_does_not_expose_disabled_reason`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_batches_degraded_visibility.py tests/regression_scheduler_week_plan_summary_observability.py tests/regression_system_history_route_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tests/regression_analysis_page_version_default_latest.py`
- `git diff --check`

最终提交前还需在干净工作区复跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`。

## 5. CodeStable 回填

- `p1-scheduler-debt-cleanup-items.yaml` 已指向本 feature 目录。
- `p1-debt-source-map.md` 已同步 P1-15 结论，并保持 P1-14 open。
- `p1-scheduler-debt-cleanup-roadmap.md` 已在 M2/PR-2、M3/PR-3 头部和变更记录写入本次 review finding 修复结果。

## 6. 后续承接

M3 只能承接停机区间和资源池事实源。M2 的冻结窗口 proof、页面展示 proof 和 CodeStable 承接 proof 不能拿来替代 M3 的停机/资源池证明。

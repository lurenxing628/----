---
doc_type: decision
category: architecture
date: 2026-09-16
slug: capacity-kernel-package
status: active
area: shared-services
tags: [architecture, capacity, calendar, utilization, import-cycle, python38]
---

## 背景与授权

工作台手册整改的 `wbfix-utilization` 条目要求「统一工作台、报表与导出的资源可用
时长和占用率计算口径」。实现时让 `core/services/report` 直接 import
`core/services/workbench` 的日历与占用率模块，共 8 条边：

- `report/utilization_calendars.py` → `plan_calendar`、`plan_calendar_engine`、
  `plan_calendar_io`、`plan_calendar_windows`
- `report/utilization.py` → `plan_calendar_intervals`、`plan_calendar_windows`、
  `resource_utilization_metrics`
- `report/report_engine.py` → `resource_utilization_metrics`（取 `METRIC_VERSION`）

而 `core/services/workbench` 早已在 import `core/services/report`
（`report_catalog`、`report_facts`、`report_exports`、`calibration_export`、
`review_values`），于是形成包级循环。`tests/workbench/test_fe04_shared_service_dependency_contract.py`
与 `tests/workbench/test_round1_execution_dependency_contract.py` 对
`core/services/{process,scheduler,workbench}` 的包级环是零容忍的，没有白名单，
两个合同因此失败。核对过基线 `7034b873`：改动前 `core/services/report` 对
`core/services/workbench` 的 import 数为 0，这条环是本轮新引入的。

用户在给出三个选项后裁决：共享内核下沉到中立包。

## 决定

新建 `core/services/capacity/`，作为工作台投影、报表和导出共用的资源产能内核，
位置在两个包之下，谁都不反向依赖谁：

- `plan_calendar_intervals.py`、`plan_calendar_io.py`、`plan_calendar_engine.py`、
  `plan_calendar_windows.py`、`resource_utilization_metrics.py` 由
  `core/services/workbench/` 整体移入，模块名不变，降低改动风险。
- 新增 `plan_calendar_issues.py`：原先放在 `plan_calendar_context.py` 的
  `_MESSAGES` 公开问题词汇表和 `issue()`。`plan_calendar_windows` 只需要它，
  但 `plan_occupancy`、`plan_occupancy_constraints` 还在用，所以
  `plan_calendar_context` 保留 `issue` 的再导出入口，调用方无需改动。
- 新增 `plan_calendar_limits.py`：`MAX_CALENDAR_DATES = 3660`、
  `MAX_POLICY_CELLS = 40000` 从 `plan_calendar.py` 移出，`plan_calendar` 再导出，
  既有的 `monkeypatch.setattr(plan_calendar, "MAX_POLICY_CELLS", 1)` 写法照旧有效。

方向约束：`core/services/capacity` 只能依赖 `core/infrastructure`、`core/models`、
`core/services/scheduler`（已确认 scheduler 不 import workbench）和
`data/repositories`，不得 import `core/services/workbench` 或
`core/services/report`。

## 为什么不选另外两条

- 「把 report 侧利用率模块整体并进 workbench」改动集中，但等于认下「利用率口径
  归 workbench 所有」，以后报表想独立演进会受限；共享定义放共享层才符合
  `wbfix-utilization` 本身「一个口径」的初衷。
- 「改合同、允许这条环」最省事，但零容忍的包级环红线是项目自己立的，开一次口子
  之后很难收回。

## 影响与验证

- 16 个文件的 import 路径由 `core.services.workbench.*` 改为
  `core.services.capacity.*`；`tools/test_registry_groups_workbench.py` 里
  `workbench_reports` 组的 target 范围把
  `core/services/workbench/resource_utilization_metrics.py` 换成
  `core/services/capacity/**/*.py`，保证内核变动仍能触发该组回归。
- `python -m tools.scan_import_cycles`：受合同约束的包级环为 0；仓库里只剩
  `['.', 'web/bootstrap', 'web/routes']` 和
  `['core/algorithms/greedy', 'core/algorithms/greedy/dispatch']` 两条既有环，
  都不在合同的 members 集合里。
- 定向回归：两个依赖合同 + `test_plan_occupancy`、`test_plan_calendar`、
  `test_plan_calendar_runtime_dates`、`test_resource_utilization_shared`、
  `tests/scheduler_analysis`、`tests/calendar_maintenance` 共 655 passed；
  `tests/workbench`、`tests/web_pages` 全量另行复跑。
- 本次不引入运行库依赖，仍面向 Win7 x64 / Python 3.8 / 单机离线。
- 按用户明令未跑全量质量门禁，不构成 clean-worktree proof。

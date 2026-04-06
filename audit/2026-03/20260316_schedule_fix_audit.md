# 排产修复审计摘要

- 时间：2026-03-16
- 证据：
  - `audit/2026-03/20260316_perf_profile_report.md`
  - `evidence/Benchmark/fjsp_benchmark_report.md`
  - `evidence/Phase7/smoke_phase7_report.md`
  - `evidence/Phase10/smoke_phase10_report.md`

## 已落地修复

1. 统一交期截止口径
- `core/algorithms/evaluation.py`
- `core/algorithms/dispatch_rules.py`
- `core/algorithms/ortools_bottleneck.py`
- `core/services/scheduler/schedule_summary.py`
- `core/services/report/calculations.py`
- 统一为 `due_exclusive = due_date + 1 day 00:00`，并使用 `finish >= due_exclusive` 判超期。

2. 新增 `min_weighted_tardiness`
- `core/algorithms/evaluation.py`
- `core/services/scheduler/config_service.py`
- `tests/run_synthetic_case.py`
- `templates/scheduler/*.html`
- `web_new_test/templates/scheduler/*.html`
- 现状：保留 `min_tardiness` 的旧语义，同时新增以 `weighted_tardiness_hours` 为主的 objective。

3. 扩展 `result_summary` 到 1.1
- 新增 `algo.comparison_metric`
- 新增 `algo.config_snapshot`
- 新增 `algo.best_score_schema`
- 新增 `summary_truncated/original_size_bytes`
- 分析页与 viewmodel 已兼容新旧 summary。

4. improve 搜索空间扩展
- `core/services/scheduler/schedule_optimizer.py`
- `core/services/scheduler/schedule_optimizer_steps.py`
- multi-start 已扩为 `dispatch_mode × strategy × dispatch_rule`（仅 `sgs` 展开 rule）。

5. 基于证据的低风险性能优化
- `core/services/scheduler/calendar_engine.py`：缓存 `DayPolicy.work_window()` 结果，降低重复解析日期成本。
- `core/algorithms/greedy/downtime.py`
- `core/algorithms/greedy/dispatch/sgs.py`：评分阶段加入轻量 gap-aware 起点估算。
- `core/algorithms/greedy/auto_assign.py`：按更优候选顺序遍历，并加入基于 `best_end` 的安全剪枝。

## profile 前后对比

对比口径：同一脚本 `audit/2026-03/20260316_perf_profile.py`，优化前后同命令重跑。

### smoke_phase7
- `dispatch_sgs` cum_s：`0.024269s -> 0.009774s`
- `calendar_add_working_hours` cum_s：`0.086434s -> 0.021385s`
- `calendar_adjust_to_working_time` cum_s：`0.088584s -> 0.021706s`

### smoke_phase10_sgs_auto_assign
- `dispatch_sgs` cum_s：`0.035252s -> 0.014917s`
- `calendar_add_working_hours` cum_s：`0.042044s -> 0.013898s`
- `auto_assign_internal_resources` cum_s：`0.028190s -> 0.016198s`

### synthetic_improve
- 墙钟耗时：`11.841s -> 11.568s`
- `dispatch_sgs` cum_s：`9.947622s -> 7.853086s`
- `calendar_add_working_hours` cum_s：`5.089441s -> 2.656964s`
- `calendar_adjust_to_working_time` cum_s：`4.656620s -> 2.370618s`

## 回归与冒烟

- 新增回归：
  - `tests/regression_due_exclusive_consistency.py`
  - `tests/regression_weighted_tardiness_objective.py`
  - `tests/regression_improve_dispatch_modes.py`
  - `tests/regression_schedule_summary_v11_contract.py`
  - `tests/regression_scheduler_objective_labels.py`
- 已通过：
  - `tests/smoke_phase7.py`
  - `tests/smoke_phase10_sgs_auto_assign.py`
  - `tests/run_synthetic_case.py --mode improve --objective min_weighted_tardiness ...`

## benchmark 基线

来自 `evidence/Benchmark/fjsp_benchmark_report.md`（standard）：

- `mk01`：最佳 `improve + B_balanced`，makespan `53.0000h`，gap `32.50%`
- `mk04`：最佳 `improve + B_balanced`，makespan `81.0000h`，gap `35.00%`
- `mk06`：最佳 `improve + B_balanced`，makespan `89.0000h`，gap `56.14%`
- `mk08`：最佳 `improve + B_balanced`，makespan `602.0000h`，gap `15.11%`
- `mk10`：最佳 `improve + B_balanced`，makespan `329.0000h`，gap `70.47%`

## 仍保留的边界

- FJSP benchmark 仍受 APS “单机绑定”建模限制，gap 只作参考，不应直接视为柔性 FJSP 的可比上界。
- `min_tardiness` 与 `min_weighted_tardiness` 并存是兼容策略，不代表 v1/v2 口径已经完全收敛。
- `result_summary` 已有 512KB 裁剪保护，但大规模实例下仍应优先关注 `improvement_trace` 和 `warnings` 的增长。

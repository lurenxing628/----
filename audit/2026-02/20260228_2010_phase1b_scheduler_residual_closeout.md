# Phase1b 收口留痕：Scheduler 残留高复杂度闭环

- 时间：2026-02-28 20:10
- 目标：对 scheduler 残留的高复杂度核心文件做“拆分 helper、保持行为不变”的降复杂度治理，并用回归脚本做护栏。

## 本批次影响范围（仅限 scheduler 残留清单）

- `core/services/scheduler/freeze_window.py`
- `core/services/scheduler/gantt_critical_chain.py`
- `core/services/scheduler/schedule_summary.py`
- `core/services/scheduler/schedule_persistence.py`
- `core/services/scheduler/resource_pool_builder.py`
- `core/services/scheduler/gantt_tasks.py`
- `core/services/scheduler/calendar_engine.py`
- `core/services/scheduler/operation_edit_service.py`

## 关键结果（以 evidence 为准）

- 复跑架构审计：`python .cursor/skills/aps-arch-audit/scripts/arch_audit.py`
- 最新报告：`evidence/ArchAudit/arch_audit_report.md`（生成时间：2026-02-28 19:47:31）
  - 圈复杂度超标（>15）：53 → 49
  - F 极高(41+)：9 → 5
  - E 很高(31-40)：5 → 3
  - 代表性降幅（本批次目标函数）：
    - `freeze_window.build_freeze_window_seed`：51(F) → 16(C)
    - `gantt_critical_chain.compute_critical_chain`：79(F) →（拆分后不再超标；关键 helper 16(C)）
    - `schedule_summary.build_result_summary`：62(F) →（拆分后不再超标；关键 helper 17(C)）
    - `schedule_persistence.persist_schedule`：41(F) →（拆分后不再超标）
    - `resource_pool_builder.build_resource_pool`：40(E) →（拆分后不再超标）
    - `gantt_tasks.build_tasks`：34(E) →（拆分后不再超标；关键 helper 16(C)）
    - `calendar_engine._policy_for_date`：22(D) →（拆分后不再超标）
    - `operation_edit_service.update_internal_operation`：22(D) →（拆分后不再超标）

## 回归门禁（通过）

- `python tests/regression_freeze_window_bounds.py` → OK
- `python tests/regression_seed_results_freeze_missing_resource.py` → OK
- `python tests/regression_schedule_summary_end_date_type_guard.py` → OK
- `python tests/regression_gantt_critical_chain_cache_thread_safe.py` → OK
- `python tests/regression_auto_assign_empty_resource_pool.py` → OK
- `python tests/smoke_phase6.py` → OK（会覆盖输出 `evidence/Phase6/smoke_phase6_report.md`）

## 备注（约束确认）

- 本批次未做接口签名变更；仅拆分私有 helper/整理逻辑结构。
- 未涉及 schema 变更；未触发开发文档同步。


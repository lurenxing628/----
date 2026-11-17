from __future__ import annotations

from typing import Any, Dict, List

from core.shared.degradation import DegradationCollector, degradation_events_to_dicts


def summary_degradation_state(
    *,
    invalid_due_count: int,
    invalid_due_batch_ids_sample: List[str],
) -> Dict[str, Any]:
    # 配置快照严格构建（build_schedule_config_snapshot），不会带降级事件进入摘要。
    collector = DegradationCollector()
    if invalid_due_count > 0:
        collector.add(
            code="invalid_due_date",
            scope="schedule.summary",
            field="due_date",
            message="存在交期数据异常，超期判断已忽略这些批次。",
            count=invalid_due_count,
            sample="、".join(invalid_due_batch_ids_sample[:5]) or None,
        )
    return {"events": degradation_events_to_dicts(collector.to_list()), "counters": collector.to_counters()}


def hard_constraint_names(*, freeze_applied: bool) -> List[str]:
    hard_constraints: List[str] = ["precedence", "calendar", "resource_machine_operator", "downtime_avoid"]
    if freeze_applied:
        hard_constraints.append("freeze_window")
    return hard_constraints

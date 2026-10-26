from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import YesNo
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.shared.degradation import DegradationCollector, degradation_events_to_dicts


def _add_counted_event(
    collector: DegradationCollector,
    *,
    count: int,
    code: str,
    scope: str,
    field: str,
    message: str,
    sample: Optional[str] = None,
) -> None:
    if count <= 0:
        return
    collector.add(code=code, scope=scope, field=field, message=message, count=count, sample=sample)


def _summary_degradation_state(
    *,
    invalid_due_count: int,
    invalid_due_batch_ids_sample: List[str],
    ortools_warmstart_failed_count: int,
) -> Dict[str, Any]:
    # 配置快照严格构建（build_schedule_config_snapshot），不会带降级事件进入摘要。
    collector = DegradationCollector()
    _add_counted_event(
        collector,
        count=invalid_due_count,
        code="invalid_due_date",
        scope="schedule.summary",
        field="due_date",
        message="存在交期数据异常，超期判断已忽略这些批次。",
        sample="、".join(invalid_due_batch_ids_sample[:5]) or None,
    )
    _add_counted_event(
        collector,
        count=ortools_warmstart_failed_count,
        code="ortools_warmstart_failed",
        scope="optimizer.warmstart",
        field="ortools_enabled",
        message="OR-Tools 预热失败，系统已改用普通计算方式继续排产。",
    )
    return {"events": degradation_events_to_dicts(collector.to_list()), "counters": collector.to_counters()}


def _compute_resource_pool_state(cfg: ScheduleConfigSnapshot, *, resource_pool_meta: Optional[Dict[str, Any]]) -> Tuple[bool, bool]:
    # 资源池建不起来时 build_resource_pool 直接抛错停止排产，摘要只记录启用与是否尝试构建。
    auto_assign_enabled = cfg.auto_assign_enabled == YesNo.YES.value
    meta = resource_pool_meta if isinstance(resource_pool_meta, dict) else {}
    return auto_assign_enabled, meta.get("resource_pool_attempted", False)


def _hard_constraints(*, freeze_applied: bool) -> List[str]:
    hard_constraints: List[str] = ["precedence", "calendar", "resource_machine_operator", "downtime_avoid"]
    if freeze_applied:
        hard_constraints.append("freeze_window")
    return hard_constraints

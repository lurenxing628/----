from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import YesNo
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.models.scheduler_degradation_messages import public_degradation_event_message
from core.shared.degradation import DegradationCollector, degradation_events_to_dicts


def _add_existing_degradation_events(collector: DegradationCollector, events: Tuple[Dict[str, Any], ...]) -> None:
    # 配置快照的降级事件由 DegradationCollector 产出并转成字典：code/scope/message 非空，
    # field 是配置键，count 至少为 1。
    for event in events:
        collector.add(
            code=event["code"],
            scope=event["scope"],
            field=event["field"],
            message=public_degradation_event_message(event["code"]),
            count=event["count"],
            sample=None,
        )


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


def _add_state_event(
    collector: DegradationCollector,
    *,
    enabled: bool,
    code: str,
    scope: str,
    field: str,
    message: Optional[str],
    default_message: str,
) -> None:
    if not enabled:
        return
    collector.add(code=code, scope=scope, field=field, message=message or default_message)


def _summary_degradation_state(
    *,
    cfg: ScheduleConfigSnapshot,
    invalid_due_count: int,
    invalid_due_batch_ids_sample: List[str],
    ortools_warmstart_failed_count: int,
) -> Dict[str, Any]:
    collector = DegradationCollector()
    _add_existing_degradation_events(collector, cfg.degradation_events)
    _add_state_event(
        collector,
        enabled=bool(cfg.degradation_events),
        code="config_fallback",
        scope="schedule.summary.config_snapshot",
        field="config_snapshot",
        message=None,
        default_message="配置中有填写不完整或不正确的设置，本次先按默认值生成摘要。",
    )
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

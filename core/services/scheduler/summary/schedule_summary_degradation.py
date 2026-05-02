from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import YesNo
from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.degradation_messages import (
    DOWNTIME_EXTEND_FAILED_MESSAGE,
    DOWNTIME_LOAD_FAILED_MESSAGE,
    RESOURCE_POOL_BUILD_FAILED_MESSAGE,
    public_degradation_event_message,
)

_LEGACY_MERGE_CONTEXT_CODES = {"template_missing", "external_group_missing"}


def _event_identity(event: Dict[str, Any]) -> Tuple[str, str, str, str, str, int]:
    return (
        str(event.get("code") or "").strip(),
        str(event.get("scope") or "").strip(),
        str(event.get("field") or "").strip(),
        str(event.get("message") or "").strip(),
        str(event.get("sample") or "").strip(),
        _event_count(event),
    )


def _dedupe_event_dicts(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        identity = _event_identity(event)
        if identity in seen:
            continue
        seen.add(identity)
        out.append(dict(event))
    return out


def _iter_build_outcome_values(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        return list(value)
    except Exception:
        return [value]


def _value_flag(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _builder_merge_context_state(value: Any) -> Tuple[bool, List[Dict[str, Any]]]:
    degraded = False
    merge_context_events: List[Dict[str, Any]] = []
    for item in _iter_build_outcome_values(value):
        degraded = degraded or bool(_value_flag(item, "merge_context_degraded"))
        raw_events = _value_flag(item, "merge_context_events")
        if not isinstance(raw_events, (list, tuple)):
            continue
        for raw_event in raw_events:
            if isinstance(raw_event, dict):
                merge_context_events.append(dict(raw_event))
    return bool(degraded), _dedupe_event_dicts(merge_context_events)


def _legacy_merge_context_events(event_dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        dict(event)
        for event in event_dicts
        if str(event.get("code") or "").strip() in _LEGACY_MERGE_CONTEXT_CODES
    ]


def _input_build_state(input_build_outcome: Optional[BuildOutcome[Any]]) -> Dict[str, Any]:
    if not isinstance(input_build_outcome, BuildOutcome):
        return {
            "degraded": False,
            "degradation_events": [],
            "degradation_counters": {},
            "empty_reason": None,
            "merge_context_degraded": False,
            "merge_context_events": [],
            "input_fallback": False,
        }

    event_dicts = degradation_events_to_dicts(input_build_outcome.events)
    builder_merge_context_degraded, builder_merge_context_events = _builder_merge_context_state(input_build_outcome.value)
    merge_context_events = (
        list(builder_merge_context_events)
        if builder_merge_context_degraded or builder_merge_context_events
        else _legacy_merge_context_events(event_dicts)
    )
    merge_context_degraded = bool(builder_merge_context_degraded or merge_context_events)
    merge_context_event_ids = {_event_identity(event) for event in merge_context_events}
    input_fallback_events = [
        event
        for event in event_dicts
        if _event_identity(event) not in merge_context_event_ids
    ]
    degradation_counters = dict(input_build_outcome.counters or {})
    return {
        "degraded": bool(input_build_outcome.has_events or merge_context_degraded),
        "degradation_events": event_dicts,
        "degradation_counters": degradation_counters,
        "empty_reason": input_build_outcome.empty_reason,
        "merge_context_degraded": merge_context_degraded,
        "merge_context_events": merge_context_events,
        "input_fallback": bool(input_fallback_events),
    }


def _meta_int(meta: Dict[str, Any], key: str) -> int:
    try:
        return max(0, int(meta.get(key) or 0))
    except Exception:
        return 0


def _meta_sample(meta: Dict[str, Any], key: str, *, limit: int = 5) -> List[str]:
    raw = meta.get(key)
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[str] = []
    for item in raw:
        try:
            text = str(item).strip()
        except Exception:
            continue
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _metric_int(metrics: Any, key: str) -> int:
    if metrics is None:
        return 0
    try:
        return max(0, int(getattr(metrics, key, 0) or 0))
    except Exception:
        return 0


def _metric_sample(metrics: Any, key: str, *, limit: int) -> List[str]:
    if metrics is None:
        return []
    raw = getattr(metrics, key, None)
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[str] = []
    for item in raw:
        try:
            text = str(item).strip()
        except Exception:
            continue
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _event_count(event: Dict[str, Any]) -> int:
    try:
        return max(1, int(event.get("count") or 1))
    except Exception:
        return 1


def _add_input_events(collector: DegradationCollector, input_state: Dict[str, Any]) -> None:
    for event in list(input_state.get("degradation_events") or []):
        if not isinstance(event, dict):
            continue
        code = _optional_text(event.get("code"))
        if code is None:
            continue
        collector.add(
            code=code,
            scope=_optional_text(event.get("scope")) or "schedule.input_contract",
            field=_optional_text(event.get("field")),
            message=public_degradation_event_message(code),
            count=_event_count(event),
            sample=None,
        )


def _add_existing_degradation_events(collector: DegradationCollector, raw_events: Any) -> None:
    for event in raw_events or ():
        if not isinstance(event, dict):
            continue
        code = _optional_text(event.get("code"))
        message = _optional_text(event.get("message"))
        if not code or not message:
            continue
        collector.add(
            code=code,
            scope=_optional_text(event.get("scope")) or "scheduler.config_snapshot",
            field=_optional_text(event.get("field")),
            message=public_degradation_event_message(code),
            count=_event_count(event),
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
    collector.add(code=code, scope=scope, field=field, message=message, count=int(count), sample=sample)


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
    collector.add(code=code, scope=scope, field=field, message=str(message or default_message))


def _summary_degradation_state(
    *,
    cfg: Any,
    input_state: Dict[str, Any],
    invalid_due_count: int,
    invalid_due_batch_ids_sample: List[str],
    legacy_external_days_defaulted_count: int,
    freeze_state: Dict[str, Any],
    downtime_state: Dict[str, Any],
    resource_pool_enabled: bool,
    resource_pool_degraded: bool,
    resource_pool_degradation_reason: Optional[str],
    ortools_warmstart_failed_count: int,
    merge_context_degraded: bool,
    warning_merge_status: Dict[str, Any],
) -> Dict[str, Any]:
    collector = DegradationCollector()
    _add_existing_degradation_events(collector, getattr(cfg, "degradation_events", None))
    _add_state_event(
        collector,
        enabled=bool(tuple(getattr(cfg, "degradation_events", ()) or ())),
        code="config_fallback",
        scope="schedule.summary.config_snapshot",
        field="config_snapshot",
        message=None,
        default_message="配置中有已按安全取值处理的设置，摘要已按处理后的配置生成。",
    )
    _add_input_events(collector, input_state)
    _add_state_event(
        collector,
        enabled=bool(input_state.get("input_fallback")),
        code="input_fallback",
        scope="schedule.summary.input_contract",
        field="input_contract",
        message=None,
        default_message="排产输入里有已按安全取值处理的数据，摘要已按处理后的数据生成。",
    )
    _add_counted_event(
        collector,
        count=int(invalid_due_count),
        code="invalid_due_date",
        scope="schedule.summary",
        field="due_date",
        message="存在交期数据异常，超期判断已忽略这些批次。",
        sample="、".join(invalid_due_batch_ids_sample[:5]) or None,
    )
    _add_counted_event(
        collector,
        count=int(legacy_external_days_defaulted_count),
        code="legacy_external_days_defaulted",
        scope="greedy.external",
        field="ext_days",
        message="部分外协周期缺失或不合法，本次先按 1 天计算。",
    )
    _add_counted_event(
        collector,
        count=int(ortools_warmstart_failed_count),
        code="ortools_warmstart_failed",
        scope="optimizer.warmstart",
        field="ortools_enabled",
        message="深度优化启动失败，系统已改用普通计算方式继续排产。",
    )
    _add_state_event(
        collector,
        enabled=str(freeze_state.get("freeze_state") or "").strip().lower() == "degraded",
        code="freeze_window_degraded",
        scope="schedule.summary.freeze_window",
        field="freeze_window",
        message=_optional_text(freeze_state.get("degradation_reason")),
        default_message="冻结窗口资料不完整，本次排产未使用冻结窗口。",
    )
    _add_state_event(
        collector,
        enabled=bool(downtime_state.get("downtime_degraded")),
        code="downtime_avoid_degraded",
        scope="schedule.summary.downtime_avoid",
        field="downtime_avoid",
        message=_optional_text(downtime_state.get("downtime_degradation_reason")),
        default_message="停机时间资料不完整，本次先按可用数据继续。",
    )
    _add_state_event(
        collector,
        enabled=bool(resource_pool_enabled and resource_pool_degraded),
        code="resource_pool_degraded",
        scope="schedule.summary.resource_pool",
        field="resource_pool",
        message=resource_pool_degradation_reason,
        default_message="资源池资料不完整，本次先按可用资源继续。",
    )
    _add_state_event(
        collector,
        enabled=bool(merge_context_degraded),
        code="merge_context_degraded",
        scope="schedule.summary.merge_context",
        field="warnings",
        message=None,
        default_message="组合并资料不完整，摘要已按可确认内容继续生成。",
    )
    _add_state_event(
        collector,
        enabled=bool(warning_merge_status.get("summary_merge_failed")),
        code="summary_merge_failed",
        scope="schedule.summary.warning_pipeline",
        field="warnings",
        message=None,
        default_message="排产提示没有完整整理，已保留能确认的提示。",
    )
    return {"events": degradation_events_to_dicts(collector.to_list()), "counters": collector.to_counters()}


def _partial_fail_reason(prefix: str, count: int, sample: List[str], suffix: str) -> str:
    sample_text = "、".join(sample)
    message = f"{prefix}（{count} 台"
    if sample_text:
        message += f"，如：{sample_text}"
    return message + f"），{suffix}"


def _downtime_reason(
    *,
    auto_assign_enabled: bool,
    downtime_extend_attempted: bool,
    load_failed: bool,
    downtime_load_error: Any,
    load_partial_fail_count: int,
    load_partial_fail_machines_sample: List[str],
    extend_failed: bool,
    downtime_extend_error: Any,
    extend_partial_fail_count: int,
    extend_partial_fail_machines_sample: List[str],
) -> Optional[str]:
    if load_partial_fail_count > 0:
        return _partial_fail_reason(
            "部分设备停机区间加载失败", load_partial_fail_count, load_partial_fail_machines_sample, "这些设备本次先不使用停机约束"
        )
    if load_failed:
        return DOWNTIME_LOAD_FAILED_MESSAGE
    if auto_assign_enabled and downtime_extend_attempted and extend_partial_fail_count > 0:
        return _partial_fail_reason(
            "部分候选设备停机区间扩展加载失败", extend_partial_fail_count, extend_partial_fail_machines_sample, "这些候选设备可能未覆盖停机约束"
        )
    if extend_failed:
        return DOWNTIME_EXTEND_FAILED_MESSAGE
    return None


def _compute_downtime_degradation(cfg: Any, *, downtime_meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    snapshot = ensure_schedule_config_snapshot(
        cfg,
        strict_mode=False,
        source="scheduler.summary.downtime_degradation",
    )
    auto_assign_enabled = str(snapshot.auto_assign_enabled).strip().lower() == YesNo.YES.value
    meta = downtime_meta if isinstance(downtime_meta, dict) else {}

    downtime_load_ok = True if "downtime_load_ok" not in meta else bool(meta.get("downtime_load_ok"))
    load_partial_fail_count = _meta_int(meta, "downtime_partial_fail_count")
    extend_partial_fail_count = _meta_int(meta, "downtime_extend_partial_fail_count")
    downtime_extend_attempted = bool(meta.get("downtime_extend_attempted") or False)
    extend_ok_raw = meta.get("downtime_extend_ok")
    downtime_extend_ok = True if extend_ok_raw is None else bool(extend_ok_raw)
    load_failed = bool(not downtime_load_ok)
    extend_failed = bool(auto_assign_enabled and downtime_extend_attempted and (not downtime_extend_ok))

    return {
        "auto_assign_enabled": bool(auto_assign_enabled),
        "downtime_load_ok": bool(downtime_load_ok),
        "downtime_degraded": bool(load_failed or extend_failed),
        "downtime_degradation_reason": _downtime_reason(
            auto_assign_enabled=bool(auto_assign_enabled),
            downtime_extend_attempted=bool(downtime_extend_attempted),
            load_failed=bool(load_failed),
            downtime_load_error=meta.get("downtime_load_error"),
            load_partial_fail_count=int(load_partial_fail_count),
            load_partial_fail_machines_sample=_meta_sample(meta, "downtime_partial_fail_machines_sample"),
            extend_failed=bool(extend_failed),
            downtime_extend_error=meta.get("downtime_extend_error"),
            extend_partial_fail_count=int(extend_partial_fail_count),
            extend_partial_fail_machines_sample=_meta_sample(meta, "downtime_extend_partial_fail_machines_sample"),
        ),
        "downtime_extend_attempted": bool(downtime_extend_attempted),
        "load_partial_fail_count": int(load_partial_fail_count),
        "load_partial_fail_machines_sample": _meta_sample(meta, "downtime_partial_fail_machines_sample"),
        "extend_partial_fail_count": int(extend_partial_fail_count),
        "extend_partial_fail_machines_sample": _meta_sample(meta, "downtime_extend_partial_fail_machines_sample"),
    }


def _compute_resource_pool_degradation(cfg: Any, *, resource_pool_meta: Optional[Dict[str, Any]]) -> Tuple[bool, bool, Optional[str], bool]:
    snapshot = ensure_schedule_config_snapshot(
        cfg,
        strict_mode=False,
        source="scheduler.summary.resource_pool_degradation",
    )
    auto_assign_enabled = str(snapshot.auto_assign_enabled).strip().lower() == YesNo.YES.value
    meta = resource_pool_meta if isinstance(resource_pool_meta, dict) else {}
    attempted = bool(meta.get("resource_pool_attempted") or False)
    build_ok_raw = meta.get("resource_pool_build_ok")
    build_ok = True if build_ok_raw is None else bool(build_ok_raw)
    degraded = bool(auto_assign_enabled and attempted and (not build_ok))
    reason = RESOURCE_POOL_BUILD_FAILED_MESSAGE if degraded else None
    return bool(auto_assign_enabled), bool(degraded), reason, bool(attempted)


def _hard_constraints(cfg: Any, *, downtime_degraded: bool, freeze_applied: bool) -> List[str]:
    hard_constraints: List[str] = ["precedence", "calendar", "resource_machine_operator"]
    if not downtime_degraded:
        hard_constraints.append("downtime_avoid")
    if bool(freeze_applied):
        hard_constraints.append("freeze_window")
    return hard_constraints

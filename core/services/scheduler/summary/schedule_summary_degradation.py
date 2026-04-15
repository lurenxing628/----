from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import YesNo
from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts

from ..number_utils import to_yes_no

_FREEZE_WINDOW_STATE_ACTIVE = "active"


def _cfg_yes_no_flag(cfg: Any, key: str, *, default: str = YesNo.NO.value) -> bool:
    from core.algorithms.greedy.config_adapter import cfg_get

    return to_yes_no(cfg_get(cfg, key, default), default=default) == YesNo.YES.value


def _input_build_state(input_build_outcome: Optional[BuildOutcome[Any]]) -> Dict[str, Any]:
    if isinstance(input_build_outcome, BuildOutcome):
        event_dicts = degradation_events_to_dicts(input_build_outcome.events)
        merge_context_events = [
            event
            for event in event_dicts
            if str(event.get("code") or "") in {"template_missing", "external_group_missing"}
        ]
        return {
            "degraded": bool(input_build_outcome.has_events),
            "degradation_events": event_dicts,
            "degradation_counters": dict(input_build_outcome.counters or {}),
            "empty_reason": input_build_outcome.empty_reason,
            "merge_context_degraded": bool(merge_context_events),
            "merge_context_events": merge_context_events,
        }
    return {
        "degraded": False,
        "degradation_events": [],
        "degradation_counters": {},
        "empty_reason": None,
        "merge_context_degraded": False,
        "merge_context_events": [],
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
            message=_optional_text(event.get("message")) or code,
            count=_event_count(event),
            sample=_optional_text(event.get("sample")),
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
) -> Dict[str, Any]:
    collector = DegradationCollector()
    _add_input_events(collector, input_state)
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
        message="历史外协周期缺失或不合法，已按 1.0 天兼容读取。",
    )
    _add_counted_event(
        collector,
        count=int(ortools_warmstart_failed_count),
        code="ortools_warmstart_failed",
        scope="optimizer.warmstart",
        field="ortools_enabled",
        message="OR-Tools 预热失败，已回退到常规求解路径。",
    )
    _add_state_event(
        collector,
        enabled=str(freeze_state.get("freeze_state") or "").strip().lower() == "degraded",
        code="freeze_window_degraded",
        scope="schedule.summary.freeze_window",
        field="freeze_window",
        message=_optional_text(freeze_state.get("degradation_reason")),
        default_message="冻结窗口约束已降级。",
    )
    _add_state_event(
        collector,
        enabled=bool(downtime_state.get("downtime_degraded")),
        code="downtime_avoid_degraded",
        scope="schedule.summary.downtime_avoid",
        field="downtime_avoid",
        message=_optional_text(downtime_state.get("downtime_degradation_reason")),
        default_message="停机避让约束已降级。",
    )
    _add_state_event(
        collector,
        enabled=bool(resource_pool_enabled and resource_pool_degraded),
        code="resource_pool_degraded",
        scope="schedule.summary.resource_pool",
        field="resource_pool",
        message=resource_pool_degradation_reason,
        default_message="自动分配资源池构建已降级。",
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
            "部分设备停机区间加载失败", load_partial_fail_count, load_partial_fail_machines_sample, "这些设备已降级为忽略停机约束"
        )
    if load_failed:
        return str(downtime_load_error or "停机区间加载失败")
    if auto_assign_enabled and downtime_extend_attempted and extend_partial_fail_count > 0:
        return _partial_fail_reason(
            "部分候选设备停机区间扩展加载失败", extend_partial_fail_count, extend_partial_fail_machines_sample, "这些候选设备可能未覆盖停机约束"
        )
    if extend_failed:
        return str(downtime_extend_error or "停机区间扩展加载失败")
    return None


def _compute_downtime_degradation(cfg: Any, *, downtime_meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    auto_assign_enabled = _cfg_yes_no_flag(cfg, "auto_assign_enabled")
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
    auto_assign_enabled = _cfg_yes_no_flag(cfg, "auto_assign_enabled")
    meta = resource_pool_meta if isinstance(resource_pool_meta, dict) else {}
    attempted = bool(meta.get("resource_pool_attempted") or False)
    build_ok_raw = meta.get("resource_pool_build_ok")
    build_ok = True if build_ok_raw is None else bool(build_ok_raw)
    degraded = bool(auto_assign_enabled and attempted and (not build_ok))
    reason = str(meta.get("resource_pool_build_error") or "自动分配资源池构建失败") if degraded else None
    return bool(auto_assign_enabled), bool(degraded), reason, bool(attempted)


def _hard_constraints(cfg: Any, *, downtime_degraded: bool, freeze_state: str) -> List[str]:
    hard_constraints: List[str] = ["precedence", "calendar", "resource_machine_operator"]
    if not downtime_degraded:
        hard_constraints.append("downtime_avoid")
    if str(freeze_state or "").strip().lower() == _FREEZE_WINDOW_STATE_ACTIVE:
        hard_constraints.append("freeze_window")
    return hard_constraints

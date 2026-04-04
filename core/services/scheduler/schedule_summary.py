from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import YesNo
from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts

from .number_utils import to_yes_no

_SUMMARY_SIZE_LIMIT_BYTES = 512 * 1024


def _serialize_end_date(end_date: Optional[Any]) -> Optional[str]:
    if end_date is None:
        return None
    if isinstance(end_date, str):
        s = end_date.strip()
        return s if s else None
    try:
        iso_fn = getattr(end_date, "isoformat", None)
        if callable(iso_fn):
            return str(iso_fn())
    except Exception:
        pass
    s = str(end_date).strip()
    return s if s else None


def _due_exclusive(due_date) -> datetime:
    if not due_date:
        return datetime.max
    return datetime(due_date.year, due_date.month, due_date.day) + timedelta(days=1)


def _config_snapshot_dict(cfg: Any) -> Dict[str, Any]:
    if cfg is None:
        return {}
    if isinstance(cfg, dict):
        return dict(cfg)

    try:
        to_dict = getattr(cfg, "to_dict", None)
        if callable(to_dict):
            obj = to_dict()
            if isinstance(obj, dict):
                return dict(obj)
    except Exception:
        pass

    keys = (
        "sort_strategy",
        "priority_weight",
        "due_weight",
        "ready_weight",
        "holiday_default_efficiency",
        "enforce_ready_default",
        "prefer_primary_skill",
        "dispatch_mode",
        "dispatch_rule",
        "auto_assign_enabled",
        "ortools_enabled",
        "ortools_time_limit_seconds",
        "algo_mode",
        "time_budget_seconds",
        "objective",
        "freeze_window_enabled",
        "freeze_window_days",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        try:
            if not hasattr(cfg, key):
                continue
            value = getattr(cfg, key)
        except Exception:
            continue
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
            continue
        out[key] = str(value)
    return out


def _cfg_value(cfg: Any, key: str, default: Any = None) -> Any:
    from core.algorithms.greedy.config_adapter import cfg_get

    return cfg_get(cfg, key, default)


def _warning_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, dict):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = list(value)
    else:
        try:
            raw_items = list(value)
        except Exception:
            raw_items = [value]

    out: List[str] = []
    for item in raw_items:
        try:
            text = str(item)
        except Exception:
            continue
        if text:
            out.append(text)
    return out


def _merge_warning_lists(primary: Any, extra: Any) -> List[str]:
    merged = _warning_list(primary)
    seen = set(merged)
    for text in _warning_list(extra):
        if text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _append_summary_warning(summary: Any, message: str) -> bool:
    if isinstance(summary, dict):
        warnings = _warning_list(summary.get("warnings"))
        warnings.append(message)
        summary["warnings"] = warnings
        return True

    warnings = getattr(summary, "warnings", None)
    if isinstance(warnings, list):
        warnings.append(message)
        return True

    normalized_warnings = _warning_list(warnings)
    normalized_warnings.append(message)
    try:
        summary.warnings = normalized_warnings
        return True
    except Exception:
        return False


def _counter_dict(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw)
        except Exception:
            continue
        if count != 0:
            out[str(key)] = int(count)
    return out


def _comparison_metric(objective_name: str) -> str:
    obj = str(objective_name or "min_overdue").strip().lower()
    if obj == "min_tardiness":
        return "total_tardiness_hours"
    if obj == "min_weighted_tardiness":
        return "weighted_tardiness_hours"
    if obj == "min_changeover":
        return "changeover_count"
    return "overdue_count"


def _best_score_schema(objective_name: str) -> List[Dict[str, Any]]:
    obj = str(objective_name or "min_overdue").strip().lower()
    parts: List[Tuple[str, str]]
    if obj == "min_tardiness":
        parts = [
            ("failed_ops", "失败工序数"),
            ("total_tardiness_hours", "总拖期小时"),
            ("overdue_count", "超期批次数"),
            ("makespan_hours", "总工期小时"),
            ("changeover_count", "换型次数"),
        ]
    elif obj == "min_weighted_tardiness":
        parts = [
            ("failed_ops", "失败工序数"),
            ("weighted_tardiness_hours", "加权拖期小时"),
            ("overdue_count", "超期批次数"),
            ("total_tardiness_hours", "总拖期小时"),
            ("makespan_hours", "总工期小时"),
            ("changeover_count", "换型次数"),
        ]
    elif obj == "min_changeover":
        parts = [
            ("failed_ops", "失败工序数"),
            ("changeover_count", "换型次数"),
            ("overdue_count", "超期批次数"),
            ("total_tardiness_hours", "总拖期小时"),
            ("makespan_hours", "总工期小时"),
        ]
    else:
        parts = [
            ("failed_ops", "失败工序数"),
            ("overdue_count", "超期批次数"),
            ("total_tardiness_hours", "总拖期小时"),
            ("makespan_hours", "总工期小时"),
            ("changeover_count", "换型次数"),
        ]
    return [{"index": int(idx), "key": key, "label": label} for idx, (key, label) in enumerate(parts)]


def _summary_size_bytes(obj: Dict[str, Any]) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _apply_summary_size_guard(result_summary_obj: Dict[str, Any]) -> Dict[str, Any]:
    original_size = _summary_size_bytes(result_summary_obj)
    if original_size <= _SUMMARY_SIZE_LIMIT_BYTES:
        return result_summary_obj

    algo = result_summary_obj.get("algo")
    algo_dict = algo if isinstance(algo, dict) else {}
    trace = algo_dict.get("improvement_trace")
    warnings = result_summary_obj.get("warnings")
    attempts = algo_dict.get("attempts")
    best_batch_order = algo_dict.get("best_batch_order")
    selected_batch_ids = result_summary_obj.get("selected_batch_ids")
    overdue_batches = result_summary_obj.get("overdue_batches")
    overdue_items = overdue_batches.get("items") if isinstance(overdue_batches, dict) else None

    def _trim_trace(limit: int) -> None:
        if isinstance(trace, list):
            algo_dict["improvement_trace"] = trace[:limit]

    def _trim_warnings(limit: int) -> None:
        if isinstance(warnings, list):
            result_summary_obj["warnings"] = warnings[:limit]

    def _trim_attempts(limit: int) -> None:
        if isinstance(attempts, list):
            algo_dict["attempts"] = attempts[:limit]

    def _trim_best_batch_order(limit: int) -> None:
        if isinstance(best_batch_order, list):
            algo_dict["best_batch_order"] = best_batch_order[:limit]

    def _trim_selected_batch_ids(limit: int) -> None:
        if isinstance(selected_batch_ids, list):
            result_summary_obj["selected_batch_ids"] = selected_batch_ids[:limit]

    def _trim_overdue_items(limit: int) -> None:
        if isinstance(overdue_batches, dict) and isinstance(overdue_items, list):
            overdue_batches["items"] = overdue_items[:limit]

    for trace_limit, warning_limit, attempt_limit, best_order_limit, selected_ids_limit, overdue_items_limit in (
        (80, 50, 12, None, None, None),
        (20, 20, 12, None, None, None),
        (0, 20, 12, None, None, None),
        (0, 10, 6, None, None, None),
        (0, 0, 6, 2000, 2000, 500),
        (0, 0, 6, 500, 1000, 200),
        (0, 0, 6, 100, 200, 50),
        (0, 0, 6, 0, 50, 20),
        (0, 0, 0, 0, 0, 0),
    ):
        _trim_trace(trace_limit)
        _trim_warnings(warning_limit)
        _trim_attempts(attempt_limit)
        if best_order_limit is not None:
            _trim_best_batch_order(best_order_limit)
        if selected_ids_limit is not None:
            _trim_selected_batch_ids(selected_ids_limit)
        if overdue_items_limit is not None:
            _trim_overdue_items(overdue_items_limit)
        result_summary_obj["summary_truncated"] = True
        result_summary_obj["original_size_bytes"] = int(original_size)
        if _summary_size_bytes(result_summary_obj) <= _SUMMARY_SIZE_LIMIT_BYTES:
            return result_summary_obj

    return result_summary_obj


def _finish_time_by_batch(results: List[Any]) -> Dict[str, datetime]:
    finish_by_batch: Dict[str, datetime] = {}
    for r in results:
        if not getattr(r, "end_time", None):
            continue
        bid = str(getattr(r, "batch_id", "") or "").strip()
        cur = finish_by_batch.get(bid)
        if (cur is None) or (r.end_time > cur):
            finish_by_batch[bid] = r.end_time
    return finish_by_batch


def _build_overdue_items(
    svc,
    *,
    batches: Dict[str, Any],
    finish_by_batch: Dict[str, datetime],
    summary: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    overdue_items: List[Dict[str, Any]] = []

    invalid_due_count = 0
    invalid_due_ids_sample: List[str] = []
    invalid_due_raw_sample: List[str] = []

    for bid, b in batches.items():
        due = svc._normalize_text(getattr(b, "due_date", None))
        if not due:
            continue
        try:
            due_date = datetime.strptime(due.replace("/", "-"), "%Y-%m-%d").date()
        except Exception:
            invalid_due_count += 1
            if len(invalid_due_ids_sample) < 10:
                invalid_due_ids_sample.append(str(bid))
            if len(invalid_due_raw_sample) < 5:
                invalid_due_raw_sample.append(f"{bid}={due!r}")
            continue

        finish = finish_by_batch.get(str(bid))
        if not finish:
            continue
        if finish >= _due_exclusive(due_date):
            overdue_items.append(
                {
                    "batch_id": bid,
                    "due_date": due,
                    "finish_time": svc._format_dt(finish),
                }
            )

    if invalid_due_count > 0:
        sample_ids = "，".join(invalid_due_ids_sample[:10])
        msg = f"存在 {invalid_due_count} 个批次 due_date 格式不合法，已忽略超期判断（示例批次：{sample_ids}）"
        warning_appended = _append_summary_warning(summary, msg)
        if svc.logger:
            try:
                raw_sample = "；".join(invalid_due_raw_sample[:5])
                detail = f"{msg}；示例原始 due_date：{raw_sample}"
                if not warning_appended:
                    detail += "；且 summary.warnings 追加失败"
                svc.logger.warning(detail)
            except Exception:
                pass

    return overdue_items, {
        "invalid_due_count": int(invalid_due_count),
        "invalid_due_batch_ids_sample": list(invalid_due_ids_sample),
        "invalid_due_raw_sample": list(invalid_due_raw_sample),
    }


def _compute_result_status(summary: Any, *, simulate: bool) -> str:
    if getattr(summary, "success", False):
        result_status = "success"
    elif int(getattr(summary, "scheduled_ops", 0) or 0) > 0:
        result_status = "partial"
    else:
        result_status = "failed"
    if simulate:
        result_status = "simulated"
    return result_status


def _frozen_batch_ids(operations: List[Any], *, frozen_op_ids: Set[int]) -> List[str]:
    return sorted(
        {
            str(op.batch_id or "")
            for op in operations
            if op and getattr(op, "id", None) and int(op.id) in frozen_op_ids and str(op.batch_id or "").strip()
        }
    )


def _extract_freeze_warnings(summary: Any) -> List[str]:
    all_warnings = _warning_list(summary if isinstance(summary, (list, tuple, str)) else getattr(summary, "warnings", None))
    freeze_warnings: List[str] = []
    for w in all_warnings:
        ws = str(w)
        if ws.startswith("【冻结窗口】"):
            freeze_warnings.append(ws)
    return freeze_warnings


def _freeze_meta_dict(
    cfg: Any,
    *,
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]],
    freeze_warnings: List[str],
) -> Dict[str, Any]:
    meta = freeze_meta if isinstance(freeze_meta, dict) else {}
    enabled = to_yes_no(_cfg_value(cfg, "freeze_window_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
    try:
        days = int(_cfg_value(cfg, "freeze_window_days", 0) or 0)
    except Exception:
        days = 0
    raw_state = str(meta.get("freeze_state") or "").strip().lower()
    degradation_codes = [
        str(code).strip()
        for code in list(meta.get("freeze_degradation_codes") or [])
        if str(code).strip()
    ]
    degraded = raw_state == "degraded" or bool(freeze_warnings) or bool(degradation_codes)
    applied = bool(meta.get("freeze_applied")) if "freeze_applied" in meta else bool(frozen_op_ids)
    if degraded:
        freeze_state = "degraded"
    elif enabled and days > 0 and applied:
        freeze_state = "active"
    else:
        freeze_state = "disabled"
    return {
        "enabled": bool(enabled),
        "days": int(days),
        "freeze_state": freeze_state,
        "freeze_applied": bool(applied),
        "freeze_degradation_codes": degradation_codes,
        "degradation_reason": meta.get("freeze_degradation_reason") or (freeze_warnings[0] if freeze_warnings else None),
    }


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

    for event in list(input_state.get("degradation_events") or []):
        if not isinstance(event, dict):
            continue
        code = str(event.get("code") or "").strip()
        if not code:
            continue
        scope = str(event.get("scope") or "schedule.input_contract").strip() or "schedule.input_contract"
        message = str(event.get("message") or code or "退化事件").strip() or "退化事件"
        field = event.get("field")
        sample = event.get("sample")
        try:
            count = max(1, int(event.get("count") or 1))
        except Exception:
            count = 1
        collector.add(
            code=code,
            scope=scope,
            field=(None if field is None else str(field)),
            message=message,
            count=count,
            sample=(None if sample is None else str(sample)),
        )

    if invalid_due_count > 0:
        collector.add(
            code="invalid_due_date",
            scope="schedule.summary",
            field="due_date",
            message="存在交期数据异常，超期判断已忽略这些批次。",
            count=int(invalid_due_count),
            sample="、".join(invalid_due_batch_ids_sample[:5]) or None,
        )

    if legacy_external_days_defaulted_count > 0:
        collector.add(
            code="legacy_external_days_defaulted",
            scope="greedy.external",
            field="ext_days",
            message="历史外协周期缺失或不合法，已按 1.0 天兼容读取。",
            count=int(legacy_external_days_defaulted_count),
        )

    if ortools_warmstart_failed_count > 0:
        collector.add(
            code="ortools_warmstart_failed",
            scope="optimizer.warmstart",
            field="ortools_enabled",
            message="OR-Tools 预热失败，已回退到常规求解路径。",
            count=int(ortools_warmstart_failed_count),
        )

    if str(freeze_state.get("freeze_state") or "").strip().lower() == "degraded":
        collector.add(
            code="freeze_window_degraded",
            scope="schedule.summary.freeze_window",
            field="freeze_window",
            message=str(freeze_state.get("degradation_reason") or "冻结窗口约束已降级。"),
        )

    if bool(downtime_state.get("downtime_degraded")):
        collector.add(
            code="downtime_avoid_degraded",
            scope="schedule.summary.downtime_avoid",
            field="downtime_avoid",
            message=str(downtime_state.get("downtime_degradation_reason") or "停机避让约束已降级。"),
        )

    if bool(resource_pool_enabled and resource_pool_degraded):
        collector.add(
            code="resource_pool_degraded",
            scope="schedule.summary.resource_pool",
            field="resource_pool",
            message=str(resource_pool_degradation_reason or "自动分配资源池构建已降级。"),
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
    auto_assign_enabled = (
        to_yes_no(_cfg_value(cfg, "auto_assign_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
    )
    meta = downtime_meta if isinstance(downtime_meta, dict) else {}

    downtime_load_ok = True if "downtime_load_ok" not in meta else bool(meta.get("downtime_load_ok"))
    downtime_load_error = meta.get("downtime_load_error")
    load_partial_fail_count = _meta_int(meta, "downtime_partial_fail_count")
    load_partial_fail_machines_sample = _meta_sample(meta, "downtime_partial_fail_machines_sample")

    downtime_extend_attempted = bool(meta.get("downtime_extend_attempted") or False)
    extend_ok_raw = meta.get("downtime_extend_ok")
    downtime_extend_ok = True if extend_ok_raw is None else bool(extend_ok_raw)
    downtime_extend_error = meta.get("downtime_extend_error")
    extend_partial_fail_count = _meta_int(meta, "downtime_extend_partial_fail_count")
    extend_partial_fail_machines_sample = _meta_sample(meta, "downtime_extend_partial_fail_machines_sample")

    load_failed = bool(not downtime_load_ok)
    extend_failed = bool(auto_assign_enabled and downtime_extend_attempted and (not downtime_extend_ok))
    downtime_degraded = load_failed or extend_failed
    downtime_degradation_reason = _downtime_reason(
        auto_assign_enabled=bool(auto_assign_enabled),
        downtime_extend_attempted=bool(downtime_extend_attempted),
        load_failed=bool(load_failed),
        downtime_load_error=downtime_load_error,
        load_partial_fail_count=int(load_partial_fail_count),
        load_partial_fail_machines_sample=list(load_partial_fail_machines_sample),
        extend_failed=bool(extend_failed),
        downtime_extend_error=downtime_extend_error,
        extend_partial_fail_count=int(extend_partial_fail_count),
        extend_partial_fail_machines_sample=list(extend_partial_fail_machines_sample),
    )

    return {
        "auto_assign_enabled": bool(auto_assign_enabled),
        "downtime_load_ok": bool(downtime_load_ok),
        "downtime_degraded": bool(downtime_degraded),
        "downtime_degradation_reason": downtime_degradation_reason,
        "downtime_extend_attempted": bool(downtime_extend_attempted),
        "load_partial_fail_count": int(load_partial_fail_count),
        "load_partial_fail_machines_sample": list(load_partial_fail_machines_sample),
        "extend_partial_fail_count": int(extend_partial_fail_count),
        "extend_partial_fail_machines_sample": list(extend_partial_fail_machines_sample),
    }


def _compute_resource_pool_degradation(cfg: Any, *, resource_pool_meta: Optional[Dict[str, Any]]) -> Tuple[bool, bool, Optional[str], bool]:
    auto_assign_enabled = (
        to_yes_no(_cfg_value(cfg, "auto_assign_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
    )
    meta = resource_pool_meta if isinstance(resource_pool_meta, dict) else {}

    attempted = bool(meta.get("resource_pool_attempted") or False)
    build_ok_raw = meta.get("resource_pool_build_ok")
    build_ok = True if build_ok_raw is None else bool(build_ok_raw)
    build_error = meta.get("resource_pool_build_error")

    degraded = bool(auto_assign_enabled and attempted and (not build_ok))
    degradation_reason = str(build_error or "自动分配资源池构建失败") if degraded else None
    return auto_assign_enabled, degraded, degradation_reason, attempted


def _hard_constraints(cfg: Any, *, downtime_degraded: bool, freeze_state: str) -> List[str]:
    hard_constraints: List[str] = [
        "precedence",
        "calendar",
        "resource_machine_operator",
    ]
    if not downtime_degraded:
        hard_constraints.append("downtime_avoid")
    if str(freeze_state or "").strip().lower() == "active":
        hard_constraints.append("freeze_window")
    return hard_constraints


def build_result_summary(
    svc,
    *,
    cfg: Any,
    version: int,
    normalized_batch_ids: List[str],
    start_dt: datetime,
    end_date: Optional[Any],
    batches: Dict[str, Any],
    operations: List[Any],
    results: List[Any],
    summary: Any,
    used_strategy: Any,
    used_params: Dict[str, Any],
    algo_mode: str,
    objective_name: str,
    time_budget_seconds: int,
    best_score: Optional[Tuple[float, ...]],
    best_metrics: Optional[Any],
    best_order: List[str],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]] = None,
    input_build_outcome: Optional[BuildOutcome[Any]] = None,
    downtime_meta: Optional[Dict[str, Any]] = None,
    resource_pool_meta: Optional[Dict[str, Any]] = None,
    algo_stats: Optional[Dict[str, Any]] = None,
    algo_warnings: Optional[List[str]] = None,
    warning_merge_status: Optional[Dict[str, Any]] = None,
    simulate: bool,
    t0: float,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    """
    生成：超期清单 + result_status + result_summary（dict/json）。

    Returns:
        (overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms)
    """
    # 超期预警：批次预计完工时间 vs due_date
    finish_by_batch = _finish_time_by_batch(results)
    overdue_items, overdue_meta = _build_overdue_items(svc, batches=batches, finish_by_batch=finish_by_batch, summary=summary)
    invalid_due_count = _metric_int(best_metrics, "invalid_due_count") or int(overdue_meta.get("invalid_due_count") or 0)
    invalid_due_batch_ids_sample = _metric_sample(best_metrics, "invalid_due_batch_ids_sample", limit=10) or list(
        overdue_meta.get("invalid_due_batch_ids_sample") or []
    )
    unscheduled_batch_ids_all = [
        str(bid).strip()
        for bid in sorted(batches.keys(), key=lambda item: str(item).strip())
        if str(bid).strip() and str(bid).strip() not in finish_by_batch
    ]
    unscheduled_batch_count = _metric_int(best_metrics, "unscheduled_batch_count") or int(len(unscheduled_batch_ids_all))
    unscheduled_batch_ids_sample = _metric_sample(best_metrics, "unscheduled_batch_ids_sample", limit=20) or list(
        unscheduled_batch_ids_all[:20]
    )

    # result_status：success/partial/failed/simulated
    result_status = _compute_result_status(summary, simulate=simulate)

    time_cost_ms = int((time.time() - float(t0)) * 1000)

    frozen_batch_ids = _frozen_batch_ids(operations, frozen_op_ids=frozen_op_ids)

    # 冻结窗口降级识别：目前以 warnings 前缀为准（freeze_window.py 会统一加前缀）
    summary_warnings = _warning_list(getattr(summary, "warnings", None))
    algo_warning_list = _warning_list(algo_warnings)
    all_warnings = _merge_warning_lists(summary_warnings, algo_warning_list)
    freeze_warnings = _extract_freeze_warnings(all_warnings)
    input_state = _input_build_state(input_build_outcome)
    merge_context_degraded = bool(input_state.get("merge_context_degraded"))
    merge_context_events = list(input_state.get("merge_context_events") or [])
    if merge_context_degraded:
        all_warnings = _merge_warning_lists(
            all_warnings,
            ["组合并语义已退化：部分外协工序缺少模板或外部组，已按逐道外协语义继续排产。"],
        )
    if unscheduled_batch_count > 0:
        sample_text = "、".join(unscheduled_batch_ids_sample[:10])
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {unscheduled_batch_count} 个批次未形成完工结果（示例批次：{sample_text}）。"],
        )
    freeze_state = _freeze_meta_dict(
        cfg,
        frozen_op_ids=frozen_op_ids,
        freeze_meta=freeze_meta,
        freeze_warnings=freeze_warnings,
    )
    if str(freeze_state.get("freeze_state") or "") == "degraded" and freeze_state.get("degradation_reason"):
        all_warnings = _merge_warning_lists(all_warnings, [f"【冻结窗口】未生效：{freeze_state.get('degradation_reason')}"])

    # 停机约束状态：避免“停机加载失败但摘要仍宣称硬约束已启用”
    downtime_state = _compute_downtime_degradation(cfg, downtime_meta=downtime_meta)
    auto_assign_enabled = bool(downtime_state.get("auto_assign_enabled"))
    downtime_load_ok = bool(downtime_state.get("downtime_load_ok"))
    downtime_degraded = bool(downtime_state.get("downtime_degraded"))
    downtime_degradation_reason = downtime_state.get("downtime_degradation_reason")
    downtime_extend_attempted = bool(downtime_state.get("downtime_extend_attempted"))
    downtime_load_partial_fail_count = int(downtime_state.get("load_partial_fail_count") or 0)
    downtime_load_partial_fail_machines_sample = list(downtime_state.get("load_partial_fail_machines_sample") or [])
    downtime_extend_partial_fail_count = int(downtime_state.get("extend_partial_fail_count") or 0)
    downtime_extend_partial_fail_machines_sample = list(downtime_state.get("extend_partial_fail_machines_sample") or [])
    resource_pool_enabled, resource_pool_degraded, resource_pool_degradation_reason, resource_pool_attempted = (
        _compute_resource_pool_degradation(cfg, resource_pool_meta=resource_pool_meta)
    )
    hard_constraints = _hard_constraints(
        cfg, downtime_degraded=downtime_degraded, freeze_state=str(freeze_state.get("freeze_state") or "disabled")
    )

    warning_pipeline = warning_merge_status if isinstance(warning_merge_status, dict) else {}
    algo_stats_dict = algo_stats if isinstance(algo_stats, dict) else {}
    fallback_counts = _counter_dict(algo_stats_dict.get("fallback_counts"))
    param_fallbacks = _counter_dict(algo_stats_dict.get("param_fallbacks"))
    legacy_external_days_defaulted_count = int(fallback_counts.get("legacy_external_days_defaulted_count") or 0)
    ortools_warmstart_failed_count = int(fallback_counts.get("ortools_warmstart_failed_count") or 0)
    if legacy_external_days_defaulted_count > 0:
        all_warnings = _merge_warning_lists(
            all_warnings,
            [f"存在 {legacy_external_days_defaulted_count} 道外协工序使用了历史兼容周期 1.0 天。"],
        )
    if ortools_warmstart_failed_count > 0:
        all_warnings = _merge_warning_lists(all_warnings, ["OR-Tools 预热失败，已回退到常规求解路径。"])

    summary_degradation = _summary_degradation_state(
        input_state=input_state,
        invalid_due_count=int(invalid_due_count),
        invalid_due_batch_ids_sample=list(invalid_due_batch_ids_sample),
        legacy_external_days_defaulted_count=int(legacy_external_days_defaulted_count),
        freeze_state=freeze_state,
        downtime_state=downtime_state,
        resource_pool_enabled=bool(resource_pool_enabled),
        resource_pool_degraded=bool(resource_pool_degraded),
        resource_pool_degradation_reason=resource_pool_degradation_reason,
        ortools_warmstart_failed_count=int(ortools_warmstart_failed_count),
    )

    comparison_metric = _comparison_metric(objective_name)
    result_summary_obj: Dict[str, Any] = {
        "summary_schema_version": "1.1",
        "is_simulation": bool(simulate),
        "version": int(version),
        "strategy": used_strategy.value,
        "strategy_params": used_params or {},
        "algo": {
            "mode": algo_mode,
            "objective": objective_name,
            "comparison_metric": comparison_metric,
            "config_snapshot": _config_snapshot_dict(cfg),
            "time_budget_seconds": int(time_budget_seconds),
            "hard_constraints": hard_constraints,
            "soft_objectives": [objective_name],
            "best_score": list(best_score) if best_score is not None else None,
            "best_score_schema": _best_score_schema(objective_name),
            "metrics": best_metrics.to_dict() if best_metrics is not None else None,
            "best_batch_order": list(best_order or []),
            "attempts": (attempts or [])[:12],
            "improvement_trace": (improvement_trace or [])[:200],
            "downtime_avoid": {
                "loaded_ok": bool(downtime_load_ok),
                "degraded": bool(downtime_degraded),
                "degradation_reason": downtime_degradation_reason,
                "extend_attempted": bool(downtime_extend_attempted) if auto_assign_enabled else False,
                "load_partial_fail_count": int(downtime_load_partial_fail_count),
                "load_partial_fail_machines_sample": list(downtime_load_partial_fail_machines_sample),
                "extend_partial_fail_count": int(downtime_extend_partial_fail_count) if auto_assign_enabled else 0,
                "extend_partial_fail_machines_sample": (
                    list(downtime_extend_partial_fail_machines_sample) if auto_assign_enabled else []
                ),
            },
            "input_contract": {
                "degraded": bool(input_state.get("degraded")),
                "degradation_events": list(input_state.get("degradation_events") or []),
                "degradation_counters": dict(input_state.get("degradation_counters") or {}),
                "empty_reason": input_state.get("empty_reason"),
            },
            "merge_context_degraded": bool(merge_context_degraded),
            "merge_context_events": list(merge_context_events),
            "freeze_window": {
                "enabled": YesNo.YES.value if bool(freeze_state.get("enabled")) else YesNo.NO.value,
                "days": int(freeze_state.get("days") or 0),
                "frozen_op_count": int(len(frozen_op_ids)),
                "frozen_batch_count": int(len(frozen_batch_ids)),
                "frozen_batch_ids_sample": frozen_batch_ids[:20],
                "freeze_state": freeze_state.get("freeze_state"),
                "freeze_applied": bool(freeze_state.get("freeze_applied")),
                "freeze_degradation_codes": list(freeze_state.get("freeze_degradation_codes") or []),
                "degraded": str(freeze_state.get("freeze_state") or "") == "degraded",
                "degradation_reason": freeze_state.get("degradation_reason"),
            },
        },
        "selected_batch_ids": list(normalized_batch_ids),
        "start_time": svc._format_dt(start_dt),
        "end_date": _serialize_end_date(end_date),
        "invalid_due_count": int(invalid_due_count),
        "invalid_due_batch_ids_sample": list(invalid_due_batch_ids_sample[:10]),
        "unscheduled_batch_count": int(unscheduled_batch_count),
        "unscheduled_batch_ids_sample": list(unscheduled_batch_ids_sample[:20]),
        "legacy_external_days_defaulted_count": int(legacy_external_days_defaulted_count),
        "degradation_events": list(summary_degradation.get("events") or []),
        "degradation_counters": dict(summary_degradation.get("counters") or {}),
        "counts": {
            "batch_count": len(batches),
            # 与调度器 summary 同口径（包含 seed_results；并考虑 seed 与 operations 去重过滤）
            "op_count": int(getattr(summary, "total_ops", 0)),
            "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
            "failed_ops": int(getattr(summary, "failed_ops", 0)),
            "unscheduled_batch_count": int(unscheduled_batch_count),
        },
        "overdue_batches": {"count": len(overdue_items), "items": overdue_items},
        "errors_sample": (getattr(summary, "errors", None) or [])[:10],
        "warnings": list(all_warnings),
        "time_cost_ms": int(time_cost_ms),
    }

    algo_dict = result_summary_obj.get("algo") or {}
    if resource_pool_enabled or (isinstance(resource_pool_meta, dict) and bool(resource_pool_meta)):
        algo_dict["resource_pool"] = {
            "enabled": _cfg_value(cfg, "auto_assign_enabled", "no"),
            "attempted": bool(resource_pool_attempted) if resource_pool_enabled else False,
            "degraded": bool(resource_pool_degraded),
            "degradation_reason": resource_pool_degradation_reason,
        }
    if algo_warning_list or any(bool(x) for x in warning_pipeline.values()):
        algo_dict["warning_pipeline"] = {
            "algo_warning_count": int(len(algo_warning_list)),
            "summary_warning_count": int(len(summary_warnings)),
            "summary_merge_attempted": bool(warning_pipeline.get("summary_merge_attempted") or False),
            "summary_merge_failed": bool(warning_pipeline.get("summary_merge_failed") or False),
            "summary_merge_error": warning_pipeline.get("summary_merge_error"),
        }
    if fallback_counts:
        algo_dict["fallback_counts"] = fallback_counts
    if param_fallbacks:
        algo_dict["param_fallbacks"] = param_fallbacks
    result_summary_obj["algo"] = algo_dict

    result_summary_obj = _apply_summary_size_guard(result_summary_obj)
    result_summary_json = json.dumps(result_summary_obj, ensure_ascii=False)
    return overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms


from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import YesNo

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
        bid = str(getattr(r, "batch_id", "") or "")
        cur = finish_by_batch.get(bid)
        if (cur is None) or (r.end_time > cur):
            finish_by_batch[bid] = r.end_time
    return finish_by_batch


def _build_overdue_items(svc, *, batches: Dict[str, Any], finish_by_batch: Dict[str, datetime], summary: Any) -> List[Dict[str, Any]]:
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
        try:
            summary.warnings.append(msg)
        except Exception:
            pass
        if svc.logger:
            try:
                raw_sample = "；".join(invalid_due_raw_sample[:5])
                svc.logger.warning(f"{msg}；示例原始 due_date：{raw_sample}")
            except Exception:
                pass

    return overdue_items


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
    all_warnings = getattr(summary, "warnings", None) or []
    freeze_warnings: List[str] = []
    try:
        for w in list(all_warnings or []):
            ws = str(w)
            if ws.startswith("【冻结窗口】"):
                freeze_warnings.append(ws)
    except Exception:
        freeze_warnings = []
    return freeze_warnings


def _compute_downtime_degradation(cfg: Any, *, downtime_meta: Optional[Dict[str, Any]]) -> Tuple[bool, bool, bool, Optional[str], bool]:
    auto_assign_enabled = (
        to_yes_no(_cfg_value(cfg, "auto_assign_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
    )

    meta = downtime_meta if isinstance(downtime_meta, dict) else {}

    downtime_load_ok = True if "downtime_load_ok" not in meta else bool(meta.get("downtime_load_ok"))
    downtime_load_error = meta.get("downtime_load_error")

    downtime_extend_attempted = bool(meta.get("downtime_extend_attempted") or False)
    extend_ok_raw = meta.get("downtime_extend_ok")
    downtime_extend_ok = True if extend_ok_raw is None else bool(extend_ok_raw)
    downtime_extend_error = meta.get("downtime_extend_error")

    extend_failed = bool(auto_assign_enabled and downtime_extend_attempted and (not downtime_extend_ok))
    downtime_degraded = (not downtime_load_ok) or extend_failed
    downtime_degradation_reason = None
    if downtime_degraded:
        if not downtime_load_ok:
            downtime_degradation_reason = str(downtime_load_error or "停机区间加载失败")
        elif extend_failed:
            downtime_degradation_reason = str(downtime_extend_error or "停机区间扩展加载失败")

    return auto_assign_enabled, downtime_load_ok, downtime_degraded, downtime_degradation_reason, downtime_extend_attempted


def _hard_constraints(cfg: Any, *, downtime_degraded: bool) -> List[str]:
    hard_constraints: List[str] = [
        "precedence",
        "calendar",
        "resource_machine_operator",
    ]
    if not downtime_degraded:
        hard_constraints.append("downtime_avoid")
    if to_yes_no(_cfg_value(cfg, "freeze_window_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value:
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
    downtime_meta: Optional[Dict[str, Any]] = None,
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
    overdue_items = _build_overdue_items(svc, batches=batches, finish_by_batch=finish_by_batch, summary=summary)

    # result_status：success/partial/failed/simulated
    result_status = _compute_result_status(summary, simulate=simulate)

    time_cost_ms = int((time.time() - float(t0)) * 1000)

    frozen_batch_ids = _frozen_batch_ids(operations, frozen_op_ids=frozen_op_ids)

    # 冻结窗口降级识别：目前以 warnings 前缀为准（freeze_window.py 会统一加前缀）
    all_warnings = getattr(summary, "warnings", None) or []
    freeze_warnings = _extract_freeze_warnings(summary)

    # 停机约束状态：避免“停机加载失败但摘要仍宣称硬约束已启用”
    auto_assign_enabled, downtime_load_ok, downtime_degraded, downtime_degradation_reason, downtime_extend_attempted = (
        _compute_downtime_degradation(cfg, downtime_meta=downtime_meta)
    )
    hard_constraints = _hard_constraints(cfg, downtime_degraded=downtime_degraded)

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
            },
            "freeze_window": {
                "enabled": _cfg_value(cfg, "freeze_window_enabled", "no"),
                "days": int(_cfg_value(cfg, "freeze_window_days", 0) or 0),
                "frozen_op_count": int(len(frozen_op_ids)),
                "frozen_batch_count": int(len(frozen_batch_ids)),
                "frozen_batch_ids_sample": frozen_batch_ids[:20],
                "degraded": bool(freeze_warnings),
                "degradation_reason": (freeze_warnings[0] if freeze_warnings else None),
            },
        },
        "selected_batch_ids": list(normalized_batch_ids),
        "start_time": svc._format_dt(start_dt),
        "end_date": _serialize_end_date(end_date),
        "counts": {
            "batch_count": len(batches),
            # 与调度器 summary 同口径（包含 seed_results；并考虑 seed 与 operations 去重过滤）
            "op_count": int(getattr(summary, "total_ops", 0)),
            "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
            "failed_ops": int(getattr(summary, "failed_ops", 0)),
        },
        "overdue_batches": {"count": len(overdue_items), "items": overdue_items},
        "errors_sample": (getattr(summary, "errors", None) or [])[:10],
        "warnings": list(all_warnings or []),
        "time_cost_ms": int(time_cost_ms),
    }

    result_summary_obj = _apply_summary_size_guard(result_summary_obj)
    result_summary_json = json.dumps(result_summary_obj, ensure_ascii=False)
    return overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms


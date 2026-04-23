from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..summary.schedule_summary_types import SummaryBuildContext
from .schedule_input_collector import ScheduleRunInput
from .schedule_persistence import ValidatedSchedulePayload, build_validated_schedule_payload

_LOGGER = logging.getLogger(__name__)
_SUMMARY_MERGE_ERROR_CODES = {
    "summary_missing",
    "summary_warnings_assignment_failed",
    "summary_warnings_unavailable",
}


def _normalize_summary_merge_error(reason: Any) -> Optional[str]:
    text = str(reason or "").strip()
    if not text:
        return None
    if text in _SUMMARY_MERGE_ERROR_CODES:
        return text
    return "summary_warnings_assignment_failed"


@dataclass(frozen=True)
class ScheduleSummaryContract:
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.payload)


@dataclass
class ScheduleOrchestrationOutcome:
    version: int
    results: List[Any]
    summary: Any
    summary_contract: ScheduleSummaryContract
    validated_schedule_payload: ValidatedSchedulePayload
    used_strategy: Any
    used_params: Dict[str, Any]
    best_metrics: Any
    best_score: Tuple[float, ...]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    algo_stats: Dict[str, Any]
    time_budget_seconds: int
    warning_merge_status: Dict[str, Any]
    algo_warnings: List[str]
    overdue_items: List[Any]
    result_status: str
    result_summary_obj: Dict[str, Any]
    result_summary_json: str
    time_cost_ms: int


@dataclass
class _NormalizedOptimizerOutcome:
    results: List[Any]
    summary: Any
    used_strategy: Any
    used_params: Dict[str, Any]
    best_metrics: Any
    best_score: Tuple[float, ...]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    algo_stats: Dict[str, Any]
    time_budget_seconds: int


def _summary_field(summary: Any, field: str, default: Any) -> Any:
    if isinstance(summary, dict):
        return summary.get(field, default)
    return getattr(summary, field, default)


def _summary_warnings(result_summary_obj: Dict[str, Any], summary: Any) -> List[str]:
    if isinstance(result_summary_obj, dict) and "warnings" in result_summary_obj:
        raw_warnings = result_summary_obj.get("warnings")
        if raw_warnings is None:
            return []
        if isinstance(raw_warnings, str):
            return [raw_warnings] if raw_warnings else []
        try:
            return [str(item) for item in list(raw_warnings or []) if str(item)]
        except Exception:
            text = str(raw_warnings).strip()
            return [text] if text else []
    return list(_summary_field(summary, "warnings", []) or [])


def _summary_errors(result_summary_obj: Dict[str, Any], summary: Any) -> List[str]:
    if isinstance(result_summary_obj, dict) and "errors" in result_summary_obj:
        raw_errors = result_summary_obj.get("errors")
    else:
        raw_errors = _summary_field(summary, "errors", [])
    if raw_errors is None:
        return []
    if isinstance(raw_errors, str):
        return [raw_errors] if raw_errors else []
    try:
        return [str(item) for item in list(raw_errors or []) if str(item)]
    except Exception:
        text = str(raw_errors).strip()
        return [text] if text else []


def _summary_counts(result_summary_obj: Dict[str, Any], summary: Any) -> Dict[str, int]:
    raw_counts = result_summary_obj.get("counts") if isinstance(result_summary_obj, dict) else {}
    counts = dict(raw_counts or {}) if isinstance(raw_counts, dict) else {}

    def _to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    total_ops = _to_int(counts.get("op_count", counts.get("total_ops", _summary_field(summary, "total_ops", 0))))
    scheduled_ops = _to_int(counts.get("scheduled_ops", _summary_field(summary, "scheduled_ops", 0)))
    failed_ops = _to_int(counts.get("failed_ops", _summary_field(summary, "failed_ops", 0)))
    counts["op_count"] = total_ops
    counts["total_ops"] = total_ops
    counts["scheduled_ops"] = scheduled_ops
    counts["failed_ops"] = failed_ops
    return counts


def _build_summary_contract(summary: Any, *, result_summary_obj: Dict[str, Any]) -> ScheduleSummaryContract:
    payload = dict(result_summary_obj or {})
    warnings = _summary_warnings(result_summary_obj, summary)
    errors = _summary_errors(result_summary_obj, summary)
    counts = _summary_counts(result_summary_obj, summary)
    payload.update(
        {
            "success": bool(_summary_field(summary, "success", False)),
            "total_ops": int(counts.get("total_ops") or 0),
            "scheduled_ops": int(counts.get("scheduled_ops") or 0),
            "failed_ops": int(counts.get("failed_ops") or 0),
            "warnings": list(warnings),
            "errors": list(errors),
            "duration_seconds": float(_summary_field(summary, "duration_seconds", 0.0) or 0.0),
            "degradation_events": list(payload.get("degradation_events") or []),
            "degradation_counters": dict(payload.get("degradation_counters") or {}),
            "degraded_success": bool(payload.get("degraded_success") or False),
            "degraded_causes": list(payload.get("degraded_causes") or []),
            "error_count": int(payload.get("error_count") or len(errors)),
            "errors_sample": list(payload.get("errors_sample") or errors[:10]),
            "counts": counts,
        }
    )
    payload["error_count"] = max(int(payload.get("error_count") or 0), len(payload["errors_sample"]), len(errors))
    return ScheduleSummaryContract(payload=payload)


def _normalize_optimizer_outcome(optimizer_outcome: Any) -> _NormalizedOptimizerOutcome:
    return _NormalizedOptimizerOutcome(
        results=list(getattr(optimizer_outcome, "results", []) or []),
        summary=getattr(optimizer_outcome, "summary", None),
        used_strategy=getattr(optimizer_outcome, "used_strategy", None),
        used_params=dict(getattr(optimizer_outcome, "used_params", {}) or {}),
        best_metrics=getattr(optimizer_outcome, "metrics", None),
        best_score=tuple(getattr(optimizer_outcome, "best_score", ()) or ()),
        best_order=list(getattr(optimizer_outcome, "best_order", []) or []),
        attempts=list(getattr(optimizer_outcome, "attempts", []) or []),
        improvement_trace=list(getattr(optimizer_outcome, "improvement_trace", []) or []),
        algo_mode=str(getattr(optimizer_outcome, "algo_mode", "") or ""),
        objective_name=str(getattr(optimizer_outcome, "objective_name", "") or ""),
        algo_stats=dict(getattr(optimizer_outcome, "algo_stats", {}) or {}),
        time_budget_seconds=int(getattr(optimizer_outcome, "time_budget_seconds", 0) or 0),
    )


def _merge_summary_warnings(summary: Any, algo_warnings: List[str]) -> Dict[str, Any]:
    warning_merge_status: Dict[str, Any] = {
        "summary_merge_attempted": bool(algo_warnings),
        "summary_merge_failed": False,
        "summary_merge_error": None,
    }

    summary_warnings = getattr(summary, "warnings", None)
    if summary_warnings is None:
        summary_warnings = []
        if summary is None:
            warning_merge_status["summary_merge_failed"] = bool(algo_warnings)
            warning_merge_status["summary_merge_error"] = "summary_missing"
        else:
            try:
                summary.warnings = summary_warnings
            except (AttributeError, TypeError) as exc:
                warning_merge_status["summary_merge_failed"] = True
                warning_merge_status["summary_merge_error"] = "summary_warnings_assignment_failed"
                _LOGGER.warning("summary warnings assignment failed: %s", exc)

    if algo_warnings:
        if hasattr(summary_warnings, "extend"):
            summary_warnings.extend(algo_warnings)
        else:
            warning_merge_status["summary_merge_failed"] = True
            warning_merge_status["summary_merge_error"] = (
                _normalize_summary_merge_error(warning_merge_status.get("summary_merge_error")) or "summary_warnings_unavailable"
            )

    warning_merge_status["summary_merge_error"] = _normalize_summary_merge_error(warning_merge_status.get("summary_merge_error"))
    return warning_merge_status


def orchestrate_schedule_run(
    svc: Any,
    *,
    schedule_input: ScheduleRunInput,
    simulate: bool,
    strict_mode: bool,
    optimize_schedule_fn: Any,
    build_result_summary_fn: Any,
) -> ScheduleOrchestrationOutcome:
    optimizer_outcome = _normalize_optimizer_outcome(
        optimize_schedule_fn(
            calendar_service=schedule_input.cal_svc,
            cfg_svc=schedule_input.cfg_svc,
            cfg=schedule_input.cfg,
            algo_ops_to_schedule=schedule_input.algo_ops_to_schedule,
            batches=schedule_input.batches,
            start_dt=schedule_input.start_dt_norm,
            end_date=schedule_input.end_date_norm,
            downtime_map=schedule_input.downtime_map,
            seed_results=schedule_input.seed_results,
            resource_pool=schedule_input.resource_pool,
            version=schedule_input.optimizer_seed_version,
            logger=svc.logger,
            strict_mode=bool(strict_mode),
        )
    )

    validated_schedule_payload = build_validated_schedule_payload(
        optimizer_outcome.results,
        allowed_op_ids=set(schedule_input.reschedulable_op_ids),
    )

    warning_merge_status = _merge_summary_warnings(
        optimizer_outcome.summary,
        list(schedule_input.algo_warnings or []),
    )

    with svc.tx_manager.transaction():
        version = int(svc.history_repo.allocate_next_version())

    summary_ctx = SummaryBuildContext(
        cfg=schedule_input.cfg,
        version=version,
        normalized_batch_ids=schedule_input.normalized_batch_ids,
        start_dt=schedule_input.start_dt_norm,
        end_date=schedule_input.end_date_norm,
        batches=schedule_input.batches,
        operations=schedule_input.operations,
        results=optimizer_outcome.results,
        summary=optimizer_outcome.summary,
        used_strategy=optimizer_outcome.used_strategy,
        used_params=optimizer_outcome.used_params,
        algo_mode=optimizer_outcome.algo_mode,
        objective_name=optimizer_outcome.objective_name,
        time_budget_seconds=int(optimizer_outcome.time_budget_seconds),
        best_score=optimizer_outcome.best_score,
        best_metrics=optimizer_outcome.best_metrics,
        best_order=optimizer_outcome.best_order,
        attempts=optimizer_outcome.attempts,
        improvement_trace=optimizer_outcome.improvement_trace,
        frozen_op_ids=set(schedule_input.frozen_op_ids),
        freeze_meta=schedule_input.freeze_meta,
        input_build_outcome=schedule_input.algo_input_outcome,
        downtime_meta=schedule_input.downtime_meta,
        resource_pool_meta=schedule_input.resource_pool_meta,
        algo_stats=optimizer_outcome.algo_stats,
        algo_warnings=list(schedule_input.algo_warnings or []),
        warning_merge_status=warning_merge_status,
        simulate=simulate,
        t0=schedule_input.t0,
    )

    overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary_fn(
        svc,
        ctx=summary_ctx,
    )

    return ScheduleOrchestrationOutcome(
        version=version,
        results=optimizer_outcome.results,
        summary=optimizer_outcome.summary,
        summary_contract=_build_summary_contract(
            optimizer_outcome.summary,
            result_summary_obj=result_summary_obj,
        ),
        validated_schedule_payload=validated_schedule_payload,
        used_strategy=optimizer_outcome.used_strategy,
        used_params=optimizer_outcome.used_params,
        best_metrics=optimizer_outcome.best_metrics,
        best_score=optimizer_outcome.best_score,
        best_order=optimizer_outcome.best_order,
        attempts=optimizer_outcome.attempts,
        improvement_trace=optimizer_outcome.improvement_trace,
        algo_mode=optimizer_outcome.algo_mode,
        objective_name=optimizer_outcome.objective_name,
        algo_stats=optimizer_outcome.algo_stats,
        time_budget_seconds=optimizer_outcome.time_budget_seconds,
        warning_merge_status=warning_merge_status,
        algo_warnings=list(schedule_input.algo_warnings or []),
        overdue_items=overdue_items,
        result_status=result_status,
        result_summary_obj=result_summary_obj,
        result_summary_json=result_summary_json,
        time_cost_ms=int(time_cost_ms),
    )

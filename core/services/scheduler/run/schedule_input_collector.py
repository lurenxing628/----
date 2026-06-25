from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import ValidationError
from core.models import Batch, BatchOperation
from core.models.enums import BatchStatus, ReadyStatus, SourceType, YesNo
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.execution_fact_provider import ExecutionFact
from core.shared.boolean_normalize import normalize_yes_no_wide

from ..number_utils import parse_finite_float, to_yes_no
from .schedule_execution_guardrails import (
    _collect_execution_guardrails,
    _op_id,
)
from .schedule_input_contracts import _build_algo_operations_outcome
from .schedule_input_runtime_support import _build_runtime_support_inputs

_FAIL_FAST_BATCH_STATUSES = frozenset((BatchStatus.COMPLETED.value, BatchStatus.CANCELLED.value))


@dataclass
class ScheduleRunInput:
    normalized_batch_ids: List[str]
    start_dt_norm: datetime
    end_date_norm: Optional[date]
    created_by_text: str
    run_label: str
    t0: float
    cal_svc: Any
    cfg_svc: Any
    cfg: Any
    readiness_gate_enabled: bool
    batches: Dict[str, Batch]
    operations: List[BatchOperation]
    reschedulable_operations: List[BatchOperation]
    reschedulable_op_ids: Set[int]
    missing_internal_resource_op_ids: Set[int]
    algo_input_outcome: BuildOutcome[List[Any]]
    algo_ops: List[Any]
    prev_version: int
    frozen_op_ids: Set[int]
    seed_results: List[Dict[str, Any]]
    execution_facts: Dict[int, ExecutionFact]
    execution_fixed_op_ids: Set[int]
    execution_completed_op_ids: Set[int]
    execution_seed_results: List[Dict[str, Any]]
    execution_guard_state_revisions: Dict[int, str]
    execution_snapshot_revision: str
    execution_snapshot_op_ids: List[int]
    execution_snapshot_op_count: int
    execution_has_guarded_facts: bool
    schedule_output_allowed_op_ids: Set[int]
    payload_validation_operations: List[BatchOperation]
    algo_warnings: List[str]
    freeze_meta: Dict[str, Any]
    algo_ops_to_schedule: List[Any]
    downtime_meta: Dict[str, Any]
    resource_pool_meta: Dict[str, Any]
    downtime_map: Dict[str, Any]
    resource_pool: Any
    optimizer_seed_version: int
    run_time_budget_seconds: Optional[float] = None


def _normalized_status_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _raise_schedule_empty_result(message: str, *, reason: str) -> None:
    exc = ValidationError(message, field="排产")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = reason
    raise exc


def _normalize_batch_ids_or_raise(svc: Any, batch_ids: List[str]) -> List[str]:
    if not batch_ids:
        raise ValidationError("请至少选择 1 个批次执行排产。", field="batch_ids")

    normalized: List[str] = []
    seen = set()
    for raw in batch_ids:
        batch_id = svc._normalize_text(raw)
        if not batch_id or batch_id in seen:
            continue
        seen.add(batch_id)
        normalized.append(batch_id)

    if not normalized:
        raise ValidationError("请至少选择 1 个批次执行排产。", field="batch_ids")
    return normalized


def _normalize_schedule_window(svc: Any, *, start_dt: Any, end_date: Any) -> Tuple[datetime, Optional[date]]:
    if start_dt is not None and str(start_dt).strip() != "":
        start_dt_norm = svc._normalize_datetime(start_dt)
        if start_dt_norm is None:
            raise ValidationError(
                "开始时间写法不对，请填写日期或日期加时间，例如 2026-05-20 或 2026-05-20 08:00。",
                field="start_dt",
            )
    else:
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        start_dt_norm = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8, 0, 0)

    end_date_norm = None
    if end_date is not None and str(end_date).strip() != "":
        end_dt = svc._normalize_datetime(end_date)
        if not end_dt:
            raise ValidationError("结束日期写法不对，请填写类似 2026-05-20 的日期。", field="end_date")
        end_date_norm = end_dt.date()
        if end_date_norm < start_dt_norm.date():
            raise ValidationError("结束日期不能早于开始时间所在日期", field="end_date")

    return start_dt_norm, end_date_norm


def _resolve_enforce_ready_effective(cfg: Any, enforce_ready: Optional[bool]) -> bool:
    if enforce_ready is None:
        return to_yes_no(cfg.enforce_ready_default, default=YesNo.NO.value) == YesNo.YES.value
    if isinstance(enforce_ready, bool):
        return bool(enforce_ready)
    if isinstance(enforce_ready, str):
        text = enforce_ready.strip()
        if not text:
            raise ValidationError("齐套检查开关不能为空，请填 yes/no。", field="enforce_ready")
        # 复用 core 低层唯一别名源（认 是/否/y/n/yes/no/true/false/1/0/on/off）；未知值 fail-loud。
        # 不再手搓窄别名集，避免与 normalize_yes_no_wide 单边漂移（"是"/"y" 被误判未知而拒绝）。
        try:
            normalized = normalize_yes_no_wide(text, unknown_policy="raise")
        except ValueError as exc:
            raise ValidationError("齐套检查开关只支持 yes/no。", field="enforce_ready") from exc
        return normalized == YesNo.YES.value
    raise ValidationError("齐套检查开关只支持布尔值或 yes/no。", field="enforce_ready")


def _normalize_run_time_budget_seconds(value: Any) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    budget = parse_finite_float(value, field="run_time_budget_seconds", allow_none=False)
    if budget is None or float(budget) <= 0:
        raise ValidationError("这次找更好排法先试多久必须大于 0 秒。", field="run_time_budget_seconds")
    return float(budget)


def _load_batches_and_operations(svc: Any, normalized_batch_ids: List[str]) -> Tuple[Dict[str, Batch], List[BatchOperation]]:
    batches: Dict[str, Batch] = {}
    operations: List[BatchOperation] = []
    blocked_batch_ids: List[str] = []

    for batch_id in normalized_batch_ids:
        batch = svc._get_batch_or_raise(batch_id)
        batches[batch_id] = batch
        if _normalized_status_text(getattr(batch, "status", None)) in _FAIL_FAST_BATCH_STATUSES:
            blocked_batch_ids.append(batch_id)
            continue
        operations.extend(list(svc.op_repo.list_by_batch(batch_id) or []))

    if blocked_batch_ids:
        sample = "，".join(blocked_batch_ids[:20])
        raise ValidationError(f"以下批次状态不允许排产（已完成/已取消）：{sample}", field="批次")

    return batches, operations


def _build_reschedulable_state(
    svc: Any,
    operations: List[BatchOperation],
    *,
    run_label: str,
) -> Tuple[List[BatchOperation], Set[int], Set[int]]:
    reschedulable_operations = [op for op in operations if svc._is_reschedulable_operation(op)]
    if not reschedulable_operations:
        _raise_schedule_empty_result(
            f"所选批次没有可重排工序，本次未执行{run_label}。",
            reason="no_reschedulable_operations",
        )

    reschedulable_op_ids = {
        int(getattr(op, "id", 0) or 0)
        for op in reschedulable_operations
        if op and getattr(op, "id", None) and int(getattr(op, "id", 0) or 0) > 0
    }
    missing_internal_resource_op_ids = {
        int(getattr(op, "id", 0) or 0)
        for op in reschedulable_operations
        if _is_missing_internal_resource(op) and int(getattr(op, "id", 0) or 0) > 0
    }
    return reschedulable_operations, reschedulable_op_ids, missing_internal_resource_op_ids

def _is_missing_internal_resource(op: BatchOperation) -> bool:
    if not op or not getattr(op, "id", None):
        return False
    if str(getattr(op, "source", "") or "").strip().lower() != SourceType.INTERNAL.value:
        return False
    machine_id = str(getattr(op, "machine_id", "") or "").strip()
    operator_id = str(getattr(op, "operator_id", "") or "").strip()
    return (machine_id == "") or (operator_id == "")


def _ensure_ready_batches(svc: Any, batches: Dict[str, Batch]) -> None:
    not_ready = [
        batch_id
        for batch_id, batch in batches.items()
        if (svc._normalize_text(getattr(batch, "ready_status", None)) or "").strip().lower() != ReadyStatus.YES.value
    ]
    if not_ready:
        sample = "，".join(not_ready[:20])
        raise ValidationError(f"以下批次未齐套，禁止排产：{sample}", field="齐套")


def _remove_completed_from_reschedulable(
    *,
    reschedulable_operations: List[BatchOperation],
    reschedulable_op_ids: Set[int],
    missing_internal_resource_op_ids: Set[int],
    execution_completed_op_ids: Set[int],
    run_label: str,
) -> Tuple[List[BatchOperation], Set[int], Set[int]]:
    if not execution_completed_op_ids:
        return reschedulable_operations, reschedulable_op_ids, missing_internal_resource_op_ids
    completed = set(execution_completed_op_ids)
    remaining_operations = [op for op in reschedulable_operations if _op_id(op) not in completed]
    remaining_op_ids = {int(op_id) for op_id in reschedulable_op_ids if int(op_id) not in completed}
    remaining_missing_resource_ids = {
        int(op_id) for op_id in missing_internal_resource_op_ids if int(op_id) not in completed
    }
    if not remaining_operations:
        _raise_schedule_empty_result(
            f"所选批次没有可重排工序，本次未执行{run_label}。",
            reason="no_reschedulable_operations",
        )
    return remaining_operations, remaining_op_ids, remaining_missing_resource_ids


def _build_algo_input_or_raise(
    *,
    build_algo_operations_fn: Any,
    svc: Any,
    reschedulable_operations: List[BatchOperation],
    strict_mode: bool,
    run_label: str,
) -> Tuple[BuildOutcome[List[Any]], List[Any]]:
    algo_input_outcome = _build_algo_operations_outcome(
        build_algo_operations_fn,
        svc,
        reschedulable_operations,
        strict_mode=bool(strict_mode),
    )
    algo_ops = list(algo_input_outcome.value or [])
    if not algo_ops:
        _raise_schedule_empty_result(
            f"所选批次未生成可用于排产的工序输入，本次未执行{run_label}。",
            reason=str(getattr(algo_input_outcome, "empty_reason", "") or "").strip() or "no_algo_operations_built",
        )
    return algo_input_outcome, algo_ops


def collect_schedule_run_input(
    svc: Any,
    *,
    batch_ids: List[str],
    start_dt: Any = None,
    end_date: Any = None,
    created_by: Optional[str] = None,
    simulate: bool = False,
    enforce_ready: Optional[bool] = None,
    strict_mode: bool = False,
    run_time_budget_seconds: Any = None,
    calendar_service_cls: Any,
    config_service_cls: Any,
    get_snapshot_with_strict_mode: Any,
    build_algo_operations_fn: Any,
    build_freeze_window_seed_fn: Any,
    load_machine_downtimes_fn: Any,
    build_resource_pool_fn: Any,
    extend_downtime_map_for_resource_pool_fn: Any,
) -> ScheduleRunInput:
    normalized = _normalize_batch_ids_or_raise(svc, batch_ids)
    t0 = time.time()
    start_dt_norm, end_date_norm = _normalize_schedule_window(svc, start_dt=start_dt, end_date=end_date)

    created_by_text = svc._normalize_text(created_by) or "system"
    run_label = "模拟排产" if simulate else "排产"

    cal_svc = calendar_service_cls(svc.conn, logger=svc.logger, op_logger=svc.op_logger)
    cfg_svc = config_service_cls(svc.conn, logger=svc.logger, op_logger=svc.op_logger)
    cfg = get_snapshot_with_strict_mode(cfg_svc, strict_mode=bool(strict_mode))
    enforce_ready_effective = _resolve_enforce_ready_effective(cfg, enforce_ready)
    normalized_run_time_budget_seconds = _normalize_run_time_budget_seconds(run_time_budget_seconds)

    batches, operations = _load_batches_and_operations(svc, normalized)
    reschedulable_operations, reschedulable_op_ids, missing_internal_resource_op_ids = _build_reschedulable_state(
        svc,
        operations,
        run_label=run_label,
    )
    if enforce_ready_effective:
        _ensure_ready_batches(svc, batches)

    prev_version = int(svc.history_repo.get_latest_version() or 0)
    (
        execution_facts,
        execution_fixed_op_ids,
        execution_completed_op_ids,
        execution_seed_results,
        execution_guard_state_revisions,
        execution_snapshot,
    ) = _collect_execution_guardrails(
        svc,
        operations,
        prev_version=prev_version,
    )
    reschedulable_operations, reschedulable_op_ids, missing_internal_resource_op_ids = _remove_completed_from_reschedulable(
        reschedulable_operations=reschedulable_operations,
        reschedulable_op_ids=reschedulable_op_ids,
        missing_internal_resource_op_ids=missing_internal_resource_op_ids,
        execution_completed_op_ids=execution_completed_op_ids,
        run_label=run_label,
    )
    algo_input_outcome, algo_ops = _build_algo_input_or_raise(
        build_algo_operations_fn=build_algo_operations_fn,
        svc=svc,
        reschedulable_operations=reschedulable_operations,
        strict_mode=bool(strict_mode),
        run_label=run_label,
    )

    (
        frozen_op_ids,
        seed_results,
        algo_warnings,
        freeze_meta,
        algo_ops_to_schedule,
        downtime_meta,
        resource_pool_meta,
        downtime_map,
        resource_pool,
        optimizer_seed_version,
    ) = _build_runtime_support_inputs(
        svc,
        cfg=cfg,
        prev_version=prev_version,
        start_dt_norm=start_dt_norm,
        run_label=run_label,
        batches=batches,
        operations=operations,
        reschedulable_operations=reschedulable_operations,
        algo_ops=algo_ops,
        execution_fixed_op_ids=execution_fixed_op_ids,
        execution_completed_op_ids=execution_completed_op_ids,
        execution_seed_results=execution_seed_results,
        strict_mode=bool(strict_mode),
        build_freeze_window_seed_fn=build_freeze_window_seed_fn,
        load_machine_downtimes_fn=load_machine_downtimes_fn,
        build_resource_pool_fn=build_resource_pool_fn,
        extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool_fn,
        raise_schedule_empty_result_fn=_raise_schedule_empty_result,
    )

    return ScheduleRunInput(
        normalized_batch_ids=normalized,
        start_dt_norm=start_dt_norm,
        end_date_norm=end_date_norm,
        created_by_text=created_by_text,
        run_label=run_label,
        t0=t0,
        cal_svc=cal_svc,
        cfg_svc=cfg_svc,
        cfg=cfg,
        readiness_gate_enabled=bool(enforce_ready_effective),
        batches=batches,
        operations=operations,
        reschedulable_operations=reschedulable_operations,
        reschedulable_op_ids=set(reschedulable_op_ids),
        missing_internal_resource_op_ids=set(missing_internal_resource_op_ids),
        algo_input_outcome=algo_input_outcome,
        algo_ops=algo_ops,
        prev_version=prev_version,
        frozen_op_ids=set(frozen_op_ids),
        seed_results=list(seed_results or []),
        execution_facts=dict(execution_facts),
        execution_fixed_op_ids=set(execution_fixed_op_ids),
        execution_completed_op_ids=set(execution_completed_op_ids),
        execution_seed_results=list(execution_seed_results or []),
        execution_guard_state_revisions=dict(execution_guard_state_revisions),
        execution_snapshot_revision=execution_snapshot.revision,
        execution_snapshot_op_ids=list(execution_snapshot.op_ids),
        execution_snapshot_op_count=int(execution_snapshot.op_count),
        execution_has_guarded_facts=bool(execution_fixed_op_ids or execution_completed_op_ids),
        schedule_output_allowed_op_ids=set(reschedulable_op_ids)
        | set(execution_fixed_op_ids)
        | set(execution_completed_op_ids),
        payload_validation_operations=list(operations or []),
        algo_warnings=list(algo_warnings or []),
        freeze_meta=freeze_meta,
        algo_ops_to_schedule=algo_ops_to_schedule,
        downtime_meta=downtime_meta,
        resource_pool_meta=resource_pool_meta,
        downtime_map=downtime_map,
        resource_pool=resource_pool,
        optimizer_seed_version=optimizer_seed_version,
        run_time_budget_seconds=normalized_run_time_budget_seconds,
    )

"""Prove resources, occupied intervals, calendar duration and readiness explicitly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.models.content import content_text
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.scheduler.run.schedule_payload_contract import (
    ValidatedSchedulePayload,
    build_validated_schedule_payload,
)
from core.services.workbench.facts.zero_duration import candidate_point_validator

from .compute_validation import validate_candidate
from .input_runtime import runtime_resource_inputs
from .schedule_occupancy_constraints import (
    collect_occupancy_issues,
    collect_resource_segments,
    resource_overlap_issue,
)
from .schedule_row_constraints import (
    calendar_duration_conflict,
    collect_draft_predecessor_issues,
    evaluate_draft_row,
    external_holds_resources,
    readiness_problem,
    resource_gaps,
)

if TYPE_CHECKING:
    from core.models.workbench_piece_adoption import PieceAdoptionScope

    from .input import PreparedBusinessInput


@dataclass(frozen=True)
class ScheduleValidationOutcome:
    validated_payload: ValidatedSchedulePayload
    resolved_intervals: Mapping[int, Tuple[datetime, datetime]]
    issues: Tuple[Dict[str, Any], ...]


@dataclass(frozen=True)
class DraftScheduleEvaluation:
    issues: Tuple[Dict[str, Any], ...]
    resolved_intervals_by_row: Mapping[str, Tuple[datetime, datetime]]
    proven_points_by_op: Mapping[int, Any]
    piece_scope: Optional[PieceAdoptionScope]


def arrangement_calendar(business: PreparedBusinessInput, arrangements: Sequence[Any]):
    operator_ids = frozenset(
        item
        for item in (
            *(seed["operator_id"] for seed in business.seeds.seed_results),
            *(op.operator_id for op in business.operations),
            *(row.operator_id for row in arrangements),
        )
        if item is not None
    )
    return business.facts.calendar(operator_ids)


def prepare_schedule_validation_context(
    business: PreparedBusinessInput,
    *,
    validation_context: Optional[Mapping[str, Any]] = None,
    payload: Optional[ValidatedSchedulePayload] = None,
) -> Dict[str, Any]:
    piece_scope = business.piece_scope
    quantities = (
        {work.op_id: work.target_quantity for work in piece_scope.operations}
        if piece_scope is not None
        else {op.id: business.batches[op.batch_id].quantity for op in business.operations}
    )
    return {
        "checks": business.facts.checks(),
        "ops": {op.id: op for op in business.operations},
        "algo_ops": {op.id: op for op in business.algo_ops},
        "raw_batches": {batch_id: vars(batch) for batch_id, batch in business.batches.items()},
        "quantities": quantities,
        "actual": business.execution_guard.execution_completed_op_ids,
        "actual_intervals": business.seeds.unscheduled_external_seed_by_op,
        "downtime": adoption_downtimes(business, payload),
        "validation_context": validation_context,
    }


def adoption_downtimes(
    prepared: PreparedBusinessInput, payload: Optional[ValidatedSchedulePayload] = None
):
    if payload is not None:
        actual = prepared.execution_guard.execution_completed_op_ids
        rows = [row for row in payload.schedule_rows if row.source == "internal" and row.op_id not in actual]
        if not rows:
            return {}
    # Locked seeds may precede the requested run window. Prove every planned
    # arrangement against downtime at its own time and assigned machine.
    return runtime_resource_inputs(prepared.facts).downtimes


_CANDIDATE_ISSUES = {
    "protected_resource_invalid": {
        "code": "candidate_resource_invalid",
        "message": "实际安排的原资源身份或自制外协归属不完整，不能正式采用。",
    },
    "resource_invalid": {
        "code": "candidate_resource_invalid",
        "message": "候选实际使用的设备、人员资质、工种或供应商不合法。",
    },
    "execution_unprotected": {
        "code": "candidate_execution_unprotected",
        "message": "已开工、已完工或已取消的工序没有对应的报工记录保护，不能正式采用。",
    },
    "scope_incomplete": {
        "code": "candidate_scope_incomplete",
        "message": "外协工序的目标数量是 0，排不出工期，不能正式采用。",
    },
    "material_not_ready": {
        "code": "candidate_material_not_ready",
        "message": "候选仍有未齐套物料，不能正式采用。",
    },
    "before_material": {
        "code": "candidate_before_material",
        "message": "候选安排早于本工序物料到齐日期。",
    },
    "before_ready_date": {
        "code": "candidate_before_ready_date",
        "message": "候选安排早于实际可开工日期。",
    },
    "calendar_duration_conflict": {
        "code": "candidate_calendar_duration_conflict",
        "message": "候选开完工时间与真实班次、效率、停机或工时不一致。",
    },
    "external_resource_conflict": {
        "code": "candidate_external_resource_conflict",
        "message": "外协候选带有未支持的内部资源占用。",
    },
    "external_duration_conflict": {
        "code": "candidate_external_duration_conflict",
        "message": "外协候选与真实外协周期不一致。",
    },
}

_PIECE_ISSUES = {
    "protected_resource_invalid": {
        "code": "piece_resource_invalid",
        "message": "原工序资料或分配的设备、人员、工种资格有问题，本次没有采用。请到基础资料核对后重新排产。",
    },
    "resource_invalid": {
        "code": "piece_resource_invalid",
        "message": "原工序资料或分配的设备、人员、工种资格有问题，本次没有采用。请到基础资料核对后重新排产。",
    },
    "execution_unprotected": {
        "code": "piece_execution_unprotected",
        "message": "已开工、已完工或已取消的工序没有对应的报工记录保护，本次没有采用。请刷新现场记录后重新排产。",
    },
    "scope_incomplete": {
        "code": "piece_scope_incomplete",
        "message": "外协工序的目标数量是 0，排不出工期，本次没有采用。请到批次管理补数量后重新排产。",
    },
    "material_not_ready": {
        "code": "piece_material_not_ready",
        "message": "批次齐套条件不满足，本次没有采用。请到批次管理核对齐套状态后重新排产。",
    },
    "before_material": {
        "code": "piece_before_material",
        "message": "有工序早于本序物料到齐日期，本次没有采用。请重新排产。",
    },
    "before_ready_date": {
        "code": "piece_before_ready_date",
        "message": "有工序排在齐套日期之前，本次没有采用。请回「执行排产」重新排一次。",
    },
    "calendar_duration_conflict": {
        "code": "piece_calendar_duration_conflict",
        "message": "工序时长和数量、工时定额、工作日历算出来的对不上，本次没有采用。请回「执行排产」重新排一次。",
    },
    "external_resource_conflict": {
        "code": "piece_external_duration_conflict",
        "message": "外协工序的周期或设备人员安排和原资料不一致，本次没有采用。请回「执行排产」重新排一次。",
    },
    "external_duration_conflict": {
        "code": "piece_external_duration_conflict",
        "message": "外协工序的周期或设备人员安排和原资料不一致，本次没有采用。请回「执行排产」重新排一次。",
    },
}


def _candidate_external_conflict(calendar: Any, row: Any, op: Any, actual_intervals: Mapping[int, Any]) -> bool:
    expected = actual_intervals.get(row.op_id)
    if expected is not None:
        return expected != (row.start_time, row.end_time)
    days = op.ext_group_total_days if op.ext_merge_mode == "merged" else op.ext_days
    return calendar.add_calendar_days(row.start_time, days) != row.end_time


def _evaluate_row(
    prepared: PreparedBusinessInput,
    calendar: Any,
    checks: Any,
    row: Any,
    op: Any,
    algo: Any,
    batch: Any,
    raw_batch: Mapping[str, Any],
    raw: Mapping[str, Any],
    quantity: Any,
    downtime: Mapping[Any, Sequence[Any]],
    actual_ids: Any,
    actual_intervals: Mapping[int, Any],
    *,
    purpose: str,
) -> Optional[str]:
    protected_cycle = row.op_id in actual_ids or row.op_id in actual_intervals
    protected_gaps, field_gaps, res_gaps = resource_gaps(
        checks, raw_batch, raw, protected_cycle=protected_cycle
    )
    if protected_cycle:
        if protected_gaps:
            return "protected_resource_invalid"
        if row.op_id in actual_ids:
            return None
    elif field_gaps or res_gaps:
        return "resource_invalid"
    if op.status in ("processing", "completed", "skipped") or batch.status in ("completed", "cancelled"):
        return "execution_unprotected"
    if op.source == "external" and quantity == 0:
        return "scope_incomplete"
    if not protected_cycle:
        code = readiness_problem(checks, raw_batch, raw, row.start_time, prepared.settings)
        if code is not None:
            return code
    held_in_publication = purpose == "publication" and row.op_id in prepared.seeds.frozen_op_ids
    if row.source == "internal":
        if (
            not held_in_publication
            and row.start_time != row.end_time
            and calendar_duration_conflict(
                calendar, row, algo, batch, downtime.get(row.machine_id, ()), quantity=quantity
            )
        ):
            return "calendar_duration_conflict"
        return None
    if external_holds_resources(row):
        return "external_resource_conflict"
    if not held_in_publication and _candidate_external_conflict(calendar, row, algo, actual_intervals):
        return "external_duration_conflict"
    return None


def evaluate_draft_schedule_constraints(
    calendar: Any,
    rows: Sequence[Mapping[str, Any]],
    *,
    context: Mapping[str, Any],
) -> DraftScheduleEvaluation:
    trial_intervals = context["trial_intervals"]
    issues: List[Dict[str, Any]] = list(context["base_issues"])
    for row in rows:
        issues.extend(evaluate_draft_row(calendar, row, context))
    issues.extend(collect_draft_predecessor_issues(rows, context["live"], trial_intervals["current_by_op"]))
    issues.extend(context["piece_issues"])
    issues.extend(
        collect_occupancy_issues(
            rows,
            context["live"],
            trial_intervals=trial_intervals,
            latest_schedule=context["latest_schedule"],
            outside_point_versions=context["outside_point_versions"],
        )
    )
    deduped = tuple({content_text(item): item for item in issues}.values())
    return DraftScheduleEvaluation(
        issues=deduped,
        resolved_intervals_by_row=trial_intervals["current_by_row"],
        proven_points_by_op=trial_intervals["current_points_by_op"],
        piece_scope=context["piece_scope"],
    )


def bind_validated_schedule_outcome(
    business: PreparedBusinessInput,
    schedule_rows: Sequence[Any],
    evaluation: DraftScheduleEvaluation,
) -> ScheduleValidationOutcome:
    payload = build_validated_schedule_payload(
        schedule_rows,
        allowed_op_ids=business.allowed_op_ids,
        operations=business.operations,
        missing_internal_resource_op_ids=business.missing_internal_resource_op_ids,
        point_validator=candidate_point_validator(
            business,
            proven_points=evaluation.proven_points_by_op,
        ),
        operation_sources=business.operation_sources,
    )
    return ScheduleValidationOutcome(
        validated_payload=payload,
        resolved_intervals={row.op_id: (row.start_time, row.end_time) for row in payload.schedule_rows},
        issues=(),
    )


def evaluate_schedule_constraints(
    business: PreparedBusinessInput,
    calendar: Any,
    arrangements: Sequence[Any],
    *,
    purpose: str = "adoption",
    context: Optional[Mapping[str, Any]] = None,
    failure_details: Sequence[Any] = (),
) -> ScheduleValidationOutcome:
    """Unified schedule constraint evaluation for candidate publication and adoption."""
    validation_context = context["validation_context"] if context is not None else None
    payload = validate_candidate(
        business,
        arrangements,
        failure_details=failure_details,
        context=validation_context,
    )
    rows: Sequence[Any] = payload.schedule_rows
    resolved_intervals = {row.op_id: (row.start_time, row.end_time) for row in rows}
    resource_segments = collect_resource_segments(rows, business.execution_guard)
    overlap_issue = resource_overlap_issue(resource_segments)
    if overlap_issue is not None:
        return ScheduleValidationOutcome(
            validated_payload=payload,
            resolved_intervals=resolved_intervals,
            issues=(overlap_issue,),
        )
    resolved_context = (
        prepare_schedule_validation_context(business, payload=payload)
        if context is None
        else context
    )
    checks = resolved_context["checks"]
    ops = resolved_context["ops"]
    algo_ops = resolved_context["algo_ops"]
    raw_batches = resolved_context["raw_batches"]
    quantities = resolved_context["quantities"]
    actual_ids = resolved_context["actual"]
    actual_intervals = resolved_context["actual_intervals"]
    downtime = resolved_context["downtime"]

    issue_map = _PIECE_ISSUES if business.piece_scope is not None else _CANDIDATE_ISSUES
    for row in rows:
        op = ops[row.op_id]
        algo = algo_ops[row.op_id]
        batch = business.batches[op.batch_id]
        raw_batch = raw_batches[op.batch_id]
        raw = {**vars(op), "machine_id": row.machine_id, "operator_id": row.operator_id}
        reason = _evaluate_row(
            business,
            calendar,
            checks,
            row,
            op,
            algo,
            batch,
            raw_batch,
            raw,
            quantities[row.op_id],
            downtime,
            actual_ids,
            actual_intervals,
            purpose=purpose,
        )
        if reason is not None:
            return ScheduleValidationOutcome(
                validated_payload=payload,
                resolved_intervals=resolved_intervals,
                issues=(dict(issue_map[reason]),),
            )
    return ScheduleValidationOutcome(
        validated_payload=payload,
        resolved_intervals=resolved_intervals,
        issues=(),
    )


def validate_adoption_constraints(prepared: PreparedBusinessInput, payload: Sequence[Any]) -> ScheduleValidationOutcome:
    outcome = evaluate_schedule_constraints(
        prepared,
        arrangement_calendar(prepared, payload),
        payload,
    )
    if outcome.issues:
        first = outcome.issues[0]
        raise CandidateAdoptionBlocked(first["code"], first["message"])
    return outcome

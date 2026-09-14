"""Restore AJ's persisted DTOs exactly; no aggregation, coercion or defaults."""

from dataclasses import fields
from datetime import datetime

from core.models.workbench_execution import ExecutionProjection, ProductionReport
from core.models.workbench_execution_input import MAX_OPERATIONS
from core.models.workbench_preflight import public_ref
from core.services.workbench.preflight_checks import number

from .run_input_rows import fail


def _exact_fields(value, cls):
    if not isinstance(value, dict) or set(value) != {field.name for field in fields(cls)}:
        fail("execution_snapshot_invalid", "存下来的报工记录内容不完整，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    return dict(value)


def _validate_projection_quantities(projection):
    for field in ("target_quantity", "known_completed_quantity", "unknown_record_count", "remaining_quantity"):
        value = getattr(projection, field)
        if value is None and field in ("target_quantity", "remaining_quantity"):
            continue
        if not number(value, integer=True):
            fail("execution_projection_type", "存下来的报工数量不是整数，这次排产没有开始。请到现场记录核对后重试。", field=field)
    if type(projection.quantity_complete) is not bool or type(projection.records_complete) is not bool:
        fail("execution_projection_type", "存下来的报工标记不是“是”或“否”，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")


def _validate_projection_collections(projection):
    for field in ("reports", "legacy_facts", "data_gaps"):
        value = getattr(projection, field)
        expected = ProductionReport if field == "reports" else dict
        if not isinstance(value, list) or not all(isinstance(item, expected) for item in value):
            fail("execution_projection_type", "存下来的报工明细里有内容对不上，这次排产没有开始。请刷新重试；仍不行请联系维护人员。", field=field)
    for field in ("plan_identity", "remaining_plan", "write_context"):
        value = getattr(projection, field)
        if value is not None and not isinstance(value, dict):
            fail("execution_projection_type", "存下来的报工附带信息格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。", field=field)


def _validate_projection_times(projection):
    for field in ("first_actual_start", "confirmed_finish"):
        value = getattr(projection, field)
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                fail("execution_projection_type", "存下来的报工时间格式不对，这次排产没有开始。请到现场记录核对后重试。", field=field)
            if parsed.tzinfo is not None:
                fail("execution_projection_type", "存下来的报工时间格式不对，这次排产没有开始。请到现场记录核对后重试。", field=field)


def validate_projection_dto(projection):
    if not isinstance(projection, ExecutionProjection) or not public_ref(projection.operation_ref):
        fail("execution_projection_type", "读到的报工记录或工序编号不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    _validate_projection_quantities(projection)
    if (projection.execution_state not in ("unreported", "started", "partial", "paused", "exception", "complete")
            or projection.data_quality not in ("invalid", "legacy_incomplete", "incomplete", "complete")
            or projection.target_basis not in ("batch", "piece")
            or projection.completion_basis not in (None, "legacy_finish_event", "complete_reports")):
        fail("execution_projection_type", "存下来的报工状态认不出来，这次排产没有开始。请到现场记录核对后重试。")
    _validate_projection_collections(projection)
    _validate_projection_times(projection)


def restore_execution_projections(payload):
    """Decode only complete Projection.to_dict() snapshots saved by run admission."""
    if not isinstance(payload, list) or len(payload) > MAX_OPERATIONS:
        fail("execution_snapshot_invalid", "存下来的报工记录条数超出上限或格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    projections = []
    refs = set()
    for value in payload:
        row = _exact_fields(value, ExecutionProjection)
        if not isinstance(row["reports"], list):
            fail("execution_snapshot_invalid", "存下来的逐次报工格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
        row["reports"] = [ProductionReport(**_exact_fields(report, ProductionReport)) for report in row["reports"]]
        projection = ExecutionProjection(**row)
        validate_projection_dto(projection)
        if not isinstance(projection.operation_ref, str) or projection.operation_ref in refs:
            fail("execution_snapshot_invalid", "存下来的工序编号不对或者有重复，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
        refs.add(projection.operation_ref)
        projections.append(projection)
    return projections

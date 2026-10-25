"""Restore AJ's persisted DTOs exactly; no aggregation, coercion or defaults."""

from dataclasses import fields
from datetime import datetime
from typing import Any, Dict, Optional

from core.models.content import same
from core.models.workbench_execution import ExecutionProjection, ProductionReport
from core.models.workbench_execution_input import MAX_OPERATIONS
from core.models.workbench_preflight import public_ref

from .preflight_checks import number
from .run_input_rows import fail

_DTO_FIELDS = {cls: frozenset(field.name for field in fields(cls)) for cls in (ExecutionProjection, ProductionReport)}


def execution_snapshots_match(left, right):
    """Compare every saved field by permanent operation identity, retaining all rows."""
    return same(sorted(left, key=lambda row: row["operation_ref"]),
                sorted(right, key=lambda row: row["operation_ref"]))


def _exact_fields(value, cls) -> Dict[str, Any]:
    if not isinstance(value, dict) or value.keys() != _DTO_FIELDS[cls]:
        fail("execution_snapshot_invalid", "存下来的报工记录内容不完整，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    return dict(value)


def _validate_projection_quantities(values):
    for field in ("target_quantity", "known_completed_quantity", "unknown_record_count", "remaining_quantity"):
        value = values[field]
        if value is None and field in ("target_quantity", "remaining_quantity"):
            continue
        if not number(value, integer=True):
            fail("execution_projection_type", "存下来的报工数量不是整数，这次排产没有开始。请到现场记录核对后重试。", field=field)
    if type(values["quantity_complete"]) is not bool or type(values["records_complete"]) is not bool:
        fail("execution_projection_type", "存下来的报工标记不是“是”或“否”，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")


def _validate_projection_collections(values, *, check_reports=False):
    for field in ("reports", "legacy_facts", "data_gaps", "voided_reports"):
        if field == "reports" and not check_reports:
            continue
        value = values[field]
        expected = ProductionReport if field == "reports" else dict
        if not isinstance(value, list) or not all(isinstance(item, expected) for item in value):
            fail("execution_projection_type", "存下来的报工明细里有内容对不上，这次排产没有开始。请刷新重试；仍不行请联系维护人员。", field=field)
    for field in ("plan_identity", "remaining_plan", "write_context"):
        value = values[field]
        if value is not None and not isinstance(value, dict):
            fail("execution_projection_type", "存下来的报工附带信息格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。", field=field)


def _validate_projection_times(values):
    for field in ("first_actual_start", "confirmed_finish"):
        value = values[field]
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                fail("execution_projection_type", "存下来的报工时间格式不对，这次排产没有开始。请到现场记录核对后重试。", field=field)
            if parsed.tzinfo is not None:
                fail("execution_projection_type", "存下来的报工时间格式不对，这次排产没有开始。请到现场记录核对后重试。", field=field)


def validate_projection_dto(projection):
    if not isinstance(projection, ExecutionProjection):
        fail("execution_projection_type", "读到的报工记录或工序编号不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    _validate_projection_values(vars(projection), check_reports=True)


def _validate_projection_values(values, *, check_reports=False):
    if not public_ref(values["operation_ref"]):
        fail("execution_projection_type", "读到的报工记录或工序编号不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    _validate_projection_quantities(values)
    if (values["execution_state"] not in ("unreported", "started", "partial", "paused", "exception", "complete")
            or values["data_quality"] not in ("invalid", "legacy_incomplete", "incomplete", "complete")
            or values["target_basis"] not in ("batch", "piece")
            or values["completion_basis"] not in (None, "legacy_finish_event", "complete_reports")):
        fail("execution_projection_type", "存下来的报工状态认不出来，这次排产没有开始。请到现场记录核对后重试。")
    _validate_projection_collections(values, check_reports=check_reports)
    _validate_projection_times(values)


def prepare_execution_projections(payload, *, max_operations: Optional[int] = MAX_OPERATIONS):
    """Validate complete saved fields once without building public ledger DTOs.

    The prepared rows retain all report/audit values for display and quantity
    readers, while workers materialize their DTOs through the adapter below.
    """
    if not isinstance(payload, list) or (max_operations is not None and len(payload) > max_operations):
        fail("execution_snapshot_invalid", "存下来的工序执行快照条数超出上限或格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    projections = []
    refs = set()
    for value in payload:
        # The sole pre-void DTO shape predates this additive audit collection.
        # Its effective reports retain their captured meaning, without querying
        # current facts or changing any persisted snapshot.
        if isinstance(value, dict) and "voided_reports" not in value:
            value = dict(value, voided_reports=[])
        row = _exact_fields(value, ExecutionProjection)
        if not isinstance(row["reports"], list):
            fail("execution_snapshot_invalid", "存下来的逐次报工格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
        row["reports"] = [_exact_fields(report, ProductionReport) for report in row["reports"]]
        _validate_projection_values(row)
        ref = row["operation_ref"]
        if ref in refs:
            fail("execution_snapshot_invalid", "存下来的工序编号不对或者有重复，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
        refs.add(ref)
        projections.append(row)
    return projections


def restore_execution_projections(payload):
    """Materialize the worker DTOs from the same strict, prepared saved fields."""
    projections = []
    for row in prepare_execution_projections(payload, max_operations=None):
        row["reports"] = [ProductionReport(**report) for report in row["reports"]]
        projections.append(ExecutionProjection(**row))
    return projections

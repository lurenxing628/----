"""Restore AJ's persisted DTOs exactly; no aggregation, coercion or defaults."""

from dataclasses import fields
from typing import Any, Dict, Optional

from core.models.content import same
from core.models.workbench_execution import ExecutionProjection, ProductionReport
from core.models.workbench_execution_input import MAX_OPERATIONS

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
        row = _exact_fields(value, ExecutionProjection)
        if not isinstance(row["reports"], list):
            fail("execution_snapshot_invalid", "存下来的逐次报工格式不对，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
        row["reports"] = [_exact_fields(report, ProductionReport) for report in row["reports"]]
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

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
        fail("execution_snapshot_invalid", "Persisted execution DTO fields are missing or unexpected.")
    return dict(value)


def _validate_projection_quantities(projection):
    for field in ("target_quantity", "known_completed_quantity", "unknown_record_count", "remaining_quantity"):
        value = getattr(projection, field)
        if value is None and field in ("target_quantity", "remaining_quantity"):
            continue
        if not number(value, integer=True):
            fail("execution_projection_type", "Execution quantity/count has an invalid type.", field=field)
    if type(projection.quantity_complete) is not bool or type(projection.records_complete) is not bool:
        fail("execution_projection_type", "Execution flags must be actual booleans.")


def _validate_projection_collections(projection):
    for field in ("reports", "legacy_facts", "data_gaps"):
        value = getattr(projection, field)
        expected = ProductionReport if field == "reports" else dict
        if not isinstance(value, list) or not all(isinstance(item, expected) for item in value):
            fail("execution_projection_type", "Execution DTO collection has an invalid item type.", field=field)
    for field in ("plan_identity", "remaining_plan", "write_context"):
        value = getattr(projection, field)
        if value is not None and not isinstance(value, dict):
            fail("execution_projection_type", "Execution DTO context has an invalid type.", field=field)


def _validate_projection_times(projection):
    for field in ("first_actual_start", "confirmed_finish"):
        value = getattr(projection, field)
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                fail("execution_projection_type", "Execution DTO timestamp is invalid.", field=field)
            if parsed.tzinfo is not None:
                fail("execution_projection_type", "Execution timestamps must use factory-local time.", field=field)


def validate_projection_dto(projection):
    if not isinstance(projection, ExecutionProjection) or not public_ref(projection.operation_ref):
        fail("execution_projection_type", "Execution projection has an invalid DTO or permanent identity.")
    _validate_projection_quantities(projection)
    if (projection.execution_state not in ("unreported", "started", "partial", "paused", "exception", "complete")
            or projection.data_quality not in ("invalid", "legacy_incomplete", "incomplete", "complete")
            or projection.target_basis not in ("batch", "piece")
            or projection.completion_basis not in (None, "legacy_finish_event", "complete_reports")):
        fail("execution_projection_type", "Execution DTO contains an unknown state/basis.")
    _validate_projection_collections(projection)
    _validate_projection_times(projection)


def restore_execution_projections(payload):
    """Decode only complete Projection.to_dict() snapshots saved by run admission."""
    if not isinstance(payload, list) or len(payload) > MAX_OPERATIONS:
        fail("execution_snapshot_invalid", "Persisted execution snapshot must be a bounded list.")
    projections = []
    refs = set()
    for value in payload:
        row = _exact_fields(value, ExecutionProjection)
        if not isinstance(row["reports"], list):
            fail("execution_snapshot_invalid", "Persisted execution reports must be a list.")
        row["reports"] = [ProductionReport(**_exact_fields(report, ProductionReport)) for report in row["reports"]]
        projection = ExecutionProjection(**row)
        validate_projection_dto(projection)
        if not isinstance(projection.operation_ref, str) or projection.operation_ref in refs:
            fail("execution_snapshot_invalid", "Persisted execution identities are invalid or duplicated.")
        refs.add(projection.operation_ref)
        projections.append(projection)
    return projections

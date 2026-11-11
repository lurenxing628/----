"""Read-only piece proof shared by candidate publication and formal adoption.

Publication accepts a closed partial scope; adoption requires the whole scope.
Adoption repeats its proof in the caller's write transaction.
The caller still owns saved-source/raw equality, candidate/scenario identity,
baseline admission, request receipts and append-only official persistence.
This replaces the batch-only constraints/execution check for a piece scope; do
not also run the legacy flat-seq downstream check over independent pieces.
"""

from contextlib import contextmanager

from core.errors import AppError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.facts.piece_scope import block
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.zero_duration import PointEventError

from .candidate_adoption_constraints import (
    arrangement_calendar,
    evaluate_schedule_constraints,
    prepare_schedule_validation_context,
)
from .piece_adoption_facts import current_piece_scope


def validate_piece_candidate(conn, *, prepared, calendar, payload, context, failure_details=()):
    """Validate a candidate for publication while retaining every protected seed."""
    with _piece_validation_snapshot(conn):
        return _validate_piece(
            prepared,
            calendar,
            payload,
            purpose="publication",
            context=context,
            failure_details=failure_details,
        )


def validate_piece_adoption(conn, *, prepared, payload):
    """Validate formal adoption for a piece scope; raise a typed blocker without writes or repair.

    prepared uses the PreparedBusinessInput fields, including raw operations,
    dispositions with complete ExecutionProjection.to_dict(), original batches,
    calendar, seeds and full execution guards.
    No proof is inferred from the engine's completion flag.
    """
    with _piece_validation_snapshot(conn):
        context = _prepare_piece_validation_context(conn, prepared)
        calendar = arrangement_calendar(prepared, payload)
        return _validate_piece(
            prepared,
            calendar,
            payload,
            purpose="adoption",
            context=context,
        )


@contextmanager
def _piece_validation_snapshot(conn):
    try:
        with candidate_read_snapshot(conn):
            yield
    except PieceAdoptionBlocked:
        raise
    except (CandidateAdoptionBlocked, CandidateRunInputError, PointEventError) as exc:
        raise PieceAdoptionBlocked(exc.code, str(exc)) from exc
    except AppError as exc:
        code = (exc.details or {}).get("reason", "piece_constraint_unproven")
        raise PieceAdoptionBlocked(code, str(exc)) from exc


def prepare_piece_validation_context(conn, prepared):
    """Prepare shared proof inside the current snapshot, never across requests."""
    with _piece_validation_snapshot(conn):
        return _prepare_piece_validation_context(conn, prepared)


def _prepare_piece_validation_context(conn, prepared):
    scope = current_piece_scope(conn, prepared)
    context = prepare_schedule_validation_context(prepared)
    _material_deferrals(prepared, context["checks"], context["ops"], context["raw_batches"])
    scope_ids = {work.op_id for work in scope.operations}
    expected_ids = scope_ids - {row["op_id"] for row in prepared.dispositions if row["status"] == "skipped"}
    if prepared.allowed_op_ids != expected_ids:
        block("piece_scope_incomplete", "排产结果没有把共同工序和每个分件各排一次，本次没有采用。请回「执行排产」重新排一次。")
    context["scope_ids"] = scope_ids
    return context


def _validate_piece(prepared, calendar, payload, *, purpose, context, failure_details=()):
    outcome = evaluate_schedule_constraints(
        prepared,
        calendar,
        payload,
        purpose=purpose,
        context=context,
        failure_details=failure_details,
    )
    _payload(prepared, outcome.validated_payload, context, purpose=purpose)
    if outcome.issues:
        first = outcome.issues[0]
        block(first["code"], first["message"])
    return outcome


def _payload(prepared, payload, context, *, purpose):
    if purpose == "adoption":
        adoption_ids = context["scope_ids"] - material_deferred_ids(prepared.dispositions, prepared.settings)
        if payload.scheduled_op_ids != adoption_ids:
            block("piece_scope_incomplete", "排产结果没有把共同工序和每个分件各排一次，本次没有采用。请回「执行排产」重新排一次。")


def _material_deferrals(prepared, checks, ops, raw_batches):
    deferred = material_deferred_ids(prepared.dispositions, prepared.settings)
    current = []
    for op_id in deferred:
        op = ops[op_id]
        batch, raw = raw_batches[op.batch_id], vars(op)
        if checks.fields(batch, raw):
            block("piece_resource_invalid", "待料工序的原始资料不完整，请核对后重新排产。")
        problems, _day = checks.operation_readiness(batch, raw, prepared.settings)
        current.append({"op_id": op_id, "status": "skipped", "issues": problems})
    if material_deferred_ids(current, prepared.settings) != deferred:
        block("piece_scope_incomplete", "被暂缓的工序没有当前缺料依据，请重新排产。")

"""Strict raw-row validation and exact-scope classification for candidate runs."""

from collections import defaultdict
from dataclasses import fields, replace
from typing import NoReturn

from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.workbench_preflight import issue
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.preflight_checks import PreflightChecks, number, stored_date
from core.services.workbench.preflight_dependencies import link_predecessors

_BATCH_STATES = {"pending", "scheduled", "processing", "completed", "cancelled"}
_OP_STATES = {"pending", "scheduled", "processing", "completed", "skipped"}


def fail(reason, message, **context) -> NoReturn:
    raise CandidateRunInputError(reason, message, issues=[issue(reason, message, **context)])


def _required_text(value, field):
    if not isinstance(value, str) or not value or value.strip() != value:
        fail("invalid_stored_text", "Stored identity/text is missing or not canonical.", field=field)


def _optional_text(value, field):
    if value is not None:
        _required_text(value, field)


def batch_model(row):
    for key in ("batch_id", "part_no"):
        _required_text(row[key], key)
    if row["status"] not in _BATCH_STATES or row["priority"] not in ("normal", "urgent", "critical"):
        fail("invalid_batch_state", "Batch status or priority is unknown.", batch_id=row["batch_id"])
    if row["ready_status"] not in ("yes", "no", "partial"):
        fail("invalid_ready_status", "Batch readiness is unknown.", batch_id=row["batch_id"])
    if not number(row["quantity"], integer=True):
        fail("quantity_unknown", "Unknown quantity is not zero.", batch_id=row["batch_id"])
    for key in ("due_date", "ready_date"):
        if row[key] is not None and stored_date(row[key]) is None:
            fail("invalid_batch_date", "Stored batch date is invalid.", batch_id=row["batch_id"], field=key)
    return Batch(**{item.name: row[item.name] for item in fields(Batch)})


def operation_model(row):
    if not number(row["id"], integer=True, positive=True) or not number(row["seq"], integer=True, positive=True):
        fail("invalid_operation_identity", "Operation id and sequence must be positive integers.")
    for key in ("op_code", "batch_id", "op_type_id", "op_type_name"):
        _required_text(row[key], key)
    for key in ("piece_id", "machine_id", "operator_id", "supplier_id"):
        _optional_text(row[key], key)
    if row["status"] not in _OP_STATES or row["source"] not in ("internal", "external"):
        fail("invalid_operation_state", "Operation status or source is unknown.", op_id=row["id"])
    for key in ("setup_hours", "unit_hours"):
        if not number(row[key]):
            fail("hours_missing", "Unknown hours cannot be converted to zero.", op_id=row["id"], field=key)
    if row["ext_days"] is not None and not number(row["ext_days"], positive=True):
        fail("external_days_invalid", "Explicit external lead time must be positive.", op_id=row["id"])
    return BatchOperation(**{item.name: row[item.name] for item in fields(BatchOperation)})


def validate_single_chain(operations):
    by_batch = defaultdict(list)
    for op in operations:
        by_batch[op.batch_id].append(op)
    for batch_id, chain in by_batch.items():
        if len({op.piece_id for op in chain}) > 1:
            fail("piece_precedence_adapter_unavailable", "The current candidate graph only supports one chain per batch.",
                 batch_id=batch_id)
        if len({op.seq for op in chain}) != len(chain):
            fail("dependency_ambiguous", "Operation sequences are duplicated within a chain.", batch_id=batch_id)


def classify_rows(facts, settings, raw_batches, operations, projections, guarded_ids, *, piece_scope=None):
    checks = PreflightChecks(facts.tables)
    raw_by_id = {row["id"]: row for row in facts.tables["BatchOperations"]}
    batches = {row["batch_id"]: row for row in raw_batches}
    rows = []
    for op in operations:
        raw, batch = raw_by_id[op.id], batches[op.batch_id]
        ref = facts.operation_ref(raw)
        projection = projections[ref]
        status, reasons = _classification(checks, batch, raw, projection, settings, guarded_ids)
        rows.append({"operation_ref": ref, "op_id": op.id, "batch_ref": batch["ref"], "batch_id": op.batch_id,
                     "piece_id": op.piece_id, "sequence": op.seq, "status": status, "issues": reasons,
                     "predecessor_refs": [], "execution": projection.to_dict()})
    _link_dispositions(rows, batches, piece_scope)
    blocked = [row for row in rows if row["status"] == "blocked"]
    if blocked:
        raise CandidateRunInputError("input_blocked", "Candidate input has unresolved data gaps.", issues=blocked)
    eligible = {row["op_id"] for row in rows if row["status"] in ("eligible", "auto_assign_required")}
    if not eligible:
        raise CandidateRunInputError("no_eligible_operations", "No operations remain in the exact requested scope.", issues=rows)
    mutable = [_assignable_operation(op, checks.resources(raw_by_id[op.id])) for op in operations if op.id in eligible]
    return rows, mutable


def _link_dispositions(rows, batches, piece_scope):
    by_batch = defaultdict(list)
    for row in rows:
        by_batch[row["batch_id"]].append(row)
    if piece_scope is None:
        for chain in by_batch.values():
            link_predecessors(chain)
    else:
        by_id = {row["op_id"]: row for row in rows}
        for work in piece_scope.operations:
            by_id[work.op_id]["predecessor_refs"] = [by_id[key]["operation_ref"] for key in work.predecessor_op_ids]
        if any(row["status"] not in ("eligible", "auto_assign_required", "protected") for row in rows):
            fail("piece_scope_incomplete", "Every common and piece operation must be included or exactly protected.")
    for batch_id, batch in batches.items():
        if batch_id not in by_batch:
            fail("route_missing", "Selected batch has no operations.", batch_ref=batch["ref"])


def _classification(checks, batch, op, projection, settings, guarded_ids):
    if op["id"] in guarded_ids:
        return "protected", [issue("actuals_preserved", "Original execution is retained by the shared ledger guard.")]
    if (op["status"] in ("processing", "completed") or projection.execution_state != "unreported"
            or projection.reports or projection.legacy_facts or projection.first_actual_start or projection.confirmed_finish):
        return "blocked", [issue("execution_protection_unresolved", "Execution marker has no representable shared protection.")]
    gaps = checks.fields(batch, op)
    if projection.data_quality == "invalid":
        gaps.extend(projection.data_gaps or [issue("execution_invalid", "Execution projection has invalid data quality.")])
    if gaps:
        return "blocked", gaps
    return _mutable_classification(checks, batch, op, settings)


def _mutable_classification(checks, batch, op, settings):
    if op["status"] == "skipped" or batch["status"] in ("completed", "cancelled"):
        return "skipped", [issue("closed", "Closed batch or explicitly skipped operation.")]
    if batch["quantity"] == 0 and op["source"] != "internal":
        return "skipped", [issue("zero_quantity", "External work has zero target quantity.")]
    ready = checks.readiness(batch, settings["ready_check"])
    if ready:
        return "skipped", ready
    ready_day = stored_date(batch["ready_date"])
    if settings["ready_check"] and ready_day is not None and ready_day > settings["end_date"]:
        return "skipped", [issue("ready_after_window", "Ready date is after the requested window.")]
    resources = checks.resources(op)
    if resources:
        return ("auto_assign_required" if settings["missing_resource_policy"] == "auto_assign" else "skipped"), resources
    return "eligible", []


def _assignable_operation(op, gaps):
    if not gaps:
        return op
    codes = {row["code"] for row in gaps}
    return replace(op, machine_id=None if "machine_missing" in codes else op.machine_id,
                   operator_id=None if codes.intersection({"operator_missing", "operator_skill_missing",
                                                           "machine_authorization_missing"}) else op.operator_id)

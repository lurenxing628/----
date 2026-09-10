"""Bind complete prepared scope to current raw rows and existing permanent refs."""

from dataclasses import asdict

from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .piece_adoption_scope import block, build_piece_adoption_scope
from .preflight_checks import stored_date
from .run_input_rows import batch_model, operation_model


def current_piece_scope(conn, prepared):
    ids = prepared.normalized_batch_ids
    if not ids or len(ids) != len(set(ids)) or set(ids) != set(prepared.batches):
        block("piece_scope_incomplete", "Prepared batch scope is empty, duplicated or inconsistent.")
    batches, operations, batch_refs = {}, [], {}
    for batch_id in ids:
        row = conn.execute("SELECT * FROM Batches WHERE batch_id=?", (batch_id,)).fetchone()
        if row is None:
            block("piece_identity_changed", "An original batch no longer exists.")
        batches[batch_id] = batch_model(dict(row))
        ref = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 "
                           "AND entity_key=?", (batch_id,)).fetchall()
        if len(ref) != 1:
            block("piece_identity_changed", "An original batch lacks its unique permanent identity.")
        batch_refs[batch_id] = ref[0][0]
        operations.extend(operation_model(dict(row)) for row in conn.execute(
            "SELECT * FROM BatchOperations WHERE batch_id=? ORDER BY id", (batch_id,)))
    scope = build_piece_adoption_scope(operations, batches)
    if not any(op.piece_id is not None for op in operations):
        block("piece_scope_required", "This helper requires a scope containing actual piece operations.")
    if sorted(prepared.normalized_input["batch_refs"]) != sorted(batch_refs.values()):
        block("piece_identity_changed", "The accepted batch identities no longer match the complete scope.")
    _require_original_work(prepared, operations, batches)
    refs = WorkbenchPlanIdentityRepository(conn).get_operation_refs(op.id for op in operations)
    _dispositions(prepared, scope, refs, batch_refs)
    return scope, refs


def _require_original_work(prepared, operations, batches):
    for op in prepared.operations:
        operation_model(asdict(op))
    accepted = {key: _batch_facts(value) for key, value in prepared.batches.items()}
    current = {key: _batch_facts(value) for key, value in batches.items()}
    if (len(prepared.operations) != len(operations)
            or {op.id: asdict(op) for op in prepared.operations} != {op.id: asdict(op) for op in operations}
            or accepted != current):
        block("piece_raw_changed", "Prepared work differs from the current original raw operations or quantities.")


def _batch_facts(batch):
    raw = asdict(batch)
    batch_model(raw)
    # SQLite DATE objects and saved JSON dates share only this validated form.
    for key in ("due_date", "ready_date"):
        if raw[key] is not None:
            raw[key] = stored_date(raw[key])
    return raw


def _dispositions(prepared, scope, refs, batch_refs):
    rows = prepared.dispositions
    if any(type(row["op_id"]) is not int or type(row["sequence"]) is not int for row in rows):
        block("piece_identity_invalid", "Disposition operation IDs and sequences must retain integer identity types.")
    by_id = {row["op_id"]: row for row in rows}
    if len(rows) != len(by_id) or set(by_id) != set(refs):
        block("piece_scope_incomplete", "Prepared dispositions must cover every current operation exactly once.")
    for work in scope.operations:
        row = by_id[work.op_id]
        expected = {"operation_ref": refs[work.op_id], "batch_ref": batch_refs[work.batch_id],
                    "batch_id": work.batch_id, "piece_id": work.piece_id, "sequence": work.sequence}
        if any(row[key] != value for key, value in expected.items()):
            block("piece_identity_changed", "A disposition no longer refers to its original piece operation.")
        predecessors = row["predecessor_refs"]
        if (type(predecessors) is not list or len(predecessors) != len(set(predecessors))
                or set(predecessors) != {refs[op_id] for op_id in work.predecessor_op_ids}):
            block("piece_dependency_mismatch", "Prepared dependencies omit common work or cross independent pieces.")
        if row["status"] not in ("eligible", "auto_assign_required", "protected"):
            block("piece_scope_incomplete", "Excluded or blocked work cannot be silently omitted from adoption.")

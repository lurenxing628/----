"""Bind complete prepared scope to current raw rows and existing permanent refs."""


from core.infrastructure.read_evidence import verified_read
from core.services.workbench.facts.piece_scope import block, build_piece_adoption_scope
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids


def current_piece_scope(conn, prepared):
    return verified_read(conn, ("piece_scope", id(prepared)), lambda: _current_piece_scope(conn, prepared))


def _current_piece_scope(conn, prepared):
    ids = prepared.normalized_batch_ids
    if not ids or len(ids) != len(set(ids)) or set(ids) != set(prepared.batches):
        block("piece_scope_incomplete", "这次排产的批次范围为空或有重复，本次没有采用。请回「执行排产」重新排一次。")
    facts = prepared.preflight_facts
    batches, operations = prepared.batches, prepared.operations
    batch_refs = {batch_id: facts.refs.get(("batch", batch_id)) for batch_id in ids}
    if any(ref is None for ref in batch_refs.values()):
        block("piece_identity_changed", "有批次缺少唯一编号，本次没有采用。请刷新后重新排产。")
    scope = build_piece_adoption_scope(operations, batches)
    if not any(op.piece_id is not None for op in operations):
        block("piece_scope_required", "本批工序现在没有分件，不能按分件采用。请回「执行排产」重新排一次。")
    if sorted(prepared.normalized_input["batch_refs"]) != sorted(batch_refs.values()):
        block("piece_identity_changed", "排产时的批次范围和现在的不一致，本次没有采用。请回「执行排产」重新排一次。")
    refs = {op.id: facts.operation_refs[op.id] for op in operations}
    _dispositions(prepared, scope, refs, batch_refs)
    return scope, refs


def _dispositions(prepared, scope, refs, batch_refs):
    rows = prepared.dispositions
    if any(type(row["op_id"]) is not int or type(row["sequence"]) is not int for row in rows):
        block("piece_identity_invalid", "处置记录里的工序编号或顺序号类型不对，本次没有采用。请回「执行排产」重新排一次。")
    by_id = {row["op_id"]: row for row in rows}
    deferred = material_deferred_ids(rows, prepared.normalized_input)
    if len(rows) != len(by_id) or set(by_id) != set(refs):
        block("piece_scope_incomplete", "处置记录没有覆盖当前每一道工序，本次没有采用。请回「执行排产」重新排一次。")
    for work in scope.operations:
        row = by_id[work.op_id]
        expected = {"operation_ref": refs[work.op_id], "batch_ref": batch_refs[work.batch_id],
                    "batch_id": work.batch_id, "piece_id": work.piece_id, "sequence": work.sequence}
        if any(row[key] != value for key, value in expected.items()):
            block("piece_identity_changed", "处置记录已经对不上原来的分件工序，本次没有采用。请回「执行排产」重新排一次。")
        _require_predecessors(row["predecessor_refs"], work, refs)
        if row["status"] not in ("eligible", "auto_assign_required", "protected") and work.op_id not in deferred:
            block("piece_scope_incomplete", "有工序缺资料被排除在外，系统不会默默跳过，本次没有采用。请先在排产检查里补齐资料。")


def _require_predecessors(predecessors, work, refs):
    if (type(predecessors) is not list or len(predecessors) != len(set(predecessors))
            or set(predecessors) != {refs[op_id] for op_id in work.predecessor_op_ids}):
        block("piece_dependency_mismatch", "工序先后关系漏了共同工序，或者串到了别的分件，本次没有采用。请回「执行排产」重新排一次。")

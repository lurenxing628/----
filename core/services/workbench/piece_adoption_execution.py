"""Reuse full ledger protection, with piece-aware precedence owned by the caller.

The legacy persistence guard's flat same-batch seq comparison is deliberately
not used here. Fresh shared guardrails retain exact actual intervals/resources,
all revisions, the whole official snapshot and unselected resource reservations.
"""

from core.services.scheduler.run.schedule_execution_guardrails import _collect_execution_guardrails
from core.services.scheduler.run.schedule_execution_persistence_guard import _validate_unselected_resource_overlap
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
from core.services.workbench.execution_ledger import ExecutionLedgerService

from .piece_adoption_scope import block
from .run_input_projection_codec import restore_execution_projections

_FIELDS = ("start_time", "end_time", "machine_id", "operator_id", "source")


def _stable_projection(projection):
    value = projection.to_dict()
    value.pop("write_context")
    value.pop("comparison_task_ref")
    for report in value["reports"]:
        report.pop("write_context")
    return value


def validate_piece_execution(svc, prepared, payload, scope, refs):
    if svc.history_repo.get_latest_version() != prepared.prev_version:
        block("piece_baseline_changed", "正式计划在这次排产之后又变了，本次没有采用。请刷新后重新排产。")
    ledger = ExecutionLedgerService(svc.conn)
    current = {item.operation_ref: item for item in ledger.project_operations(list(refs.values()))}
    supplied = restore_execution_projections([row["execution"] for row in prepared.dispositions])
    if {item.operation_ref: _stable_projection(item) for item in supplied} != {
        ref: _stable_projection(item) for ref, item in current.items()
    }:
        block("piece_execution_changed", "排产时读到的报工记录和现在的不一致，本次没有采用。请刷新现场记录后重新排产。")
    _quantities(scope, refs, current)
    facts, actual_seeds = _current_protection(svc, prepared)
    protected = _protected_arrangements(svc, prepared, payload, actual_seeds)
    _validate_unselected_resource_overlap(svc, payload=payload, execution_facts=facts,
                                        operations=prepared.operations)
    return protected


def _current_protection(svc, prepared):
    facts, fixed, completed, actual_seeds, revisions, snapshot = _collect_execution_guardrails(
        svc, prepared.operations, prev_version=prepared.prev_version)
    if (prepared.execution_facts != facts or prepared.execution_fixed_op_ids != fixed
            or prepared.execution_completed_op_ids != completed
            or prepared.execution_guard_state_revisions != revisions
            or prepared.execution_snapshot_revision != snapshot.revision
            or list(prepared.execution_snapshot_op_ids) != list(snapshot.op_ids)
            or prepared.execution_snapshot_op_count != snapshot.op_count
            or prepared.execution_seed_results != actual_seeds):
        block("piece_execution_protection_changed", "已开工工序的保护数据缺失或已过期，本次没有采用。请刷新后重新排产。")
    return facts, actual_seeds


def _protected_arrangements(svc, prepared, payload, actual_seeds):
    rows = {row.op_id: row for row in payload.schedule_rows}
    seeds = prepared.seed_results
    by_seed = {seed["op_id"]: seed for seed in seeds}
    actual = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    protected = prepared.frozen_op_ids | actual
    if len(seeds) != len(by_seed) or set(by_seed) != protected or not protected <= set(rows):
        block("piece_protected_seed_missing", "每道受保护工序都要保留原来的一条安排，现在对不上，本次没有采用。请回「执行排产」重新排一次。")
    for seed in seeds + actual_seeds:
        if any(getattr(rows[seed["op_id"]], key) != seed[key] for key in _FIELDS):
            block("piece_protected_seed_changed", "已开工或沿用的工序时间、设备、人员被改动了，本次没有采用。请回「执行排产」重新排一次。")
    _original_locks(svc, prepared, rows, actual, protected)
    return protected


def _quantities(scope, refs, projections):
    for work in scope.operations:
        item = projections[refs[work.op_id]]
        basis = "batch" if work.piece_id is None else "piece"
        if item.target_basis != basis or item.target_quantity != work.target_quantity:
            block("piece_quantity_unknown", "报工记录的目标数量和共同工序或分件工序对不上，本次没有采用。请到现场记录核对后重新排产。")
        if (item.data_quality == "invalid" or item.unknown_record_count
                or item.known_completed_quantity > work.target_quantity or item.remaining_quantity is None
                or item.remaining_quantity != work.target_quantity - item.known_completed_quantity):
            block("piece_execution_quantity_unproven", "报工数量缺失、互相矛盾或超过目标量，本次没有采用。请到现场记录核对后重新排产。")
        if item.execution_state == "complete" and (
            not item.quantity_complete or item.known_completed_quantity != work.target_quantity
        ):
            block("piece_execution_quantity_unproven", "有工序报了完工却没有确切完工数量，证明不了分件全部做完，本次没有采用。请到现场记录补齐完工数量。")


def _original_locks(svc, prepared, rows, actual, protected):
    latest = _latest_plan_rows(svc, prepared.prev_version)
    if not set(latest) <= set(rows):
        block("official_scope_not_covered", "候选方案漏掉了正式计划里已有的部分工序，本次没有采用。请回「执行排产」重新排一次。")
    for op_id, identity in latest.items():
        old = svc.conn.execute("SELECT * FROM Schedule WHERE id=?", (identity["schedule_id"],)).fetchone()
        if old["lock_status"] not in ("locked", "unlocked"):
            block("piece_lock_invalid", "原计划里有工序的锁定状态读不出来，本次没有采用。请刷新后重新排产。")
        if op_id in actual:
            continue
        if old["lock_status"] == "locked" and op_id not in protected:
            block("piece_inherited_lock_missing", "原计划里已锁定的工序在新版本里没了锁定，本次没有采用。请回「执行排产」重新排一次。")
        if op_id in protected:
            row = rows[op_id]
            if (row.start_time != svc._normalize_datetime(old["start_time"])
                    or row.end_time != svc._normalize_datetime(old["end_time"])
                    or row.machine_id != old["machine_id"] or row.operator_id != old["operator_id"]):
                block("piece_inherited_lock_changed", "锁定工序的时间、设备或人员和原正式计划不一致，本次没有采用。请回「执行排产」重新排一次。")
    if protected - actual - set(latest):
        block("piece_inherited_lock_missing", "有锁定工序在原正式计划里找不到安排，本次没有采用。请刷新后重新排产。")

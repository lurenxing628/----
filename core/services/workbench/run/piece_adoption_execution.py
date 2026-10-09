"""Reuse full ledger protection, with piece-aware precedence owned by the caller.

The legacy persistence guard's flat same-batch seq comparison is deliberately
not used here. Fresh shared guardrails retain exact actual intervals/resources,
all revisions, the whole official snapshot and unselected resource reservations.
"""

from core.infrastructure.read_evidence import verified_read
from core.services.scheduler.run.schedule_execution_guardrails import _collect_execution_guardrails
from core.services.scheduler.run.schedule_execution_persistence_guard import _validate_unselected_resource_overlap
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
from core.services.scheduler.run.schedule_input_seed_metadata import MERGED_EXECUTION_GROUP_SOURCE
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.piece_scope import block
from core.services.workbench.facts.run_input_codec import restore_execution_projections
from data.repositories.workbench_piece_adoption_repo import WorkbenchPieceAdoptionRepository

_FIELDS = ("start_time", "end_time", "machine_id", "operator_id", "source")


def _stable_projection(projection):
    value = projection.to_dict()
    value.pop("write_context")
    value.pop("comparison_task_ref")
    for report in value["reports"]:
        report.pop("write_context")
    return value


def validate_piece_execution(svc, prepared, payload, scope, refs):
    facts, actual_seeds = verified_read(svc.conn, ("piece_execution", id(prepared)),
        lambda: _execution_inputs(svc, prepared, scope, refs))
    protected = _protected_arrangements(svc, prepared, payload, actual_seeds)
    _validate_unselected_resource_overlap(svc, payload=payload, execution_facts=facts,
                                        operations=prepared.operations)
    return protected


def _execution_inputs(svc, prepared, scope, refs):
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
    return _current_protection(svc, prepared)


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
    derived = {seed["op_id"] for seed in seeds if seed.get("seed_source") == MERGED_EXECUTION_GROUP_SOURCE}
    _original_arrangements(svc, prepared, rows, actual, protected, derived)
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


def _original_arrangements(svc, prepared, rows, actual, protected, derived):
    """候选要覆盖正式计划里已有的全部工序；按不重排时段保留的工序要和正式计划里的原安排一模一样。
    正式计划里的锁定标记不再起作用，这里不再按它核对。"""
    latest = _latest_plan_rows(svc, prepared.prev_version)
    if not set(latest) <= set(rows):
        block("official_scope_not_covered", "候选方案漏掉了正式计划里已有的部分工序，本次没有采用。请回「执行排产」重新排一次。")
    official = WorkbenchPieceAdoptionRepository(svc.conn)
    for op_id, identity in latest.items():
        if op_id in actual or op_id not in protected or op_id in derived:
            continue
        old = official.get_schedule_row(identity["schedule_id"])
        row = rows[op_id]
        if old is None or (row.start_time, row.end_time, row.machine_id, row.operator_id) != (
                svc._normalize_datetime(old["start_time"]), svc._normalize_datetime(old["end_time"]),
                old["machine_id"], old["operator_id"]):
            block("piece_held_arrangement_changed", "保持原安排的工序的时间、设备或人员和原正式计划不一致，本次没有采用。请回「执行排产」重新排一次。")
    if protected - actual - derived - set(latest):
        block("piece_held_arrangement_missing", "有保持原安排的工序在原正式计划里找不到安排，本次没有采用。请刷新后重新排产。")

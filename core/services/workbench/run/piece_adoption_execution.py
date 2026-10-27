"""Reuse full ledger protection, with piece-aware precedence owned by the caller.

The legacy persistence guard's flat same-batch seq comparison is deliberately
not used here. Fresh shared guardrails retain exact actual intervals/resources,
all revisions and the whole official snapshot.
"""

from core.services.scheduler.run.schedule_input_seed_metadata import MERGED_EXECUTION_GROUP_SOURCE
from core.services.workbench.facts.piece_scope import block
from core.shared.local_datetime import parse_local_datetime as parse_dt


def validate_piece_execution(prepared, payload, *, purpose):
    _protected_arrangements(prepared, payload, purpose=purpose)


def _protected_arrangements(prepared, payload, *, purpose):
    rows = {row.op_id: row for row in payload.schedule_rows}
    seeds = prepared.seed_results
    by_seed = {seed["op_id"]: seed for seed in seeds}
    actual = prepared.execution_completed_op_ids
    protected = prepared.frozen_op_ids | actual
    if len(seeds) != len(by_seed) or set(by_seed) != protected or not protected <= set(rows):
        block("piece_protected_seed_missing", "每道受保护工序都要保留原来的一条安排，现在对不上，本次没有采用。请回「执行排产」重新排一次。")
    for seed in seeds:
        row = rows[seed["op_id"]]
        if (row.start_time, row.end_time, row.machine_id, row.operator_id, row.source) != (
                seed["start_time"], seed["end_time"], seed["machine_id"], seed["operator_id"], seed["source"]):
            block("piece_protected_seed_changed", "已开工或沿用的工序时间、设备、人员被改动了，本次没有采用。请回「执行排产」重新排一次。")
    derived = {seed["op_id"] for seed in seeds if seed.get("seed_source") == MERGED_EXECUTION_GROUP_SOURCE}
    _original_arrangements(prepared, rows, actual, protected, derived, purpose=purpose)


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


def _original_arrangements(prepared, rows, actual, protected, derived, *, purpose):
    """正式采用覆盖全部原正式工序；每份候选都保持受保护的原安排。"""
    latest = prepared.latest_plan_rows
    if purpose == "adoption" and not set(latest) <= set(rows):
        block("official_scope_not_covered", "候选方案漏掉了正式计划里已有的部分工序，本次没有采用。请回「执行排产」重新排一次。")
    for op_id, identity in latest.items():
        if op_id in actual or op_id not in protected or op_id in derived:
            continue
        old = identity
        row = rows[op_id]
        if old is None or (row.start_time, row.end_time, row.machine_id, row.operator_id) != (
                parse_dt(old["start_time"]), parse_dt(old["end_time"]),
                old["machine_id"], old["operator_id"]):
            block("piece_held_arrangement_changed", "保持原安排的工序的时间、设备或人员和原正式计划不一致，本次没有采用。请回「执行排产」重新排一次。")
    if protected - actual - derived - set(latest):
        block("piece_held_arrangement_missing", "有保持原安排的工序在原正式计划里找不到安排，本次没有采用。请刷新后重新排产。")

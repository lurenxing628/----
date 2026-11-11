"""Validate every real candidate, including original seeds and chain closure."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.workbench.facts.run_input_rows import fail
from core.services.workbench.facts.zero_duration import candidate_point_validator

from .schedule_row_constraints import PredecessorNode, iter_predecessor_violations

_CHAIN_FAILURES = {
    "predecessor_missing": (
        "candidate_predecessor_missing",
        "这次排产漏掉了前道工序，只排了后道，结果没有保存。请把整条工序链一起选上再排。",
    ),
    "merged_group_split": (
        "candidate_merged_group_split",
        "合并送出的外协工序被排到了不同时段，结果没有保存。请改成分别送出，或者联系维护人员。",
    ),
    "precedence_violation": (
        "candidate_precedence_violation",
        "这次排产让后道工序比前道还早开工，结果没有保存。请刷新重试；仍不行请联系维护人员。",
    ),
}


def prepare_candidate_validation_context(schedule_input):
    return {
        "point_validator": candidate_point_validator(schedule_input),
        "seeds": {row["op_id"]: row for row in schedule_input.seeds.seed_results},
        "end": datetime.combine(schedule_input.end_date + timedelta(days=1), datetime.min.time()),
        "algo_by_id": {op.id: op for op in schedule_input.algo_ops},
    }


def validate_candidate(schedule_input, results, *, failure_details=(), context=None):
    if context is None:
        context = prepare_candidate_validation_context(schedule_input)
    payload = build_validated_schedule_payload(
        results,
        allowed_op_ids=schedule_input.allowed_op_ids,
        operations=schedule_input.operations,
        missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
        failure_details=failure_details,
        point_validator=context["point_validator"],
        operation_sources=schedule_input.operation_sources,
    )
    by_id = {row.op_id: row for row in payload.schedule_rows}
    seeds = context["seeds"]
    for op_id, seed in seeds.items():
        row = by_id.get(op_id)
        if row is None or (row.start_time, row.end_time, row.machine_id, row.operator_id, row.source) != (
            seed["start_time"],
            seed["end_time"],
            seed["machine_id"],
            seed["operator_id"],
            seed["source"],
        ):
            fail("protected_seed_changed", "这次排产改动或漏掉了要保持原安排的工序，结果没有保存。请重新做排产检查后再排。", op_id=op_id)
    end = context["end"]
    for row in by_id.values():
        if row.op_id not in seeds and (
            row.start_time < schedule_input.start or row.end_time > end or row.start_time == end
        ):
            fail("candidate_outside_window", "这次排产把工序排到了选定的日期范围之外，结果没有保存。请放宽排产起止日期后重试。", op_id=row.op_id)
    _validate_chain(schedule_input, by_id, context["algo_by_id"])
    return payload


def _validate_chain(schedule_input, by_id, algo_by_id):
    nodes = []
    for item in schedule_input.dispositions:
        row = by_id.get(item["op_id"])
        if row is None:
            continue
        algo = algo_by_id[row.op_id]
        merged_key = (
            (algo.batch_id, algo.ext_group_id, algo.piece_id)
            if algo.source == "external"
            and algo.ext_merge_mode == "merged"
            and algo.ext_group_id is not None
            else None
        )
        span = (row.start_time, row.end_time)
        nodes.append(
            PredecessorNode(
                key=item["operation_ref"],
                op_id=row.op_id,
                predecessor_keys=item["predecessor_refs"],
                span=span,
                cycle_token=span,
                merged_group_key=merged_key,
            )
        )
    violation = next(iter_predecessor_violations(nodes, outside_completed_ends={}), None)
    if violation is not None:
        code, message = _CHAIN_FAILURES[violation.kind]
        fail(code, message, op_id=violation.op_id)

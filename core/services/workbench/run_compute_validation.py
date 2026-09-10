"""Validate every real candidate, including original seeds and chain closure."""

from datetime import datetime, timedelta

from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload

from .run_input_rows import fail
from .zero_duration import candidate_point_validator


def validate_candidate(schedule_input, results, errors):
    payload = build_validated_schedule_payload(
        results, allowed_op_ids=schedule_input.schedule_output_allowed_op_ids,
        operations=schedule_input.payload_validation_operations,
        missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
        schedule_errors=errors,
        point_validator=candidate_point_validator(schedule_input),
    )
    by_id = {row.op_id: row for row in payload.schedule_rows}
    seeds = {row["op_id"]: row for row in schedule_input.seed_results}
    for op_id, seed in seeds.items():
        row = by_id.get(op_id)
        if row is None or any(getattr(row, field) != seed[field] for field in (
            "start_time", "end_time", "machine_id", "operator_id", "source",
        )):
            fail("protected_seed_changed", "Candidate changed or omitted an original protected seed.", op_id=op_id)
    end = datetime.combine(schedule_input.end_date_norm + timedelta(days=1), datetime.min.time())
    for row in by_id.values():
        if row.op_id not in seeds and (row.start_time < schedule_input.start_dt_norm or row.end_time > end
                                      or row.start_time == end):
            fail("candidate_outside_window", "Candidate schedules mutable work outside the requested window.", op_id=row.op_id)
    _validate_chain(schedule_input, by_id)
    return payload


def _same_merged_group(left, right, algo_by_id):
    first, second = algo_by_id.get(left), algo_by_id.get(right)
    return bool(first and second and first.source == second.source == "external"
                and first.ext_merge_mode == second.ext_merge_mode == "merged"
                and first.piece_id == second.piece_id
                and first.batch_id == second.batch_id and first.ext_group_id == second.ext_group_id)


def _validate_chain(schedule_input, by_id):
    ids_by_ref = {row["operation_ref"]: row["op_id"] for row in schedule_input.dispositions}
    algo_by_id = {op.id: op for op in schedule_input.algo_ops}
    for item in schedule_input.dispositions:
        row = by_id.get(item["op_id"])
        if row is None:
            continue
        for ref in item["predecessor_refs"]:
            previous_id = ids_by_ref[ref]
            previous = by_id.get(previous_id)
            if previous is None:
                fail("candidate_predecessor_missing", "Candidate contains a successor without its predecessor.", op_id=row.op_id)
            if _same_merged_group(previous_id, row.op_id, algo_by_id):
                if (row.start_time, row.end_time) != (previous.start_time, previous.end_time):
                    fail("candidate_merged_group_split", "Merged external operations no longer share their interval.", op_id=row.op_id)
            elif row.start_time < previous.end_time:
                fail("candidate_precedence_violation", "Candidate starts before its predecessor finishes.", op_id=row.op_id)

"""Audit serialized SGS schedules, including calendar work and full operation coverage."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from core.algorithms.evaluation import compute_metrics, objective_score

RESULT_FIELDS = ("op_id", "op_code", "batch_id", "seq", "source", "machine_id", "operator_id",
                 "op_type_name", "start_time", "end_time")


def schedule_payload(candidate):
    return {
        "failed_ops": candidate["summary"].failed_ops,
        "objective_score": list(candidate["score"]),
        "schedule": [{key: _result_value(result, key) for key in RESULT_FIELDS} for result in candidate["results"]],
    }


def _result_value(result, key):
    value = getattr(result, key)
    return value.isoformat() if isinstance(value, datetime) else value


def audit_schedule(payload, env, objective):
    if not isinstance(payload, dict) or set(payload) != {"failed_ops", "objective_score", "schedule"}:
        raise ValueError("schedule metadata mismatch")
    if type(payload["failed_ops"]) is not int or payload["failed_ops"] != 0:
        raise ValueError("failed_ops: fixed feasible fixtures must schedule every operation")
    if not isinstance(payload["schedule"], list):
        raise ValueError("schedule must be a list")
    operations = {op.id: op for op in env["operations"]}
    results = {}
    for row in payload["schedule"]:
        if not isinstance(row, dict) or set(row) != set(RESULT_FIELDS):
            raise ValueError("unknown or missing schedule fields")
        op_id = row["op_id"]
        if type(op_id) is not int or op_id not in operations or op_id in results:
            raise ValueError("duplicate or unknown operation")
        op = operations[op_id]
        for key in ("op_code", "batch_id", "seq", "source", "op_type_name"):
            if type(row[key]) is not type(getattr(op, key)) or row[key] != getattr(op, key):
                raise ValueError("operation identity mismatch: " + key)
        result = SimpleNamespace(**row)
        result.start_time = datetime.fromisoformat(row["start_time"])
        result.end_time = datetime.fromisoformat(row["end_time"])
        _audit_slot(result, op, env)
        results[op_id] = result
    if set(results) != set(operations):
        raise ValueError("missing operations")
    for op_id, predecessors in env["graph"]["predecessor_op_ids_by_op_id"].items():
        if any(results[prev].end_time > results[op_id].start_time for prev in predecessors):
            raise ValueError("precedence overlap")
    for resource in ("machine_id", "operator_id"):
        _audit_resource_overlap(list(results.values()), resource)
    score = [0.0] + list(objective_score(objective, compute_metrics(list(results.values()), env["batches"])))
    if payload["objective_score"] != score:
        raise ValueError("objective_score does not match serialized schedule")
    return score


def _audit_slot(result, op, env):
    start, end = result.start_time, result.end_time
    if start.tzinfo is not None or end.tzinfo is not None or start < datetime.fromisoformat(env["data"]["start_dt"]) or end <= start:
        raise ValueError("invalid schedule interval")
    pool = env["resource_pool"]
    if pool:
        if result.machine_id not in pool["machines_by_op_type"][op.op_type_id]:
            raise ValueError("machine outside resource pool")
        if result.operator_id not in pool["operators_by_machine"][result.machine_id]:
            raise ValueError("operator outside resource pool")
    elif (result.machine_id, result.operator_id) != (op.machine_id, op.operator_id):
        raise ValueError("fixed resource changed")
    if any(start < stop and begin < end for begin, stop in env["downtime"].get(result.machine_id, [])):
        raise ValueError("downtime overlap")
    calendar = env["calendar"]
    priority = env["batches"][op.batch_id].priority
    if calendar.adjust_to_working_time(start, priority=priority, operator_id=result.operator_id) != start:
        raise ValueError("start outside working calendar")
    hours = op.setup_hours + op.unit_hours * env["batches"][op.batch_id].quantity
    expected_end = calendar.add_working_hours(start, hours, priority=priority, operator_id=result.operator_id)
    if expected_end != end:
        raise ValueError("duration/calendar mismatch")


def _audit_resource_overlap(results, key):
    groups = {}
    for result in results:
        groups.setdefault(getattr(result, key), []).append(result)
    for rows in groups.values():
        ordered = sorted(rows, key=lambda row: row.start_time)
        if any(prev.end_time > row.start_time for prev, row in zip(ordered, ordered[1:])):
            raise ValueError("resource overlap: " + key)

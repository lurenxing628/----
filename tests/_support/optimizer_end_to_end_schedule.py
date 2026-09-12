"""Revalidate complete serialized schedules outside the measured interval."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from core.algorithms.evaluation import compute_metrics, objective_score
from tests._support.optimizer_quality_matrix_schedule import RESULT_FIELDS

OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")


def quality_vectors(results, batches, failed_ops=0, **kwargs):
    metrics = compute_metrics(results, batches, **kwargs)
    return {objective: [float(failed_ops)] + list(objective_score(objective, metrics)) for objective in OBJECTIVES}


def schedule_payload(plan, schedule_input):
    results = list(plan.results)
    return {"failed_ops": int(plan.summary.failed_ops),
            "quality_vectors": quality_vectors(results, schedule_input.batches, plan.summary.failed_ops,
                                               expected_operations=schedule_input.algo_ops_to_schedule,
                                               seed_results=_seed_objects(schedule_input.seed_results),
                                               failure_details=plan.summary.failure_details),
            "schedule": [{key: _value(getattr(row, key)) for key in RESULT_FIELDS} for row in results]}


def _value(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _seed_objects(rows):
    return [SimpleNamespace(**row) if isinstance(row, dict) else row for row in rows]


def audit_payload(payload, data):
    from tests._support.optimizer_end_to_end_cases import case_environment

    if not isinstance(payload, dict) or set(payload) != {"failed_ops", "quality_vectors", "schedule"}:
        raise ValueError("unknown or missing end-to-end schedule fields")
    if type(payload["failed_ops"]) is not int or payload["failed_ops"] != 0:
        raise ValueError("all fixed end-to-end fixtures must be feasible")
    operations = {row["id"]: row for row in data["operations"]}
    results = _read_results(payload["schedule"], operations)
    _audit_seeds(results, data)
    config = {"time_budget_seconds": 1, "seed": 0}
    with case_environment(data, "min_overdue", config) as env:
        for op_id, row in results.items():
            if op_id not in env.frozen_op_ids:
                _audit_slot(row, operations[op_id], env)
        _audit_precedence(results)
        _audit_resources(results)
        vectors = quality_vectors(list(results.values()), env.batches, expected_operations=env.algo_ops_to_schedule,
                                  seed_results=_seed_objects(env.seed_results), failure_details=[])
    if payload["quality_vectors"] != vectors:
        raise ValueError("quality vectors disagree with serialized schedule")
    return vectors


def _read_results(rows, operations):
    if not isinstance(rows, list):
        raise ValueError("schedule must be a list")
    results = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(RESULT_FIELDS):
            raise ValueError("unknown or missing result fields")
        op_id = row["op_id"]
        if type(op_id) is not int or op_id not in operations or op_id in results:
            raise ValueError("duplicate or unknown operation")
        for key in ("op_code", "batch_id", "seq", "source", "op_type_name"):
            if type(row[key]) is not type(operations[op_id][key]) or row[key] != operations[op_id][key]:
                raise ValueError("operation identity mismatch: " + key)
        result = SimpleNamespace(**row)
        result.start_time = datetime.fromisoformat(row["start_time"])
        result.end_time = datetime.fromisoformat(row["end_time"])
        if result.start_time.tzinfo or result.end_time.tzinfo or result.end_time <= result.start_time:
            raise ValueError("invalid schedule interval")
        results[op_id] = result
    if set(results) != set(operations):
        raise ValueError("missing operation")
    return results


def _audit_seeds(results, data):
    for seed in data["seed_results"]:
        row = results[seed["op_id"]]
        if any(_value(getattr(row, key)) != seed[key] for key in RESULT_FIELDS):
            raise ValueError("fixed seed changed")


def _audit_slot(row, operation, env):
    if row.start_time < env.start_dt_norm:
        raise ValueError("operation starts before run start")
    batch = env.batches[row.batch_id]
    if env.readiness_gate_enabled and batch.ready_date:
        if row.start_time < datetime.fromisoformat(batch.ready_date):
            raise ValueError("readiness lower bound violated")
    if row.source == "external":
        if row.machine_id is not None or row.operator_id is not None:
            raise ValueError("external operation cannot occupy internal resources")
        if row.end_time != row.start_time + timedelta(days=operation["ext_days"]):
            raise ValueError("external calendar duration mismatch")
        return
    pool = env.resource_pool
    for field in ("machine_id", "operator_id"):
        if operation[field] and getattr(row, field) != operation[field]:
            raise ValueError("fixed resource changed")
    if pool:
        if row.machine_id not in pool["machines_by_op_type"][operation["op_type_id"]]:
            raise ValueError("machine outside pool")
        if row.operator_id not in pool["operators_by_machine"][row.machine_id]:
            raise ValueError("operator outside pool")
    elif (row.machine_id, row.operator_id) != (operation["machine_id"], operation["operator_id"]):
        raise ValueError("fixed resource changed")
    if any(row.start_time < stop and begin < row.end_time for begin, stop in env.downtime_map.get(row.machine_id, [])):
        raise ValueError("downtime overlap")
    calendar = env.cal_svc
    if calendar.adjust_to_working_time(row.start_time, priority=batch.priority, operator_id=row.operator_id) != row.start_time:
        raise ValueError("start outside working calendar")
    hours = operation["setup_hours"] + operation["unit_hours"] * batch.quantity
    if calendar.add_working_hours(row.start_time, hours, priority=batch.priority, operator_id=row.operator_id) != row.end_time:
        raise ValueError("working duration mismatch")


def _audit_precedence(results):
    batches = {}
    for row in results.values():
        batches.setdefault(row.batch_id, []).append(row)
    for rows in batches.values():
        ordered = sorted(rows, key=lambda row: (row.seq, row.op_id))
        if any(a.end_time > b.start_time for a, b in zip(ordered, ordered[1:])):
            raise ValueError("precedence overlap")


def _audit_resources(results):
    for field in ("machine_id", "operator_id"):
        groups = {}
        for row in results.values():
            if row.source == "internal":
                groups.setdefault(getattr(row, field), []).append(row)
        for rows in groups.values():
            ordered = sorted(rows, key=lambda row: row.start_time)
            if any(a.end_time > b.start_time for a, b in zip(ordered, ordered[1:])):
                raise ValueError("resource overlap: " + field)

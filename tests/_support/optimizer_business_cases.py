"""Small offline business cases for the real candidate-comparison entry point."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithms.evaluation import compute_metrics, objective_score
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_input_contracts import ScheduleRunInput
from tests._support.algo_operations import make_algo_op
from tests._support.optimizer_exact_oracle import (
    OBJECTIVES,
    ScheduledOperation,
    improving_case,
    score_schedule,
    solve_exact,
    tie_chain_case,
)
from tests._support.paths import REPO_ROOT

START = datetime(2026, 1, 5)
RESULT_FIELDS = (
    "op_id", "op_code", "batch_id", "seq", "source", "machine_id", "operator_id",
    "op_type_name", "start_time", "end_time",
)


def _assigned(value):
    """夹具用空串表示还没指定设备或人员；生产构造边界里这是 None。"""
    return None if value == "" else value


def algo_operation_from_fixture(operation: Dict[str, Any]) -> OpForScheduleAlgo:
    """像排产输入构建那样产出完整的算法工序；外协组字段只有外协夹具才给。"""
    return make_algo_op(**dict(operation, machine_id=_assigned(operation["machine_id"]),
                               operator_id=_assigned(operation["operator_id"])))


def batch_operation_from_fixture(operation: Dict[str, Any]) -> BatchOperation:
    """像排产入口 run_input_rows.operation_model 那样直接构造工序；夹具描述的是算法工序。

    算法工序用空串表示还没指定设备或人员，库里存 NULL；只有外协工序带 ext_days；
    piece_id、supplier_id、status、created_at 按新建批次工序的库内取值写明。
    """
    return BatchOperation(
        id=operation["id"], op_code=operation["op_code"], batch_id=operation["batch_id"], piece_id=None,
        seq=operation["seq"], op_type_id=operation["op_type_id"], op_type_name=operation["op_type_name"],
        source=operation["source"],
        machine_id=_assigned(operation["machine_id"]), operator_id=_assigned(operation["operator_id"]),
        supplier_id=None, setup_hours=operation["setup_hours"], unit_hours=operation["unit_hours"],
        ext_days=operation.get("ext_days"), status="pending", created_at=None,
    )


def _calendar(hours):
    return [
        {"date": (START + timedelta(days=day)).date().isoformat(), "day_type": "workday",
         "shift_start": "00:00" if hours == 24 else "08:00",
         "shift_end": "00:00" if hours == 24 else "16:00", "shift_hours": float(hours),
         "efficiency": 1.0, "allow_normal": "yes", "allow_urgent": "yes", "remark": "optimizer_business_case"}
        for day in range(60)
    ]


def _tiny_data(scenario):
    case = improving_case() if scenario == "tiny_improving" else tie_chain_case()
    batches = [
        {"batch_id": bid, "quantity": 1, "priority": case.priority_by_batch[bid],
         "due_date": (START + timedelta(minutes=due) - timedelta(days=1)).date().isoformat(),
         "ready_status": "yes", "ready_date": None}
        for bid, due in case.due_minute_by_batch.items()
    ]
    sequences, operations = {}, []
    for item in case.operations:
        sequences[item.batch_id] = sequences.get(item.batch_id, 0) + 1
        operations.append(
            {"id": item.op_id, "op_code": "T-" + str(item.op_id), "batch_id": item.batch_id,
             "seq": sequences[item.batch_id], "source": "internal", "machine_id": item.machine_id,
             "operator_id": item.operator_id, "setup_hours": 0.0,
             "unit_hours": item.duration_minutes / 60.0, "op_type_id": item.family, "op_type_name": item.family}
        )
    return {"batches": batches, "operations": operations, "calendar": _calendar(24),
            "downtime": {}, "resource_pool": None, "seed_results": [], "readiness_gate_enabled": False,
            "tiny_case": case}


def _resource_data(batch_count):
    # Preserve the original resource-pool fixture and its downtime.
    batches, operations = [], []
    for job in range(batch_count):
        batch_id = "B" + str(job).zfill(2)
        batches.append(
            {"batch_id": batch_id, "quantity": 1, "priority": ("normal", "urgent", "critical")[job % 3],
             "due_date": (START + timedelta(days=job % 3)).date().isoformat(),
             "ready_status": "yes", "ready_date": None}
        )
        for step in range(4):
            family = "TYPE" + str((job + step) % 2)
            operations.append(
                {"id": len(operations) + 1, "op_code": batch_id + "-" + str(step), "batch_id": batch_id,
                 "seq": step + 1, "source": "internal", "machine_id": "", "operator_id": "",
                 "setup_hours": 0.5, "unit_hours": float(1 + (job * 3 + step * 2) % 5),
                 "op_type_id": family, "op_type_name": family}
            )
    return {
        "batches": batches, "operations": operations, "calendar": _calendar(8),
        "downtime": {"M0": [(START + timedelta(hours=8), START + timedelta(hours=13))],
                     "M1": [(START + timedelta(days=1, hours=10), START + timedelta(days=1, hours=14))]},
        "resource_pool": {
            "machines_by_op_type": {"TYPE0": ["M0", "M1", "M2"], "TYPE1": ["M0"]},
            "operators_by_machine": {"M0": ["O0", "O1"], "M1": ["O1", "O2"], "M2": ["O0", "O2"]},
            "machines_by_operator": {"O0": ["M0", "M2"], "O1": ["M0", "M1"], "O2": ["M1", "M2"]},
            "pair_rank": {},
        },
        "seed_results": [], "readiness_gate_enabled": False,
    }


def fixture_data(scenario):
    if scenario.startswith("tiny_"):
        return _tiny_data(scenario)
    data = _resource_data(4 if scenario == "frozen_ready_external" else 12)
    if scenario == "frozen_ready_external":
        frozen = data["operations"][0]
        frozen.update(machine_id="M0", operator_id="O0")
        data["seed_results"] = [
            {"op_id": frozen["id"], "op_code": frozen["op_code"], "batch_id": frozen["batch_id"],
             "seq": frozen["seq"], "source": "internal", "machine_id": "M0", "operator_id": "O0",
             "op_type_name": frozen["op_type_name"],
             "start_time": (START - timedelta(hours=frozen["setup_hours"] + frozen["unit_hours"])).isoformat(),
             "end_time": START.isoformat()}
        ]
        data["batches"][1].update(ready_status="no", ready_date=(START + timedelta(days=2)).date().isoformat())
        data["operations"][8].update(source="external", machine_id="", operator_id="", ext_days=1.0,
                                     ext_merge_mode="separate", ext_group_id=None, ext_group_total_days=None)
        data["readiness_gate_enabled"] = True
    return data


@contextmanager
def case_environment(data, objective, config=None):
    config = config or {"time_budget_seconds": 1, "seed": 0}
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
        calendar = CalendarService(conn)
        calendar._admin.repo.upsert_many(
            [calendar._admin._build_work_calendar_from_payload(row) for row in data["calendar"]]
        )
        conn.commit()
        values = default_snapshot_values()
        values.update(sort_strategy="fifo", dispatch_mode="sgs", dispatch_rule="slack", algo_mode="improve",
                      time_budget_seconds=config["time_budget_seconds"], objective=objective, ortools_enabled="no",
                      auto_assign_enabled="no" if "tiny_case" in data else "yes",
                      freeze_window_enabled="no", freeze_window_days=0)
        operations = [algo_operation_from_fixture(row) for row in data["operations"]]
        batch_operations = [batch_operation_from_fixture(row) for row in data["operations"]]
        seeds: List[Dict[str, Any]] = [dict(row, start_time=datetime.fromisoformat(row["start_time"]),
                      end_time=datetime.fromisoformat(row["end_time"])) for row in data["seed_results"]]
        frozen_ids = {row["op_id"] for row in seeds}
        yield ScheduleRunInput(
            cal_svc=calendar, cfg=snapshot_from_values(values),
            algo_ops=operations, algo_ops_to_schedule=[op for op in operations if op.id not in frozen_ids],
            batches={row["batch_id"]: Batch(part_no=row["batch_id"], **row) for row in data["batches"]},
            start_dt_norm=START, end_date_norm=None, downtime_map=data["downtime"], seed_results=seeds,
            resource_pool=data["resource_pool"], optimizer_seed_version=config["seed"],
            readiness_gate_enabled=data["readiness_gate_enabled"], frozen_op_ids=frozen_ids,
            normalized_batch_ids=[row["batch_id"] for row in data["batches"]], t0=0.0,
            operations=batch_operations,
            missing_internal_resource_op_ids=set(),
            prev_version=0, execution_facts={}, execution_completed_op_ids=set(),
            execution_seed_results=[], execution_snapshot_revision="fixture", execution_snapshot_op_ids=[],
            execution_snapshot_op_count=0, schedule_output_allowed_op_ids={row["id"] for row in data["operations"]},
            payload_validation_operations=batch_operations,
            freeze_meta={
                "freeze_enabled": values["freeze_window_enabled"] == "yes",
                "freeze_days": int(values["freeze_window_days"]),
                "freeze_state": "active" if frozen_ids else "disabled",
                "freeze_applied": bool(frozen_ids),
                "freeze_disabled_reason": None if frozen_ids else "config_disabled",
            },
            downtime_meta={},
            resource_pool_meta={},
        )
    finally:
        conn.close()


def _payload(plan, env):
    metrics = compute_metrics(
        plan.results, env.batches, expected_operations=env.algo_ops_to_schedule,
        seed_results=[ScheduleResult(**row) for row in env.seed_results], failure_details=plan.summary.failure_details,
    )
    return {
        "quality_vectors": {objective: [float(plan.summary.failed_ops)] + list(objective_score(objective, metrics))
                            for objective in OBJECTIVES},
        "schedule": [
            {key: value.isoformat() if isinstance(value, datetime) else value
             for key in RESULT_FIELDS for value in (getattr(row, key),)}
            for row in plan.results
        ],
    }


def _audit_plan(plan, env, data):
    assert plan.summary.failed_ops == 0
    operations = {row["id"]: row for row in data["operations"]}
    results = {row.op_id: row for row in plan.results}
    assert len(results) == len(plan.results) == len(operations)
    assert set(results) == set(operations)
    for seed in env.seed_results:
        assert all(getattr(results[seed["op_id"]], key) == seed[key] for key in RESULT_FIELDS)
    for op_id, row in results.items():
        operation, batch = operations[op_id], env.batches[row.batch_id]
        assert all(getattr(row, key) == operation[key] for key in ("op_code", "batch_id", "seq", "source", "op_type_name"))
        if op_id in env.frozen_op_ids:
            continue
        assert row.start_time >= START and row.end_time > row.start_time
        if env.readiness_gate_enabled and batch.ready_date:
            assert row.start_time >= datetime.fromisoformat(batch.ready_date)
        if row.source == "external":
            assert row.machine_id is None and row.operator_id is None
            assert row.end_time == row.start_time + timedelta(days=operation["ext_days"])
            continue
        for field in ("machine_id", "operator_id"):
            if operation[field]:
                assert getattr(row, field) == operation[field]
        if env.resource_pool:
            assert row.machine_id in env.resource_pool["machines_by_op_type"][operation["op_type_id"]]
            assert row.operator_id in env.resource_pool["operators_by_machine"][row.machine_id]
        assert not any(row.start_time < end and start < row.end_time
                       for start, end in env.downtime_map.get(row.machine_id, []))
        assert env.cal_svc.adjust_to_working_time(row.start_time, priority=batch.priority,
                                                operator_id=row.operator_id) == row.start_time
        hours = operation["setup_hours"] + operation["unit_hours"] * batch.quantity
        assert env.cal_svc.add_working_hours(row.start_time, hours, priority=batch.priority,
                                            operator_id=row.operator_id) == row.end_time
    for field in ("batch_id", "machine_id", "operator_id"):
        groups = {}
        for row in results.values():
            if field == "batch_id" or row.source == "internal":
                groups.setdefault(getattr(row, field), []).append(row)
        for rows in groups.values():
            ordered = sorted(rows, key=(lambda row: (row.seq, row.op_id)) if field == "batch_id"
                             else (lambda row: row.start_time))
            assert all(left.end_time <= right.start_time for left, right in zip(ordered, ordered[1:]))


def _oracle_report(case, payload):
    rows = tuple(
        ScheduledOperation(row["op_id"],
                           int((datetime.fromisoformat(row["start_time"]) - START).total_seconds() / 60),
                           int((datetime.fromisoformat(row["end_time"]) - START).total_seconds() / 60),
                           row["machine_id"], row["operator_id"])
        for row in payload["schedule"]
    )
    selected, optimum, input_order = {}, {}, {}
    packed, minute = [], 0
    for operation in case.operations:
        packed.append(ScheduledOperation(operation.op_id, minute, minute + operation.duration_minutes,
                                         operation.machine_id, operation.operator_id))
        minute += operation.duration_minutes
    for objective in OBJECTIVES:
        selected[objective] = list(score_schedule(case, rows, objective))
        assert selected[objective] == payload["quality_vectors"][objective]
        optimum[objective] = list(solve_exact(case, objective))
        input_order[objective] = list(score_schedule(case, packed, objective))
    return {"selected_vectors": selected, "optimum_vectors": optimum, "input_order_vectors": input_order}


def run_case(scenario, objective):
    data = fixture_data(scenario)
    with case_environment(data, objective, {"time_budget_seconds": 5, "seed": 0}) as env:
        outcome = run_candidate_comparison(schedule_input=env)
        representatives = {}
        for plan in outcome.candidates:
            _audit_plan(plan, env, data)
            representatives[plan.candidate_key] = _payload(plan, env)
        selected = representatives[outcome.selection.selected_candidate_key]
        winners = {target: representatives[key] for target, key in outcome.selection.objective_winners.items()}
        oracles = ({key: _oracle_report(data["tiny_case"], payload) for key, payload in representatives.items()}
                   if "tiny_case" in data else {})
    process = outcome.unified_process
    assert process is not None
    observations = [event for event in process["events"]
                    if event["event_type"] == "archive_observation" and event["verified"] is True
                    and process["scopes"][event["scope_ref"]]["is_complete"]]
    return {"data": data, "outcome": outcome, "selected": selected, "winners": winners,
            "representatives": representatives, "oracles": oracles, "observations": observations,
            "oracle": oracles.get(outcome.selection.selected_candidate_key)}

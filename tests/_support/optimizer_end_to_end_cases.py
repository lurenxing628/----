"""Synthetic, offline inputs for the complete candidate-comparison entry point."""
from __future__ import annotations

import copy
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

from core.models.schedule_config_runtime import default_snapshot_values
from core.services.scheduler.calendar_service import CalendarService
from tests._support.optimizer_quality_matrix_cases import REPO_ROOT
from tests._support.optimizer_quality_matrix_cases import fixture_data as core_fixture

OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
SCENARIOS = ("tiny_improving", "tiny_chain", "shift_pool", "wide_parallel_chains", "frozen_ready_external")
START = datetime(2026, 1, 5)


def tiny_case(scenario):
    from tests._support.optimizer_exact_oracle import improving_case, tie_chain_case

    if scenario == "tiny_improving":
        return improving_case()
    if scenario == "tiny_chain":
        return tie_chain_case()
    raise ValueError("outside restricted tiny oracle domain")


def _tiny_data(scenario):
    case = tiny_case(scenario)
    batches = [{"batch_id": bid, "quantity": 1, "priority": case.priority_by_batch[bid],
                "due_date": (START + timedelta(minutes=due) - timedelta(days=1)).date().isoformat(),
                "ready_status": "yes", "ready_date": None}
               for bid, due in case.due_minute_by_batch.items()]
    seq = {}
    operations = []
    for item in case.operations:
        seq[item.batch_id] = seq.get(item.batch_id, 0) + 1
        operations.append({"id": item.op_id, "op_code": "T-" + str(item.op_id), "batch_id": item.batch_id,
                           "seq": seq[item.batch_id], "source": "internal", "machine_id": item.machine_id,
                           "operator_id": item.operator_id, "setup_hours": 0.0,
                           "unit_hours": item.duration_minutes / 60.0,
                           "op_type_id": item.family, "op_type_name": item.family})
    return {"batches": batches, "operations": operations, "calendar": _calendar(24),
            "downtime": {}, "resource_pool": None,
            "constraint_tags": ["single_resource", "zero_release", "independent_exact_oracle",
                                "known_improvable_order" if scenario == "tiny_improving" else "legal_no_improvement"]}


def _calendar(hours):
    return [{"date": (START + timedelta(days=day)).date().isoformat(), "day_type": "workday",
             "shift_start": "00:00" if hours == 24 else "08:00", "shift_end": "00:00" if hours == 24 else "16:00",
             "shift_hours": float(hours), "efficiency": 1.0, "allow_normal": "yes", "allow_urgent": "yes",
             "remark": "optimizer_end_to_end_v1"} for day in range(60)]


def fixture_data(scenario):
    if scenario not in SCENARIOS:
        raise ValueError("unknown end-to-end scenario: " + str(scenario))
    if scenario.startswith("tiny_"):
        data = _tiny_data(scenario)
    else:
        data = copy.deepcopy(core_fixture("medium_shift_pool"))
        data["calendar"] = _calendar(8)
        data["constraint_tags"] = ["shift_calendar", "downtime", "shared_operator", "scarce_machine_pool"]
        data["resource_pool"]["machines_by_op_type"]["TYPE1"] = ["M0"]
        if scenario == "wide_parallel_chains":
            _wide_disjoint_resources(data)
        if scenario == "frozen_ready_external":
            _mixed_constraints(data)
    data.update(scenario=scenario, start_dt=START.isoformat())
    data.setdefault("seed_results", [])
    data.setdefault("readiness_gate_enabled", False)
    return data


def _wide_disjoint_resources(data):
    resources = {batch["batch_id"]: ("M" + str(index), "O" + str(index))
                 for index, batch in enumerate(data["batches"])}
    data["operations"] = [op for op in data["operations"] if op["seq"] <= 2]
    for op in data["operations"]:
        machine, operator = resources[op["batch_id"]]
        op.update(machine_id=machine, operator_id=operator)
    pairs = list(resources.values())
    data["resource_pool"] = {
        "machines_by_op_type": {family: [machine for machine, _ in pairs] for family in ("TYPE0", "TYPE1")},
        "operators_by_machine": {machine: [operator] for machine, operator in pairs},
        "machines_by_operator": {operator: [machine] for machine, operator in pairs}, "pair_rank": {},
    }
    data["constraint_tags"] = ["shift_calendar", "downtime", "dag_width_12_parallel_linear_chains",
                               "fixed_resource_assignments", "disjoint_machine_operator_pairs"]


def _mixed_constraints(data):
    data["batches"] = data["batches"][:4]
    data["operations"] = data["operations"][:16]
    frozen = data["operations"][0]
    frozen.update(machine_id="M0", operator_id="O0")
    # Freeze an actual operation before run start, so current downtime does not invalidate it.
    hours = frozen["setup_hours"] + frozen["unit_hours"]
    data["seed_results"] = [{"op_id": frozen["id"], "op_code": frozen["op_code"], "batch_id": frozen["batch_id"],
                             "seq": frozen["seq"], "source": "internal", "machine_id": "M0", "operator_id": "O0",
                             "op_type_name": frozen["op_type_name"], "start_time": (START - timedelta(hours=hours)).isoformat(),
                             "end_time": START.isoformat()}]
    data["batches"][1].update(ready_status="no", ready_date=(START + timedelta(days=2)).date().isoformat())
    external = data["operations"][8]
    external.update(source="external", machine_id="", operator_id="", ext_days=1.0,
                    ext_merge_mode="separate", ext_group_id=None, ext_group_total_days=None)
    data["readiness_gate_enabled"] = True
    data["constraint_tags"].extend(["fixed_seed", "future_readiness_date", "external_calendar_days"])


def scheduler_config(scenario, objective, config):
    if scenario not in SCENARIOS or objective not in OBJECTIVES:
        raise ValueError("unknown end-to-end case")
    values = default_snapshot_values()
    values.update(sort_strategy="fifo", dispatch_mode="sgs", dispatch_rule="slack", algo_mode="improve",
                  time_budget_seconds=config["time_budget_seconds"], objective=objective, ortools_enabled="no",
                  auto_assign_enabled="no" if scenario.startswith("tiny_") else "yes",
                  freeze_window_enabled="no", freeze_window_days=0)
    return values


@contextmanager
def case_environment(data, objective, config):
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
        calendar = CalendarService(conn)
        for row in data["calendar"]:
            calendar.upsert_no_tx(row)
        conn.commit()
        operations = [SimpleNamespace(**row) for row in data["operations"]]
        batches = {row["batch_id"]: SimpleNamespace(**row) for row in data["batches"]}
        seeds = [dict(row, start_time=datetime.fromisoformat(row["start_time"]),
                      end_time=datetime.fromisoformat(row["end_time"])) for row in data["seed_results"]]
        frozen_ids = {row["op_id"] for row in seeds}
        values = scheduler_config(data["scenario"], objective, config)
        schedule_input = SimpleNamespace(
            cal_svc=calendar, cfg_svc=SimpleNamespace(**values), cfg=SimpleNamespace(**values),
            algo_ops=operations, algo_ops_to_schedule=[op for op in operations if op.id not in frozen_ids],
            batches=batches, start_dt_norm=datetime.fromisoformat(data["start_dt"]), end_date_norm=None,
            downtime_map={key: [(datetime.fromisoformat(a), datetime.fromisoformat(b)) for a, b in rows]
                          for key, rows in data["downtime"].items()}, seed_results=seeds,
            resource_pool=data["resource_pool"], optimizer_seed_version=config["seed"],
            readiness_gate_enabled=data["readiness_gate_enabled"], frozen_op_ids=frozen_ids,
        )
        yield schedule_input
    finally:
        conn.close()


def audit_payload(payload, data):
    from tests._support.optimizer_end_to_end_schedule import audit_payload as audit

    return audit(payload, data)

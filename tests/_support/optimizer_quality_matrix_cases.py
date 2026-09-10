"""Fixed, offline production-SGS inputs; no test-side optimizer or clock."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from core.models.schedule_config_runtime import default_snapshot_values
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.graph.metrics import build_node_metrics
from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch, build_precedence_graph
from core.services.scheduler.graph.types import OperationGraphNode

OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
SCENARIOS = ("tiny", "medium_shift_pool")
START = datetime(2026, 1, 5, 8)
REPO_ROOT = Path(__file__).resolve().parents[2]


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def fixture_data(scenario):
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario: " + str(scenario))
    medium = scenario == "medium_shift_pool"
    batches, operations = [], []
    for job in range(12 if medium else 4):
        batch_id = f"B{job:02d}"
        batches.append({
            "batch_id": batch_id, "quantity": 1, "priority": ("normal", "urgent", "critical")[job % 3],
            "due_date": (START + timedelta(days=job % 3 if medium else 0)).date().isoformat(),
            "ready_status": "yes", "ready_date": None,
        })
        for step in range(4 if medium else 2):
            family = f"TYPE{(job + step) % 2}"
            operations.append({
                "id": len(operations) + 1, "op_code": f"{batch_id}-{step}",
                "batch_id": batch_id, "seq": step + 1, "source": "internal",
                "machine_id": "" if medium else "M0", "operator_id": "" if medium else "O0",
                "setup_hours": 0.5, "unit_hours": float(1 + (job * 3 + step * 2) % 5),
                "op_type_id": family, "op_type_name": family,
            })
    calendar = [{
        "date": (START + timedelta(days=day)).date().isoformat(), "day_type": "workday",
        "shift_start": "08:00" if medium else "00:00", "shift_end": "16:00" if medium else "00:00",
        "shift_hours": 8.0 if medium else 24.0, "efficiency": 1.0,
        "allow_normal": "yes", "allow_urgent": "yes", "remark": "optimizer_quality_matrix_v1",
    } for day in range(60)]
    return {
        "scenario": scenario, "start_dt": START.isoformat(), "batches": batches, "operations": operations,
        "calendar": calendar,
        "downtime": {"M0": [[START.isoformat(), (START + timedelta(hours=5)).isoformat()]],
                     "M1": [[(START + timedelta(days=1, hours=2)).isoformat(),
                             (START + timedelta(days=1, hours=6)).isoformat()]]} if medium else {},
        "resource_pool": {
            "machines_by_op_type": {"TYPE0": ["M0", "M1", "M2"], "TYPE1": ["M0", "M1", "M2"]},
            "operators_by_machine": {"M0": ["O0", "O1"], "M1": ["O1", "O2"], "M2": ["O0", "O2"]},
            "machines_by_operator": {"O0": ["M0", "M2"], "O1": ["M0", "M1"], "O2": ["M1", "M2"]},
            "pair_rank": {},
        } if medium else None,
    }


def scheduler_config(scenario, objective, time_budget_seconds):
    if objective not in OBJECTIVES:
        raise ValueError("unknown objective: " + str(objective))
    values = default_snapshot_values()
    values.update({
        "sort_strategy": "priority_first", "dispatch_mode": "sgs", "dispatch_rule": "slack",
        "auto_assign_enabled": "yes" if scenario == "medium_shift_pool" else "no",
        "objective": objective, "algo_mode": "improve", "time_budget_seconds": time_budget_seconds,
        "ortools_enabled": "no", "freeze_window_enabled": "no", "freeze_window_days": 0,
    })
    return values


@contextmanager
def case_environment(scenario):
    data = fixture_data(scenario)
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
        calendar = CalendarService(conn)
        for row in data["calendar"]:
            calendar.upsert_no_tx(row)
        conn.commit()
        operations = [SimpleNamespace(**op) for op in data["operations"]]
        batches = {batch["batch_id"]: SimpleNamespace(**batch) for batch in data["batches"]}
        yield {
            "data": data, "calendar": calendar, "operations": operations, "batches": batches,
            "downtime": {machine: [(datetime.fromisoformat(a), datetime.fromisoformat(b)) for a, b in spans]
                         for machine, spans in data["downtime"].items()},
            "resource_pool": data["resource_pool"], "graph": graph_context(operations, batches, data["resource_pool"]),
        }
    finally:
        conn.close()


def graph_context(operations, batches, pool):
    nodes = [OperationGraphNode(
        node_id=str(op.id), batch_id=op.batch_id, op_code=op.op_code, seq=op.seq, name=op.op_code,
        duration_minutes=int((op.setup_hours + op.unit_hours * batches[op.batch_id].quantity) * 60),
        priority=batches[op.batch_id].priority, due_date=batches[op.batch_id].due_date,
        op_type_id=op.op_type_id, machine_id=op.machine_id, operator_id=op.operator_id,
        candidate_machine_ids=tuple(pool["machines_by_op_type"][op.op_type_id]) if pool else (),
    ) for op in operations]
    graph = build_precedence_graph(nodes, build_linear_edges_by_batch(nodes))
    ids = {op.id for op in operations}
    return {
        "enabled": True, "schedulable_op_ids": ids, "fixed_op_ids": set(), "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {op_id: {int(n) for n in graph.predecessors(str(op_id))} for op_id in ids},
        "successor_op_ids_by_op_id": {op_id: {int(n) for n in graph.successors(str(op_id))} for op_id in ids},
        "sort_key_by_op_id": {op.id: (list(batches).index(op.batch_id), op.seq, op.id) for op in operations},
        "graph_priority_key_by_op_id": {op_id: (0.0,) for op_id in ids},
        "node_metrics_by_op_id": {int(key): value for key, value in build_node_metrics(graph).items()},
    }

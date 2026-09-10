"""Deterministic, database-free workloads for the real SGS and calendar engine."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict

from core.algorithms import GreedyScheduler, ScheduleResult
from core.models import WorkCalendar
from core.services.scheduler.calendar_engine import CalendarEngine

BASE = datetime(2026, 9, 8, 8)


class MemoryCalendar(CalendarEngine):
    def __init__(self):
        super().__init__(conn=None)
        # This benchmark supplies its full calendar in memory, with no assigned shift profiles.
        self.operator_shift_calendar = SimpleNamespace(apply_policy=lambda policy, operator_id: policy)

    def _resolve_calendar_row(self, date_str, op_id):
        day = datetime.strptime(date_str, "%Y-%m-%d")
        working = day.weekday() < 5
        return WorkCalendar(
            date=date_str, day_type="workday" if working else "weekend",
            shift_hours=8.0 if working else 0.0,
            efficiency=0.85 if op_id and int(op_id[1:]) % 3 == 0 else 1.0,
            allow_normal="yes" if working else "no", allow_urgent="yes" if working else "no",
        )


def make_case(batch_count=36, ops_per_batch=8, *, auto=True, graph=False, window=False) -> Dict[str, Any]:
    machines = [f"M{i:02d}" for i in range(12)]
    operators = [f"W{i:02d}" for i in range(12)]
    pool = {
        "machines_by_op_type": {f"T{t}": machines[t::3] for t in range(3)},
        "operators_by_machine": {mid: [operators[i], operators[(i + 1) % 12]] for i, mid in enumerate(machines)},
        "machines_by_operator": {}, "pair_rank": {},
    }
    batches, operations, predecessors, successors = {}, [], {}, {}
    for b in range(batch_count):
        bid = f"B{b:03d}"
        batches[bid] = SimpleNamespace(
            batch_id=bid, priority="urgent" if b % 5 == 0 else "normal",
            due_date=(BASE + timedelta(days=3 + b % 15)).date(),
            ready_status="yes", ready_date=None, created_at=None, quantity=1 + b % 4,
        )
        for seq in range(ops_per_batch):
            oid = b * ops_per_batch + seq + 1
            resource = (b + seq) % 12
            operations.append(SimpleNamespace(
                id=oid, op_code=f"{bid}_{seq:02d}", batch_id=bid, seq=seq,
                source="internal", machine_id="" if auto else machines[resource],
                operator_id="" if auto else operators[resource], setup_hours=0.25 + (oid % 5) * 0.25,
                unit_hours=0.15 + (oid % 3) * 0.1, op_type_id=f"T{resource % 3}",
                op_type_name=f"TYPE{resource % 3}",
            ))
            predecessors[oid] = [oid - 1] if seq else []
            successors[oid] = [oid + 1] if seq + 1 < ops_per_batch else []
    seeds = [
        ScheduleResult(
            op_id=100000 + i * 3 + j, op_code=f"SEED_{i}_{j}", batch_id="SEED",
            seq=j, machine_id=mid, operator_id=operators[i],
            start_time=BASE + timedelta(hours=j * 3), end_time=BASE + timedelta(hours=j * 3 + 0.5),
            source="internal", op_type_name=f"TYPE{i % 3}",
        ) for i, mid in enumerate(machines) for j in range(3)
    ]
    downtimes = {
        mid: [(BASE + timedelta(days=d, hours=2), BASE + timedelta(days=d, hours=3)) for d in (0, 2, 4, 7)]
        for mid in machines
    }
    kwargs: Dict[str, Any] = dict(
        operations=operations, batches=batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack",
        resource_pool=pool if auto else None, seed_results=seeds, machine_downtimes=downtimes,
        end_date="2026-09-09" if window else None,
    )
    if graph:
        kwargs["graph_ready_context"] = {
            "enabled": True, "schedulable_op_ids": list(predecessors),
            "predecessor_op_ids_by_op_id": predecessors, "successor_op_ids_by_op_id": successors,
            "fixed_op_ids": [], "score_enabled": True,
            "sort_key_by_op_id": {op.id: ((op.id - 1) // ops_per_batch, op.seq, op.id) for op in operations},
            "graph_priority_key_by_op_id": {op.id: (float(op.id % 3), float(op.seq)) for op in operations},
        }
    return kwargs


def make_scheduler():
    return GreedyScheduler(calendar_service=MemoryCalendar(), config_service={"auto_assign_enabled": "yes"})

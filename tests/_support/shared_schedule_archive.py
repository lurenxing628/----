"""Shared archive input builders for scheduling and saved-process tests."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import compute_metrics, objective_score
from core.models.objective import target_objectives_for
from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive

START = datetime(2026, 10, 13, 20)
OPERATIONS = tuple(SimpleNamespace(id=index, batch_id=f"B{index}") for index in (1, 2, 3))
BATCHES = {
    f"B{index}": SimpleNamespace(batch_id=f"B{index}", due_date="2026-10-13", priority=priority)
    for index, priority in ((1, "critical"), (2, "normal"), (3, "urgent"))
}


def _result(op_id, start_hour, *, machine="M1", seed_source=None):
    start = START + timedelta(hours=start_hour)
    type_id = "T2" if op_id == 2 else "T1"
    return ScheduleResult(
        op_id=op_id, op_code=f"OP{op_id}", batch_id=f"B{op_id}", seq=1,
        machine_id=machine, operator_id=f"O{op_id}", start_time=start,
        end_time=start + timedelta(hours=1), source="internal", op_type_name=type_id,
        op_type_id=type_id, seed_source=seed_source, state_revision="r1",
    )


def _candidate(results, *, objective="min_tardiness", failures=(), fixed_seed=()):
    rows = list(results)
    seeds = tuple(fixed_seed)
    fixed_ids = {row.op_id for row in seeds}
    metrics = compute_metrics(
        rows, BATCHES, expected_operations=[op for op in OPERATIONS if op.id not in fixed_ids],
        seed_results=seeds, failure_details=failures,
    )
    missing = 3 - len({row.op_id for row in rows} & {1, 2, 3})
    summary = ScheduleSummary(
        success=missing == 0, total_ops=3, scheduled_ops=len(rows), failed_ops=missing,
        warnings=["original warning"], errors=[], duration_seconds=0.0,
        failure_details=list(failures),
    )
    return {
        "results": rows, "summary": summary, "metrics": metrics,
        "score": (float(missing),) + objective_score(objective, metrics),
        "objective": objective, "order": ["B1", "B2", "B3"],
        "params": {"tie_breaker": ["B1", "B2"]}, "algo_stats": {"visited": [1]},
        "dispatch_mode": "sgs", "dispatch_rule": "cr", "seed_results": seeds,
    }


def _archive(primary="min_tardiness", *, limit=64):
    return SharedScheduleArchive(
        primary, target_objectives_for(primary), {1, 2, 3}, set(BATCHES), retention_limit=limit,
    )


def _register_decode(archive, candidate, *, verified=True, elapsed_ms=0):
    observed = archive.register_decode(candidate, verified=verified, elapsed_ms=elapsed_ms)
    candidate.update(_shared_entry_id=observed.entry_id, _archive_observation=observed)
    return candidate


def _observe_decoded(search, objective, *, candidate, origin, verified, elapsed_ms):
    _register_decode(search.archive, candidate, verified=verified, elapsed_ms=elapsed_ms)
    search.observe(objective, candidate=candidate, origin=origin, verified=verified, elapsed_ms=elapsed_ms)


def _failure(op_id):
    return {"code": "dispatch_operation_failed", "op_id": op_id, "batch_id": f"B{op_id}"}

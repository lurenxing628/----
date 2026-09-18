"""SGS decode equivalence and timing receipts: graph-priority pruning on/off on one unchanged checkout.

Usage: env -u FORCE_COLOR .venv/bin/python .codestable/refactors/2026-09-19-sgs-decode-pruning-and-memo/measure.py \
           --tag before --repeats 3
Writes measure-<tag>.json next to this file: per workload the payload SHA-256 with pruning enabled and disabled
(must be equal), score-cache stats, alternating wall-clock timings and cProfile call counts. Timings are
single-machine, dirty-worktree observations, not a gate proof.
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.algorithms import GreedyScheduler, SortStrategy  # noqa: E402
from core.algorithms.greedy import scheduler as scheduler_module  # noqa: E402
from core.algorithms.greedy.dispatch.sgs_priority_pruning import GraphPriorityPruning  # noqa: E402
from tests._support import optimizer_quality_matrix_cases as qm_cases  # noqa: E402
from tests._support.sgs_slot_reuse_case import make_case, make_scheduler  # noqa: E402

COUNTED = ("_score_candidate", "estimate_internal_slot", "_choose_best_pair", "_pair_score", "_dispatch_key")


def _payload(results, summary, strategy, params):
    rows = sorted((r.op_id, r.machine_id, r.operator_id, str(r.start_time), str(r.end_time), r.source) for r in results)
    fields = {key: value for key, value in vars(summary).items() if key != "duration_seconds"}
    return json.dumps([rows, fields, str(strategy), params], sort_keys=True, default=str)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique_keys(operations):
    ordered = sorted(operations, key=lambda op: (str(op.batch_id), int(op.seq), int(op.id)))
    return {op.id: (float(index),) for index, op in enumerate(ordered)}


def _slot_case(*, auto, window, keys):
    kwargs = make_case(batch_count=24, ops_per_batch=6, auto=auto, graph=True, window=window)
    if keys == "unique":
        kwargs["graph_ready_context"]["graph_priority_key_by_op_id"] = _unique_keys(kwargs["operations"])
    return kwargs, make_scheduler


def _scaled_fixture(jobs, *, bounded):
    start = qm_cases.START

    def fixture_data(scenario):
        machines = max(3, (jobs + 3) // 4)
        names = [f"M{i}" for i in range(machines)]
        workers = [f"O{i}" for i in range(machines)]
        ntypes = max(1, machines // 3) if bounded else 2
        batches, operations = [], []
        for job in range(jobs):
            batch_id = f"B{job:03d}"
            batches.append({"batch_id": batch_id, "quantity": 1, "priority": ("normal", "urgent", "critical")[job % 3],
                            "due_date": (start + timedelta(days=job % 3)).date().isoformat(), "ready_status": "yes",
                            "ready_date": None})
            for step in range(4):
                family = f"TYPE{(job + step) % ntypes}"
                operations.append({"id": len(operations) + 1, "op_code": f"{batch_id}-{step}", "batch_id": batch_id,
                                   "seq": step + 1, "source": "internal", "machine_id": "", "operator_id": "",
                                   "setup_hours": 0.5, "unit_hours": float(1 + (job * 3 + step * 2) % 5),
                                   "op_type_id": family, "op_type_name": family})
        calendar = [{"date": (start + timedelta(days=day)).date().isoformat(), "day_type": "workday",
                     "shift_start": "08:00", "shift_end": "16:00", "shift_hours": 8.0, "efficiency": 1.0,
                     "allow_normal": "yes", "allow_urgent": "yes", "remark": "scaled"} for day in range(120)]
        ops_by_machine = {names[i]: sorted({workers[i], workers[(i + 1) % machines]}) for i in range(machines)}
        by_operator = {}
        for machine, ops in ops_by_machine.items():
            for worker in ops:
                by_operator.setdefault(worker, []).append(machine)
        pool = {"machines_by_op_type": ({f"TYPE{t}": names[3 * t:3 * t + 3] for t in range(ntypes)} if bounded
                                        else {"TYPE0": names, "TYPE1": names}),
                "operators_by_machine": ops_by_machine,
                "machines_by_operator": {k: sorted(v) for k, v in by_operator.items()}, "pair_rank": {}}
        return {"scenario": scenario, "start_dt": start.isoformat(), "batches": batches, "operations": operations,
                "calendar": calendar,
                "downtime": {"M0": [[start.isoformat(), (start + timedelta(hours=5)).isoformat()]],
                             "M1": [[(start + timedelta(days=1, hours=2)).isoformat(),
                                     (start + timedelta(days=1, hours=6)).isoformat()]]},
                "resource_pool": pool}

    return fixture_data


class _ScaledCase:
    """One optimizer-style decode on the scaled fixture: real CalendarService, production DTOs, graph context."""

    def __init__(self, jobs, *, bounded, score_enabled):
        self.jobs, self.bounded, self.score_enabled = jobs, bounded, score_enabled

    def __enter__(self):
        self._patch = patch.object(qm_cases, "fixture_data", _scaled_fixture(self.jobs, bounded=self.bounded))
        self._patch.start()
        self._env_cm = qm_cases.case_environment("medium_shift_pool")
        env = self._env_cm.__enter__()
        values = qm_cases.scheduler_config("medium_shift_pool", "min_weighted_tardiness", 5)
        graph = dict(env["graph"])
        graph["score_enabled"] = self.score_enabled
        if self.score_enabled:
            graph["graph_priority_key_by_op_id"] = _unique_keys(env["operations"])
        kwargs = {
            "strict_mode": True, "operations": env["operations"], "batches": env["batches"],
            "strategy": SortStrategy.PRIORITY_FIRST,
            "start_dt": qm_cases.START, "end_date": None, "machine_downtimes": env["downtime"], "seed_results": [],
            "dispatch_mode": "sgs", "dispatch_rule": "slack", "resource_pool": env["resource_pool"],
            "readiness_gate_enabled": False, "strategy_params": {}, "batch_order_override": list(env["batches"]),
            "graph_ready_context": graph,
        }
        calendar = env["calendar"]
        return kwargs, (lambda: GreedyScheduler(calendar_service=calendar, config_service=SimpleNamespace(**values)))

    def __exit__(self, *exc):
        self._env_cm.__exit__(*exc)
        self._patch.stop()


def workloads():
    yield "slot_auto_graph_unique", lambda: _slot_case(auto=True, window=False, keys="unique")
    yield "slot_auto_graph_tied", lambda: _slot_case(auto=True, window=False, keys="tied")
    yield "slot_auto_graph_window", lambda: _slot_case(auto=True, window=True, keys="unique")
    yield "slot_fixed_graph_unique", lambda: _slot_case(auto=False, window=False, keys="unique")
    yield "scaled192_bounded_graph", lambda: _ScaledCase(48, bounded=True, score_enabled=True)
    yield "scaled192_bounded_baseline", lambda: _ScaledCase(48, bounded=True, score_enabled=False)
    yield "scaled192_wide_graph", lambda: _ScaledCase(48, bounded=False, score_enabled=True)
    yield "scaled480_bounded_graph", lambda: _ScaledCase(120, bounded=True, score_enabled=True)


def _run(kwargs, scheduler_factory, *, enabled):
    def full_scoring(*_args):
        return None

    original = GraphPriorityPruning.frontier
    with patch.object(GraphPriorityPruning, "frontier", original if enabled else full_scoring), \
            patch.object(scheduler_module, "create_native_sgs_reuse", lambda *_a, **_k: None):
        scheduler = scheduler_factory()
        started = time.perf_counter()
        results, summary, strategy, params = scheduler.schedule(**deepcopy(kwargs))
        elapsed = time.perf_counter() - started
    return elapsed, _payload(results, summary, strategy, params), dict(scheduler._last_sgs_score_cache_stats)


def _counts(kwargs, scheduler_factory, *, enabled):
    profiler = cProfile.Profile()
    profiler.enable()
    _run(kwargs, scheduler_factory, enabled=enabled)
    profiler.disable()
    counts = {}
    for (filename, _line, name), (_cc, calls, _own, _cum, _callers) in pstats.Stats(profiler).stats.items():
        if name in COUNTED and str(ROOT) in filename:
            counts[name] = counts.get(name, 0) + calls
    return counts


def measure(name, factory, repeats):
    context = factory()
    if hasattr(context, "__enter__"):
        with context as (kwargs, scheduler_factory):
            return _measure_case(name, kwargs, scheduler_factory, repeats)
    kwargs, scheduler_factory = context
    return _measure_case(name, kwargs, scheduler_factory, repeats)


def _measure_case(name, kwargs, scheduler_factory, repeats):
    _, off_payload, off_stats = _run(kwargs, scheduler_factory, enabled=False)
    _, on_payload, on_stats = _run(kwargs, scheduler_factory, enabled=True)
    equal = off_payload == on_payload
    timings = {"off": [], "on": []}
    for repeat in range(repeats):
        for enabled in ((False, True) if repeat % 2 == 0 else (True, False)):
            elapsed, payload, _ = _run(kwargs, scheduler_factory, enabled=enabled)
            assert payload == (on_payload if enabled else off_payload)
            timings["on" if enabled else "off"].append(elapsed)
    row = {
        "workload": name, "operation_count": len(kwargs["operations"]), "payload_equal": equal,
        "payload_sha256_off": _sha(off_payload), "payload_sha256_on": _sha(on_payload),
        "stats_off": off_stats, "stats_on": on_stats,
        "median_seconds_off": statistics.median(timings["off"]), "median_seconds_on": statistics.median(timings["on"]),
        "counts_off": _counts(kwargs, scheduler_factory, enabled=False),
        "counts_on": _counts(kwargs, scheduler_factory, enabled=True),
    }
    print(json.dumps({key: row[key] for key in ("workload", "operation_count", "payload_equal", "median_seconds_off",
                                                 "median_seconds_on")}, ensure_ascii=False))
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", action="append", help="workload name filter; repeatable")
    args = parser.parse_args(argv)
    rows = [measure(name, factory, args.repeats) for name, factory in workloads()
            if not args.only or name in args.only]
    output = HERE / f"measure-{args.tag}.json"
    output.write_text(json.dumps({"tag": args.tag, "rows": rows}, ensure_ascii=False, indent=1, default=str))
    print("wrote", output)
    return 0 if all(row["payload_equal"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

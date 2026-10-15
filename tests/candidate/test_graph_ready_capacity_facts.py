"""Fixed resource blocking is shared while operation calendar windows stay dynamic."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from core.services.scheduler.run.optimizer.graph import v2_capacity
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import BASELINE_ORDERING_FIELD


def test_pair_blocking_is_prepared_once_across_feature_bases_and_operation_windows(monkeypatch):
    start = datetime(2026, 10, 14, 8)

    def at(hours):
        return start + timedelta(hours=hours)

    calls, merges, conversions, downtime_reads = [], [], [], []

    class Calendar:
        def capacity_hours_between(self, low, high, *, priority, operator_id):
            calls.append((low, high, priority, operator_id))
            return (high - low).total_seconds() / 3600 * (0.5 if priority == "urgent" else 1)

    operations = [SimpleNamespace(id=number, batch_id=batch, seq=1, source="internal", setup_hours=0, unit_hours=2,
                                  machine_id="M1", operator_id="O1", op_type_id="OT1", op_type_name="work")
                  for number, batch in ((1, "B1"), (2, "B2"))]
    batches = {"B1": SimpleNamespace(quantity=1, priority="normal", due_date="2026-10-14", ready_date=None),
               "B2": SimpleNamespace(quantity=1, priority="urgent", due_date="2026-10-15", ready_date="2026-10-15")}
    seeds = [SimpleNamespace(op_id=91, source="internal", machine_id="M1", operator_id="O2", start_time=at(1), end_time=at(3)),
             SimpleNamespace(op_id=92, source="internal", machine_id="M2", operator_id="O1", start_time=at(2), end_time=at(4))]
    downtime = {"M1": [(at(4), at(5)), (start, start), (None, start)]}
    pool = {"machines_by_op_type": {"OT1": ["M1"]}, "operators_by_machine": {"M1": ["O1"]},
            "operator_skills": {"O1": ["OT1"]}}
    original_merge, original_seed, original_downtime = v2_capacity._merge_segments, v2_capacity._seed_segments, v2_capacity._valid_segments

    def merge(values):
        merges.append(list(values))
        return original_merge(values)

    def seed(values):
        conversions.append(list(values))
        return original_seed(values)

    def valid_downtime(values):
        downtime_reads.append(list(values))
        return original_downtime(values)

    calendar = Calendar()
    with monkeypatch.context() as scoped:
        scoped.setattr(v2_capacity, "_merge_segments", merge)
        scoped.setattr(v2_capacity, "_seed_segments", seed)
        scoped.setattr(v2_capacity, "_valid_segments", valid_downtime)
        result = enrich_graph_ready_v2_metrics(
            {1: {"bottleneck_machine_score": 1}, 2: {"bottleneck_machine_score": 1}},
            operations=operations, batches=batches, start_dt=start, calendar_service=calendar, seed_results=seeds,
            resource_pool=pool, downtime_map=downtime,
            graph_ready_context={"predecessor_op_ids_by_op_id": {1: set(), 2: set()}})

    assert len(merges) == 1 and len(conversions) == 2 and len(downtime_reads) == 1
    assert len(calls) == 7 and calls.count((start, at(16), "normal", "O1")) == 2
    assert (at(16), at(40), "urgent", "O1") in calls and (start, at(40), "urgent", "O1") in calls
    fields = ("residual_capacity_window_hours", "residual_capacity_blocked_hours", "residual_capacity_hours")
    views = (result[1], result[2], result[2][BASELINE_ORDERING_FIELD])
    assert [tuple(row[key] for key in fields) for row in views] == [(16, 4, 12), (12, 0, 12), (20, 2, 18)]

    resource_seeds = v2_capacity.seed_results_by_resource_id(seeds)
    for op in operations:
        row = result[op.id]
        standalone = v2_capacity.residual_capacity_for_operation(
            op, batch=batches[op.batch_id], start_dt=at(row["residual_capacity_start_offset_hours"]),
            due_exclusive=at(16 if op.id == 1 else 40), calendar_service=calendar, downtime_map=downtime,
            seed_results_by_resource_id=resource_seeds, resource_pool=pool)
        assert tuple(standalone[key] for key in fields) == tuple(row[key] for key in fields)
    changed = v2_capacity.residual_capacity_for_operation(
        operations[0], batch=batches["B1"], start_dt=start, due_exclusive=at(16), calendar_service=calendar,
        downtime_map={}, seed_results_by_resource_id=resource_seeds, resource_pool=pool)
    assert changed["residual_capacity_blocked_hours"] == 3 and changed["residual_capacity_hours"] == 13

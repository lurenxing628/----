"""Fixed resource blocking is shared while operation calendar windows stay dynamic."""

from datetime import datetime, timedelta

import pytest

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph import v2_capacity, v2_keys, v2_ranks
from core.services.scheduler.run.optimizer.graph.v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import BASELINE_ORDERING_FIELD
from tests._support.algo_operations import make_algo_op, make_batch, make_schedule_result
from tests._support.optimizer_graph_ready_benchmark import ContinuousCalendar


def test_pair_blocking_is_prepared_once_across_feature_bases_and_operation_windows(monkeypatch):
    start = datetime(2026, 10, 14, 8)

    def at(hours):
        return start + timedelta(hours=hours)

    calls, merges, downtime_reads = [], [], []

    class Calendar:
        def capacity_hours_between(self, low, high, *, priority, operator_id):
            calls.append((low, high, priority, operator_id))
            return (high - low).total_seconds() / 3600 * (0.5 if priority == "urgent" else 1)

    operations = [make_algo_op(id=number, batch_id=batch, seq=1, source="internal", setup_hours=0.0, unit_hours=2.0,
                               machine_id="M1", operator_id="O1", op_type_id="OT1", op_type_name="work")
                  for number, batch in ((1, "B1"), (2, "B2"))]
    batches = {"B1": make_batch(batch_id="B1", quantity=1, priority="normal", due_date="2026-10-14", ready_date=None),
               "B2": make_batch(batch_id="B2", quantity=1, priority="urgent", due_date="2026-10-15",
                                ready_date="2026-10-15")}
    seeds = [make_schedule_result(op_id=91, batch_id="B0", source="internal", machine_id="M1", operator_id="O2",
                                  start_time=at(1), end_time=at(3)),
             make_schedule_result(op_id=92, batch_id="B0", source="internal", machine_id="M2", operator_id="O1",
                                  start_time=at(2), end_time=at(4))]
    downtime = {"M1": [(at(4), at(5)), (start, start), (None, start)]}
    pool = {"machines_by_op_type": {"OT1": ["M1"]}, "operators_by_machine": {"M1": ["O1"]},
            "machines_by_operator": {}, "operator_skills": {"O1": ["OT1"]}}
    original_merge, original_downtime = v2_capacity._merge_segments, v2_capacity._valid_segments

    def merge(values):
        merges.append(list(values))
        return original_merge(values)

    def valid_downtime(values):
        downtime_reads.append(list(values))
        return original_downtime(values)

    calendar = Calendar()
    with monkeypatch.context() as scoped:
        scoped.setattr(v2_capacity, "_merge_segments", merge)
        scoped.setattr(v2_capacity, "_valid_segments", valid_downtime)
        result = enrich_graph_ready_v2_metrics(
            {1: {"bottleneck_machine_score": 1}, 2: {"bottleneck_machine_score": 1}},
            operations=operations, batches=batches, start_dt=start, calendar_service=calendar, seed_results=seeds,
            resource_pool=pool, downtime_map=downtime,
            graph_ready_context={"predecessor_op_ids_by_op_id": {1: set(), 2: set()}})

    assert len(merges) == 1 and len(downtime_reads) == 1
    assert len(calls) == 5 and calls.count((start, at(16), "normal", "O1")) == 1
    assert (at(16), at(40), "urgent", "O1") in calls and (start, at(40), "urgent", "O1") in calls
    fields = ("residual_capacity_window_hours", "residual_capacity_blocked_hours", "residual_capacity_hours")
    views = (result[1], result[2], result[2][BASELINE_ORDERING_FIELD])
    assert [tuple(row[key] for key in fields) for row in views] == [(16, 4, 12), (12, 0, 12), (20, 2, 18)]

    resource_seeds = v2_capacity.seed_results_by_resource_id(seeds)
    prepared_blocking = v2_capacity.FixedResourceBlockingFacts(
        downtime_map=downtime, seed_results_by_resource_id=resource_seeds
    )
    for op in operations:
        row = result[op.id]
        standalone = v2_capacity.residual_capacity_for_operation(
            op, batch=batches[op.batch_id], start_dt=at(row["residual_capacity_start_offset_hours"]),
            due_exclusive=at(16 if op.id == 1 else 40), calendar_service=calendar,
            resource_pool=pool, prepared=prepared_blocking)
        assert tuple(standalone[key] for key in fields) == tuple(row[key] for key in fields)
    changed = v2_capacity.residual_capacity_for_operation(
        operations[0], batch=batches["B1"], start_dt=start, due_exclusive=at(16), calendar_service=calendar,
        resource_pool=pool, prepared=v2_capacity.FixedResourceBlockingFacts(
            downtime_map={}, seed_results_by_resource_id=resource_seeds))
    assert changed["residual_capacity_blocked_hours"] == 3 and changed["residual_capacity_hours"] == 13


def test_graph_resource_preparation_is_shared_by_full_and_per_operation_inputs(monkeypatch):
    from core.services.scheduler.graph import input_adapter

    rows = [make_algo_op(id=op_id, batch_id="B1", op_code="OP" + str(op_id), seq=op_id, source="internal",
                         setup_hours=0.0, unit_hours=1.0, op_type_id="T2" if op_id == 4 else "T1",
                         machine_id="M2" if op_id == 3 else None, operator_id=None) for op_id in range(1, 6)]
    batches = {"B1": make_batch(quantity=2)}
    pool = {"machines_by_op_type": {"T1": ["M1", "M2"], "T2": ["M1"]},
            "machines_by_operator": {},
            "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]},
            "operator_skills": {"O1": ["T1"], "O2": ["T1"]}}
    calls = {}
    helper = input_adapter._candidate_machine_ids

    def counted(*args, **kwargs):
        calls["_candidate_machine_ids"] = calls.get("_candidate_machine_ids", 0) + 1
        return helper(*args, **kwargs)

    monkeypatch.setattr(input_adapter, "_candidate_machine_ids", counted)

    full = input_adapter.build_operation_nodes_from_rows(rows, batches=batches, resource_pool=pool)
    assert calls == {"_candidate_machine_ids": 3}
    calls.clear()
    resources = input_adapter.GraphResourcePreparation(pool)
    per_operation = [input_adapter.build_operation_nodes_from_rows([row], batches=batches,
                     resource_preparation=resources)[0] for row in rows]
    assert calls == {"_candidate_machine_ids": 3}
    assert per_operation == full
    assert full[0].candidate_machine_ids == full[1].candidate_machine_ids == full[4].candidate_machine_ids == ("M1", "M2")
    assert full[2].candidate_machine_ids == ("M2",)
    assert full[3].candidate_machine_ids == ("M1",)


def test_multi_segment_seed_result_blocks_each_resource_only_during_its_segment():
    from core.algorithm_contracts.types import ScheduleResult
    from core.algorithms.greedy.seed import with_seed_resource_segments

    start = datetime(2026, 10, 14, 8)
    at = lambda hours: start + timedelta(hours=hours)
    seed_base = ScheduleResult(
        op_id=91, op_code="OP-SEED", batch_id="B0", seq=1,
        machine_id="M1", operator_id="O1",
        start_time=at(0), end_time=at(4), source="internal",
    )
    seed = with_seed_resource_segments(
        seed_base,
        [(at(0), at(2), "M1", "O1"), (at(2), at(4), "M2", "O2")],
    )
    pool = {
        "machines_by_op_type": {"OT1": ["M1", "M2"]},
        "machines_by_operator": {},
        "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]},
        "operator_skills": {"O1": ["OT1"], "O2": ["OT1"]},
    }
    prepared = v2_capacity.FixedResourceBlockingFacts(
        downtime_map={},
        seed_results_by_resource_id=v2_capacity.seed_results_by_resource_id([seed]),
    )
    batch = make_batch(batch_id="B1", quantity=1, priority="normal", due_date="2026-10-14", ready_date=None)
    for machine_id, operator_id in (("M1", "O1"), ("M2", "O2")):
        op = make_algo_op(
            id=1, batch_id="B1", seq=1, source="internal", setup_hours=0.0, unit_hours=2.0,
            machine_id=machine_id, operator_id=operator_id, op_type_id="OT1", op_type_name="work",
        )
        cap = v2_capacity.residual_capacity_for_operation(
            op, batch=batch, start_dt=start, due_exclusive=at(8),
            calendar_service=ContinuousCalendar(), resource_pool=pool, prepared=prepared,
        )
        assert cap["residual_capacity_window_hours"] == 8.0
        assert cap["residual_capacity_blocked_hours"] == 2.0
        assert cap["residual_capacity_hours"] == 6.0


def test_v2_feature_numbers_reject_non_numbers_with_the_feature_field():
    assert v2_capacity.non_negative_float("2.5", field="batch.quantity") == 2.5
    for value, kind in ((None, "必须是数字"), ("abc", "必须是数字"), (True, "必须是数字"), (2 ** 1100, "必须是数字"),
                        (float("nan"), "必须是有限数字"), (-1, "必须是非负数")):
        with pytest.raises(ValidationError, match=f"batch.quantity {kind}。") as caught:
            v2_capacity.non_negative_float(value, field="batch.quantity")
        assert caught.value.field == "graph_ready_v2_features"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "abc", None, True, 10 ** 400])
@pytest.mark.parametrize("read", [
    lambda metric: v2_keys.required_finite_metric(metric, "x"),
    lambda metric: v2_keys.required_positive_metric(metric, "x"),
    lambda metric: v2_keys.v2_priority_key_for_metric(metric, specs=((False, "x"),)),
])
def test_v2_priority_metrics_name_the_v2_feature_field_in_error_and_details(read, value):
    with pytest.raises(ValidationError, match="图指标 x 必须是有限数字。") as caught:
        read({"x": value})
    assert caught.value.field == caught.value.details["field"] == "graph_ready_v2_features"
    assert caught.value.details["reason"] == "graph_ready_bad_v2_feature"


@pytest.mark.parametrize(("field", "value"), [("impact_count", float("nan")), ("downstream_critical_minutes", -1),
                                              ("is_on_critical_path", 1), ("bottleneck_machine_score", None)])
def test_v2_graph_bonus_relabels_field_and_details_together(field, value):
    metric = {"is_on_critical_path": True, "impact_count": 1, "downstream_critical_minutes": 30, "bottleneck_machine_score": 0.5}
    weights = {"critical_path": 1.0, "successor_count": 0.5, "downstream_work_hours": 0.25, "bottleneck_machine": 2.0}
    with pytest.raises(ValidationError, match=field) as caught:
        v2_ranks.v2_metric_bonus({**metric, field: value}, weights=weights)
    assert caught.value.field == caught.value.details["field"] == "graph_ready_v2_features"
    assert caught.value.details["reason"] == "graph_ready_bad_v2_feature"

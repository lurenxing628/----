"""回归测试：GreedyScheduler 的 SGS 派工——评分阶段必须复用统一的 estimate_internal_slot 估算器且其排序与实际执行顺序一致（含 seed_results 占用资源后 B_B 先于 B_A），with_graph_priority_key 把图评分惩罚作为首位排序分量。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest import mock

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.downtime import occupy_resource
from core.algorithm_runtime.owned_timeline import OwnedSegments, OwnedTimeline
from core.algorithm_runtime.slot_overlap_reuse import (
    SlotOverlapReuse,
    overlap_reuse_for,
    sgs_overlap_reuse,
)
from core.algorithms.greedy.dispatch import sgs_scoring as sgs_scoring_module
from core.algorithms.greedy.dispatch.sgs_scoring import with_graph_priority_key
from core.algorithms.greedy.scheduler import GreedyScheduler
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.schedule_decode import config_snapshot, production_decode


@dataclass
class _Calendar:
    """Round-the-clock calendar at constant efficiency 1.0."""

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None):
        return dt

    def add_effective_hours(self, dt: datetime, hours: float, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours))

    def working_hours_between(self, start: datetime, end: datetime, priority=None, operator_id=None):
        return (end - start).total_seconds() / 3600.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


def _batch(batch_id: str):
    return make_batch(batch_id=batch_id, due_date="2026-01-02")


def test_sgs_internal_scoring_uses_shared_estimator_and_matches_execution_order():
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=config_snapshot(auto_assign_enabled="no"))

    batches = {"B_A": _batch("B_A"), "B_B": _batch("B_B")}
    operations = [
        make_algo_op(id=1, op_code="OP_A", batch_id="B_A", machine_id="M1", operator_id="O1",
                     setup_hours=1.0, unit_hours=0.0, op_type_id="OT1", op_type_name="车削"),
        make_algo_op(id=2, op_code="OP_B", batch_id="B_B", machine_id="M2", operator_id="O2",
                     setup_hours=1.0, unit_hours=0.0, op_type_id="OT1", op_type_name="车削"),
    ]
    seed_results = [
        ScheduleResult(
            op_id=101,
            op_code="SEED_M1_1",
            batch_id="SEED",
            seq=1,
            machine_id="M1",
            operator_id=None,
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=1),
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=102,
            op_code="SEED_O1",
            batch_id="SEED",
            seq=2,
            machine_id=None,
            operator_id="O1",
            start_time=start_dt + timedelta(hours=1),
            end_time=start_dt + timedelta(hours=2),
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=103,
            op_code="SEED_M1_2",
            batch_id="SEED",
            seq=3,
            machine_id="M1",
            operator_id=None,
            start_time=start_dt + timedelta(hours=2),
            end_time=start_dt + timedelta(hours=3),
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=104,
            op_code="SEED_B",
            batch_id="SEED",
            seq=4,
            machine_id="M2",
            operator_id="O2",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=2),
            source="internal",
            op_type_name=None,
        ),
    ]

    def _dispatch_key_by_end(inp):
        return (-inp.slack_hours, float(inp.batch_order), float(inp.seq), float(inp.op_id))

    with mock.patch.object(sgs_scoring_module, "estimate_internal_slot", wraps=sgs_scoring_module.estimate_internal_slot) as wrapped, mock.patch.object(
        sgs_scoring_module,
        "build_dispatch_key",
        side_effect=_dispatch_key_by_end,
    ):
        decoded = production_decode(
            scheduler,
            operations=operations,
            batches=batches,
            start_dt=start_dt,
            dispatch_mode="sgs",
            dispatch_rule="slack",
            batch_order_override=["B_A", "B_B"],
            seed_results=seed_results,
        )
    results, summary = decoded.results, decoded.summary

    assert summary.failed_ops == 0
    assert wrapped.call_count >= 2, "SGS 评分阶段应调用统一估算器"
    non_seed_results = [result for result in results if result.batch_id in {"B_A", "B_B"}]
    assert [result.batch_id for result in non_seed_results] == ["B_B", "B_A"]


def test_graph_priority_key_keeps_score_penalty_as_first_sort_component():
    penalized_high_graph = with_graph_priority_key((1.0, 0.0, 1.0), (-999.0, 0.0))
    unpenalized_low_graph = with_graph_priority_key((0.0, 999.0, 1.0), (0.0, 999.0))

    assert unpenalized_low_graph < penalized_high_graph


def test_sgs_native_order_keeps_seq_id_ties_and_missing_batch_with_raw_downtime():
    start = datetime(2026, 1, 1, 8)
    operations = [
        make_algo_op(id=op_id, op_code="OP" + str(op_id), batch_id=batch_id, seq=seq,
                     source="internal", machine_id=" M1 ", operator_id="O1", setup_hours=1.0,
                     unit_hours=0.0, op_type_id="OT1", op_type_name="cut")
        for op_id, batch_id, seq in ((4, "B_A", 2), (3, "B_A", 1), (1, "B_B", 1),
                                     (2, "B_A", 1), (5, "MISSING", 1))
    ]
    downtime = {" M1 ": [(start + timedelta(hours=3), start + timedelta(hours=4)),
                        (start + timedelta(hours=1), start + timedelta(hours=2))]}
    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=config_snapshot(auto_assign_enabled="no"))
    decoded = production_decode(
        scheduler, operations=operations, batches={"B_A": _batch("B_A"), "B_B": _batch("B_B")},
        start_dt=start, dispatch_mode="sgs", dispatch_rule="slack",
        batch_order_override=["B_A", "B_B"], machine_downtimes=downtime,
    )
    results, summary = decoded.results, decoded.summary

    assert [row.op_id for row in results] == [2, 3, 4, 1]
    assert [(row.start_time, row.end_time) for row in results] == [
        (start, start + timedelta(hours=1)),
        (start + timedelta(hours=2), start + timedelta(hours=3)),
        (start + timedelta(hours=4), start + timedelta(hours=5)),
        (start + timedelta(hours=5), start + timedelta(hours=6)),
    ]
    assert (summary.total_ops, summary.scheduled_ops, summary.failed_ops) == (5, 4, 1)
    assert summary.failure_details == [{"op_id": 5, "op_code": "OP5", "batch_id": "MISSING",
                                        "seq": 1, "code": "missing_batch"}]


def test_zero_hour_operation_is_a_point_event_that_busy_time_neither_shifts_nor_records():
    from tests._support.schedule_decode import production_decode_in_session

    start = datetime(2026, 1, 1, 8)
    busy = ScheduleResult(op_id=101, op_code="SEED", batch_id="SEED", seq=1, machine_id="M1", operator_id="O1",
                          start_time=start, end_time=start + timedelta(hours=2), source="internal",
                          op_type_name="cut")
    point_op = make_algo_op(id=1, op_code="POINT", batch_id="B_P", machine_id="M1", operator_id="O1",
                            setup_hours=0.0, unit_hours=0.0, op_type_id="OT2", op_type_name="mark")
    timed_op = make_algo_op(id=2, op_code="TIMED", batch_id="B_T", machine_id="M1", operator_id="O1",
                            setup_hours=1.0, unit_hours=0.0, op_type_id="OT1", op_type_name="cut")
    batches = {"B_P": _batch("B_P"), "B_T": _batch("B_T")}
    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=config_snapshot(auto_assign_enabled="no"))
    session, decoded = production_decode_in_session(
        scheduler, operations=[point_op, timed_op], batches=batches, seed_results=[busy], start_dt=start,
        dispatch_mode="sgs", dispatch_rule="slack", batch_order_override=["B_P", "B_T"],
        machine_downtimes={"M1": [(start, start + timedelta(hours=3))]}, resource_pool={},
    )
    rows = {row.op_id: row for row in decoded.results}

    # The point lands at its release inside busy and downtime blocks; the timed work still clears both.
    assert rows[1].start_time == rows[1].end_time == start
    assert (rows[2].start_time, rows[2].end_time) == (start + timedelta(hours=3), start + timedelta(hours=4))
    assert decoded.summary.failed_ops == 0
    preparation = session.native_preparation
    assert preparation.resource_claim_for(point_op) is None
    assert preparation.resource_claim_for(timed_op) is not None


def test_slot_overlap_reuse_certifies_short_owned_timeline_and_tracks_mutation_and_owner_identity():
    start = datetime(2026, 1, 1, 8)
    timeline = OwnedTimeline()
    occupy_resource(timeline, "M1", start, start + timedelta(hours=1))
    occupy_resource(timeline, "M1", start + timedelta(hours=2), start + timedelta(hours=3))

    with sgs_overlap_reuse(timeline):
        reuse = overlap_reuse_for(timeline)
        assert isinstance(reuse, SlotOverlapReuse)
        with mock.patch.object(
            OwnedSegments,
            "__iter__",
            autospec=True,
            side_effect=OwnedSegments.__iter__,
        ) as iter_spy:
            first_index = reuse.index("machine", "M1", timeline["M1"])
            assert iter_spy.call_count == 1
            assert first_index.shift_end(start, start + timedelta(hours=1)) == start + timedelta(hours=1)

            second_index = reuse.index("machine", "M1", timeline["M1"])
            assert second_index is first_index
            assert iter_spy.call_count == 1

        occupy_resource(timeline, "M1", start + timedelta(hours=4), start + timedelta(hours=5))
        updated_index = reuse.index("machine", "M1", timeline["M1"])
        assert updated_index is not first_index
        assert updated_index.shift_end(start + timedelta(hours=4), start + timedelta(hours=5)) == start + timedelta(hours=5)
        assert first_index.shift_end(start + timedelta(hours=4), start + timedelta(hours=5)) is None
        assert len(first_index) == 2

        other_timeline = OwnedTimeline()
        occupy_resource(other_timeline, "M1", start, start + timedelta(hours=1))
        occupy_resource(other_timeline, "M1", start + timedelta(hours=2), start + timedelta(hours=3))
        occupy_resource(other_timeline, "M1", start + timedelta(hours=6), start + timedelta(hours=7))
        other_index = reuse.index("machine", "M1", other_timeline["M1"])
        assert other_index is not updated_index
        assert other_index.shift_end(start + timedelta(hours=4), start + timedelta(hours=5)) is None
        assert other_index.shift_end(start + timedelta(hours=6), start + timedelta(hours=7)) == start + timedelta(hours=7)

    assert overlap_reuse_for(timeline) is None


def test_slot_overlap_reuse_compares_borrowed_list_edits_and_leaves_plain_dict_untouched():
    start = datetime(2026, 1, 1, 8)
    borrowed_segments = [
        (start, start + timedelta(hours=1)),
        (start + timedelta(hours=2), start + timedelta(hours=3)),
    ]
    plain_timeline = {"M1": borrowed_segments}

    with sgs_overlap_reuse(plain_timeline):
        assert overlap_reuse_for(plain_timeline) is None
        assert type(plain_timeline) is dict
        assert plain_timeline["M1"] is borrowed_segments

    reuse = SlotOverlapReuse()
    initial_index = reuse.index("machine", "M1", borrowed_segments)
    assert initial_index.shift_end(start + timedelta(hours=2), start + timedelta(hours=3)) == start + timedelta(hours=3)
    assert initial_index.shift_end(start + timedelta(hours=4), start + timedelta(hours=5)) is None

    borrowed_segments[1] = (start + timedelta(hours=4), start + timedelta(hours=5))
    edited_index = reuse.index("machine", "M1", borrowed_segments)
    assert edited_index is not initial_index
    assert edited_index.shift_end(start + timedelta(hours=2), start + timedelta(hours=3)) is None
    assert edited_index.shift_end(start + timedelta(hours=4), start + timedelta(hours=5)) == start + timedelta(hours=5)
    assert initial_index.shift_end(start + timedelta(hours=2), start + timedelta(hours=3)) == start + timedelta(hours=3)

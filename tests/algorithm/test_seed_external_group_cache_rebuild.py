"""合同测试（audit 2026-07-20 A14）：seed 注入必须按组键重建 merged 外协组缓存。

背景：seed 注入原本只重建资源占用与批次进度，不重建 external_group_cache；merged 外协组
被部分种入时，未种成员 cache miss 会以推进后的批次进度为起点再消耗一次完整
ext_group_total_days，打破组内"同起止"合同且零留痕。
触发面口径（第二核查修正）：健康冻结窗对 merged 组通常全进全出；真实触发偏部分种子、
版本间工艺模板变化或旧计划异常。
合同：
1) 种入部分组成员后，未种成员复用同一组块，不另起新块；
2) 同组 seed 成员起止不一致时不写缓存、降级留痕（warning + 计数），未种成员按现状另起块；
3) 生产过滤后使用种子携带的精确身份；普通 API 缺少双方资料时不猜测归属。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.greedy.external_groups import rebuild_external_group_cache_from_seeds
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.algorithms.greedy.seed import seed_external_group_keys
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_input_runtime_support import _merge_execution_and_freeze_seed_results
from core.services.scheduler.run.schedule_input_seed_metadata import with_frozen_external_seed_metadata
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results

BASE = datetime(2026, 7, 20, 8, 0, 0)


class _Calendar:
    def adjust_to_working_time(self, dt, priority=None, operator_id=None):
        return dt

    def add_working_hours(self, dt, hours, priority=None, operator_id=None):
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt, operator_id=None):
        return 1.0

    def add_calendar_days(self, dt, days, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


def _batch(batch_id="B1"):
    return SimpleNamespace(
        batch_id=batch_id,
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )


def _merged_external_op(op_id, seq, *, batch_id="B1", group_id="G1", total_days=3.0):
    return SimpleNamespace(
        id=op_id,
        op_code=f"OP{op_id}",
        batch_id=batch_id,
        seq=seq,
        source="external",
        ext_merge_mode="merged",
        ext_group_id=group_id,
        ext_group_total_days=total_days,
        ext_days=None,
        op_type_name=None,
    )


def _external_seed(op_id, seq, start, end, *, batch_id="B1"):
    return ScheduleResult(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id=batch_id,
        seq=seq,
        start_time=start,
        end_time=end,
        source="external",
    )


def test_rebuild_writes_consistent_group_block_and_counts():
    ops = [_merged_external_op(1, 1), _merged_external_op(2, 2)]
    seeds = [_external_seed(1, 1, BASE, BASE + timedelta(days=3))]
    cache = {}
    warnings = []
    algo_stats = {}

    rebuild_external_group_cache_from_seeds(
        seed_results=seeds,
        operations=ops,
        external_group_cache=cache,
        warnings=warnings,
        algo_stats=algo_stats,
    )

    assert cache == {("B1", "G1"): (BASE, BASE + timedelta(days=3))}
    assert warnings == []
    assert algo_stats["fallback_counts"]["seed_external_group_cache_rebuilt_count"] == 1


def test_rebuild_inconsistent_group_degrades_visibly_and_skips_cache():
    ops = [
        _merged_external_op(1, 1),
        _merged_external_op(2, 2),
        _merged_external_op(3, 3),
    ]
    seeds = [
        _external_seed(1, 1, BASE, BASE + timedelta(days=3)),
        _external_seed(2, 2, BASE + timedelta(days=1), BASE + timedelta(days=4)),
    ]
    cache = {}
    warnings = []
    algo_stats = {}

    rebuild_external_group_cache_from_seeds(
        seed_results=seeds,
        operations=ops,
        external_group_cache=cache,
        warnings=warnings,
        algo_stats=algo_stats,
    )

    assert cache == {}
    assert len(warnings) == 1
    assert "G1" in warnings[0]
    assert "B1" in warnings[0]
    assert "起止不一致" in warnings[0]
    assert algo_stats["fallback_counts"]["seed_external_group_block_inconsistent_count"] == 1
    assert "seed_external_group_cache_rebuilt_count" not in algo_stats["fallback_counts"]


def test_rebuild_skips_seed_whose_operation_metadata_is_absent():
    # 普通算法 API 未提供种子身份且不传重叠工序时，保持不猜归属的原有行为。
    ops = [_merged_external_op(2, 2)]
    seeds = [_external_seed(1, 1, BASE, BASE + timedelta(days=3))]
    cache = {}
    warnings = []
    algo_stats = {}

    rebuild_external_group_cache_from_seeds(
        seed_results=seeds,
        operations=ops,
        external_group_cache=cache,
        warnings=warnings,
        algo_stats=algo_stats,
    )

    assert cache == {}
    assert warnings == []
    assert algo_stats.get("fallback_counts", {}) == {} or (
        "seed_external_group_cache_rebuilt_count" not in algo_stats["fallback_counts"]
    )


def test_schedule_partially_seeded_merged_group_reuses_seed_block():
    scheduler = GreedyScheduler(calendar_service=_Calendar())
    op1 = _merged_external_op(1, 1)
    op2 = _merged_external_op(2, 2)
    seed_end = BASE + timedelta(days=3)

    results, summary, _strategy, _params = scheduler.schedule(
        operations=[op1, op2],
        batches={"B1": _batch()},
        start_dt=BASE,
        dispatch_mode="batch_order",
        seed_results=[_external_seed(1, 1, BASE, seed_end)],
    )

    assert summary.failed_ops == 0
    by_op = {r.op_id: r for r in results}
    # 未种成员复用 seed 成员的组块：同起止，不再另起一整段 total_days。
    assert by_op[2].start_time == BASE
    assert by_op[2].end_time == seed_end
    counters = scheduler._last_algo_stats["fallback_counts"]
    assert counters["seed_external_group_cache_rebuilt_count"] == 1


def test_schedule_inconsistent_seed_blocks_degrade_and_start_new_block():
    scheduler = GreedyScheduler(calendar_service=_Calendar())
    op1 = _merged_external_op(1, 1)
    op2 = _merged_external_op(2, 2)
    op3 = _merged_external_op(3, 3)

    results, summary, _strategy, _params = scheduler.schedule(
        operations=[op1, op2, op3],
        batches={"B1": _batch()},
        start_dt=BASE,
        dispatch_mode="batch_order",
        seed_results=[
            _external_seed(1, 1, BASE, BASE + timedelta(days=3)),
            _external_seed(2, 2, BASE + timedelta(days=1), BASE + timedelta(days=4)),
        ],
    )

    assert summary.failed_ops == 0
    by_op = {r.op_id: r for r in results}
    # 不一致组不写缓存：未种成员按批次进度（max seed end = base+4d）另起新组块。
    assert by_op[3].start_time == BASE + timedelta(days=4)
    assert by_op[3].end_time == BASE + timedelta(days=7)
    assert any("起止不一致" in w and "G1" in w for w in summary.warnings)
    counters = scheduler._last_algo_stats["fallback_counts"]
    assert counters["seed_external_group_block_inconsistent_count"] == 1


def _metadata_seed(*, op_id=1, batch_id="B1", group_id="G1"):
    item = asdict(_external_seed(op_id, 1, BASE, BASE + timedelta(days=3), batch_id=batch_id))
    item["_external_group_metadata"] = {"op_id": op_id, "batch_id": batch_id, "ext_group_id": group_id}
    return item


def test_internal_seed_metadata_rebuilds_without_any_operations_and_is_not_serialized():
    seed = coerce_seed_results([_metadata_seed()], optimizer_algo_stats={})[0]
    cache = {}
    rebuild_external_group_cache_from_seeds(
        seed_results=[seed], operations=[], external_group_cache=cache, warnings=[], algo_stats={},
        seed_group_keys=seed_external_group_keys([seed]),
    )
    assert cache == {("B1", "G1"): (BASE, BASE + timedelta(days=3))}
    assert asdict(seed) == asdict(_external_seed(1, 1, BASE, BASE + timedelta(days=3)))
    assert set(vars(seed)) == set(asdict(seed))


@pytest.mark.parametrize("metadata", [None, {}, {"op_id": 1},
    {"op_id": 2, "batch_id": "B1", "ext_group_id": "G1"},
    {"op_id": 1, "batch_id": "B2", "ext_group_id": "G1"},
    {"op_id": 1, "batch_id": "B1", "ext_group_id": ""},
    {"op_id": True, "batch_id": "B1", "ext_group_id": "G1"},
])
def test_malformed_or_mismatched_metadata_is_rejected_at_seed_boundary(metadata):
    item = _metadata_seed()
    item["_external_group_metadata"] = metadata
    stats = {}
    with pytest.raises(ValidationError) as caught:
        coerce_seed_results([item], optimizer_algo_stats=stats)
    assert caught.value.details["reason"] == "invalid_seed_results"
    assert stats["fallback_counts"]["optimizer_seed_result_invalid_count"] == 1


@pytest.mark.parametrize("changes", [{"ext_group_id": "G2"}, {"batch_id": "B2"},
    {"ext_merge_mode": "separate"}, {"source": "internal"},
])
def test_overlap_metadata_conflicts_stop_instead_of_choosing_one(changes):
    op = _merged_external_op(1, 1)
    vars(op).update(changes)
    cache = {}
    seeds = coerce_seed_results([_metadata_seed()], optimizer_algo_stats={})
    with pytest.raises(ValidationError):
        rebuild_external_group_cache_from_seeds(
            seed_results=seeds, seed_group_keys=seed_external_group_keys(seeds),
            operations=[op], external_group_cache=cache, warnings=[], algo_stats={},
        )
    assert cache == {}


@pytest.mark.parametrize("changes,cause", [({"id": 99}, "missing_operation"),
    ({"batch_id": "B2"}, "operation_identity_mismatch"),
    ({"seq": 2}, "operation_identity_mismatch"),
    ({"ext_group_id": ""}, "invalid_merged_group"),
    ({"merge_context_degraded": True}, "invalid_merged_group"),
    ({"ext_merge_mode": "guess"}, "invalid_merge_mode"),
])
def test_freeze_enrichment_requires_exact_current_operation(changes, cause):
    op = _merged_external_op(1, 1)
    vars(op).update(changes)
    with pytest.raises(ValidationError) as caught:
        with_frozen_external_seed_metadata(
            [asdict(_external_seed(1, 1, BASE, BASE + timedelta(days=3)))],
            frozen_op_ids={1}, algo_ops=[op],
        )
    assert caught.value.details["cause"] == cause


def test_duplicate_frozen_operation_metadata_is_rejected():
    with pytest.raises(ValidationError) as caught:
        with_frozen_external_seed_metadata(
            [asdict(_external_seed(1, 1, BASE, BASE + timedelta(days=3)))],
            frozen_op_ids={1}, algo_ops=[_merged_external_op(1, 1), _merged_external_op(1, 1, group_id="G2")],
        )
    assert caught.value.details["cause"] == "duplicate_operation"


def test_missing_merge_context_is_not_assumed_separate():
    op = _merged_external_op(1, 1)
    del op.ext_merge_mode
    with pytest.raises(ValidationError) as caught:
        with_frozen_external_seed_metadata(
            [asdict(_external_seed(1, 1, BASE, BASE + timedelta(days=3)))], frozen_op_ids={1}, algo_ops=[op],
        )
    assert caught.value.details["cause"] == "missing_merge_context"


def test_internal_source_cannot_claim_external_seed_metadata():
    item = dict(_metadata_seed(), source="internal")
    with pytest.raises(ValidationError):
        coerce_seed_results([item], optimizer_algo_stats={})


def test_freeze_execution_merge_retains_fact_fields_and_does_not_mutate_inputs():
    frozen = asdict(_external_seed(1, 1, BASE, BASE + timedelta(days=3)))
    execution = dict(frozen, seed_source="execution_fact", state_revision="1:7:3")
    before = deepcopy((frozen, execution))
    merged = _merge_execution_and_freeze_seed_results(execution_seed_results=[execution], freeze_seed_results=[frozen])
    enriched = with_frozen_external_seed_metadata(merged, frozen_op_ids={1}, algo_ops=[_merged_external_op(1, 1)])
    seeds = coerce_seed_results(enriched, optimizer_algo_stats={})
    assert asdict(seeds[0]) == execution
    assert (frozen, execution) == before
    assert merged == [execution]


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
def test_seed_group_identity_is_batch_scoped_and_survives_repeated_candidates(dispatch_mode):
    seeds = coerce_seed_results([_metadata_seed()], optimizer_algo_stats={})
    operations = [_merged_external_op(2, 2), _merged_external_op(3, 1, batch_id="B2")]
    scheduler = GreedyScheduler(calendar_service=_Calendar())
    snapshots = []
    for _ in range(2):
        results, summary, _, _ = scheduler.schedule(
            operations=operations, batches={"B1": _batch(), "B2": _batch("B2")},
            start_dt=BASE + timedelta(days=1), dispatch_mode=dispatch_mode, seed_results=seeds,
        )
        assert summary.failed_ops == 0
        by_op = {result.op_id: result for result in results}
        assert by_op[2].start_time == BASE
        assert by_op[3].start_time == BASE + timedelta(days=1)
        assert all(type(result) is ScheduleResult for result in results)
        snapshots.append([asdict(result) for result in results])
    assert snapshots[0] == snapshots[1]

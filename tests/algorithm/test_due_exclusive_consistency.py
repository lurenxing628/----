"""回归测试：交期判定的“排他下界”口径在三处统计中一致——共享的 due_exclusive() 把交期次日 0 点作为边界，使得完工时间正好落在该边界时，evaluation.compute_metrics、schedule_summary.build_result_summary 与 common.compute_overdue_bucket_groups 都判为逾期 1 单且边界拖期为 0。"""

import time
from datetime import date, datetime

from tests._support.algo_operations import make_algo_op, make_batch


def test_due_exclusive_consistency() -> None:

    from core.algorithm_contracts.date_parsers import due_exclusive
    from core.algorithm_contracts.sort_strategies import SortStrategy
    from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
    from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
    from core.models.batch import Batch
    from core.models.schedule_config_runtime_fields import default_snapshot_values
    from core.models.schedule_config_runtime_snapshot import snapshot_from_values
    from core.services.common.overdue_calculations import compute_overdue_bucket_groups
    from core.services.scheduler.contracts.schedule_summary_types import SummaryBuildContext
    from core.services.scheduler.summary.schedule_summary import build_result_summary

    due_d = date(2026, 2, 1)
    finish_dt = datetime(2026, 2, 2, 0, 0, 0)
    expected_due_exclusive = datetime(2026, 2, 2, 0, 0, 0)

    assert due_exclusive(due_d) == expected_due_exclusive, "共享 due_exclusive 不一致"

    batch = Batch(batch_id="B001", part_no="P001", due_date="2026-02-01", priority="normal", quantity=1)
    result = ScheduleResult(
        op_id=1,
        op_code="OP001",
        batch_id="B001",
        seq=10,
        machine_id="MC1",
        operator_id="OP1",
        start_time=datetime(2026, 2, 1, 8, 0, 0),
        end_time=finish_dt,
        source="internal",
        op_type_name="A工种",
    )

    operations = [make_algo_op(id=1, batch_id="B001")]
    metrics = compute_metrics([result], {"B001": batch}, expected_operations=operations, failure_details=[])
    prepared = prepare_evaluation_context(batches={"B001": batch}, expected_operations=operations, seed_results=())
    assert compute_metrics([result], {"B001": batch}, expected_operations=operations, failure_details=[],
                           prepared=prepared).to_dict() == metrics.to_dict()
    assert metrics.overdue_count == 1, f"evaluation overdue_count 应为 1，实际={metrics.overdue_count}"
    assert abs(metrics.total_tardiness_hours - 0.0) < 1e-9, f"边界拖期应为 0，实际={metrics.total_tardiness_hours}"

    cfg = snapshot_from_values(
        dict(
            default_snapshot_values(),
            freeze_window_enabled="no",
            auto_assign_enabled="no",
            freeze_window_days=0,
            objective="min_overdue",
        )
    )
    summary = ScheduleSummary(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )
    summary_ctx = SummaryBuildContext(
        cfg=cfg,
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=datetime(2026, 2, 1, 8, 0, 0),
        end_date=None,
        batches={"B001": batch},
        operations=[],
        results=[result],
        summary=summary,
        used_strategy=SortStrategy.PRIORITY_FIRST,
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=metrics,
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        scheduled_op_ids={1},
        downtime_meta={},
        simulate=False,
        t0=time.time(),
    )
    result_summary_obj = build_result_summary(
        ctx=summary_ctx,
    )
    overdue_batches = result_summary_obj.get("overdue_batches") or {}
    assert int(overdue_batches.get("count") or 0) == 1, f"schedule_summary overdue_count 应为 1，实际={overdue_batches}"

    scheduled, unscheduled, _invalid_time = compute_overdue_bucket_groups(
        [{"batch_id": "B001", "due_date": "2026-02-01", "finish_time": "2026-02-02 00:00:00"}],
        now_dt=finish_dt,
    )
    assert len(scheduled) == 1, f"report scheduled overdue 应为 1，实际={scheduled}"
    assert len(unscheduled) == 0, f"report unscheduled overdue 应为 0，实际={unscheduled}"


def test_due_exclusive_max_due_sentinel_end_to_end_not_overdue() -> None:
    """端到端回归：交期填 9999-12-31（ERP 常用"无交期"哨兵）时，排产评估与逾期报表
    都不得抛 OverflowError，且口径与 None→datetime.max 一致——永远判为不逾期。"""

    from core.algorithm_contracts.types import ScheduleResult
    from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
    from core.services.common.overdue_calculations import compute_overdue_bucket_groups

    finish_dt = datetime(2026, 2, 2, 0, 0, 0)
    batch = make_batch(batch_id="B900", due_date="9999-12-31")
    result = ScheduleResult(
        op_id=1,
        op_code="OP001",
        batch_id="B900",
        seq=10,
        machine_id="MC1",
        operator_id="OP1",
        start_time=datetime(2026, 2, 1, 8, 0, 0),
        end_time=finish_dt,
        source="internal",
        op_type_name="A工种",
    )

    operations = [make_algo_op(id=1, batch_id="B900")]
    metrics = compute_metrics([result], {"B900": batch}, expected_operations=operations, failure_details=[])
    prepared = prepare_evaluation_context(batches={"B900": batch}, expected_operations=operations, seed_results=())
    assert compute_metrics([result], {"B900": batch}, expected_operations=operations, failure_details=[],
                           prepared=prepared).to_dict() == metrics.to_dict()
    assert metrics.overdue_count == 0, f"9999-12-31 哨兵交期不应判逾期，实际 overdue_count={metrics.overdue_count}"
    assert abs(metrics.total_tardiness_hours - 0.0) < 1e-9, f"9999-12-31 哨兵交期拖期应为 0，实际={metrics.total_tardiness_hours}"

    scheduled, unscheduled, invalid_time = compute_overdue_bucket_groups(
        [
            {"batch_id": "B900", "due_date": "9999-12-31", "finish_time": "2026-02-02 00:00:00"},
            {"batch_id": "B901", "due_date": "9999-12-31", "finish_time": None},
        ],
        now_dt=finish_dt,
    )
    assert scheduled == [], f"9999-12-31 哨兵交期不应进已排程逾期桶，实际={scheduled}"
    assert unscheduled == [], f"9999-12-31 哨兵交期不应进未排程逾期桶，实际={unscheduled}"
    assert invalid_time == [], f"9999-12-31 是合法哨兵交期，不应进异常桶，实际={invalid_time}"


def test_prepared_due_sources_keep_order_and_standalone_uses_current_inputs() -> None:
    from core.algorithm_contracts.types import ScheduleResult
    from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
    from core.algorithms.evaluation_completion import collect_batch_completion

    # Batch keys are database primary keys (workbench/run/input.py), already trimmed and unique.
    batches = {
        "B1": make_batch(batch_id="B1", due_date="2026-01-01", priority="critical"),
        "B3": make_batch(batch_id="B3", due_date="bad-due", priority="urgent"),
        "B2": make_batch(batch_id="B2", due_date=None, priority="normal"),
    }
    operation = make_algo_op(id=1, batch_id="B1")
    result = ScheduleResult(op_id=1, op_code="OP1", batch_id="B1", seq=1, machine_id="M1", operator_id="O1",
                            start_time=datetime(2026, 1, 1, 8), end_time=datetime(2026, 1, 3, 1), source="internal")
    prepared = prepare_evaluation_context(batches=batches, expected_operations=[operation], seed_results=())
    metrics = compute_metrics([result], batches, expected_operations=[operation], failure_details=[], prepared=prepared)
    assert (metrics.overdue_count, metrics.total_tardiness_hours, metrics.weighted_tardiness_hours) == (1, 25.0, 75.0)
    assert metrics.unscheduled_batch_ids_sample == ["B3(bad-due)", "B2"]
    assert metrics.invalid_due_batch_ids_sample == ["B3"]
    absent = collect_batch_completion([], failure_details=[{"op_id": 1, "batch_id": "B1"}], prepared=prepared)
    assert absent.incomplete_work_weight == 6.0  # critical 3 + urgent 2 + normal 1.
    empty = compute_metrics([], batches, expected_operations=[operation], failure_details=[], prepared=prepared)
    assert empty.unscheduled_batch_ids_sample == ["B1(2026-01-01)", "B3(bad-due)", "B2"]

    batches["B1"].priority = "normal"
    batches["B1"].due_date = "2026-01-02"
    standalone = compute_metrics([result], batches, expected_operations=[operation], failure_details=[])
    assert (standalone.overdue_count, standalone.total_tardiness_hours, standalone.weighted_tardiness_hours) == (1, 1.0, 1.0)
    operation.id = 2
    current = compute_metrics([result], batches, expected_operations=[operation], failure_details=[])
    assert current.completion.missing_operation_count == current.completion.unexpected_result_count == 1

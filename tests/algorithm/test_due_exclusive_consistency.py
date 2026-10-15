"""回归测试：交期判定的“排他下界”口径在三处统计中一致——共享的 due_exclusive() 把交期次日 0 点作为边界，使得完工时间正好落在该边界时，evaluation.compute_metrics、schedule_summary.build_result_summary 与 report.compute_overdue_buckets 都判为逾期 1 单且边界拖期为 0。"""

import time
from datetime import date, datetime
from types import SimpleNamespace

import pytest


class _StubSvc:
    logger = None

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_due_exclusive_consistency() -> None:

    from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
    from core.algorithms.greedy.date_parsers import due_exclusive
    from core.algorithms.types import ScheduleResult
    from core.services.report.calculations import compute_overdue_buckets
    from core.services.scheduler.summary.schedule_summary import build_result_summary
    from core.services.scheduler.summary.schedule_summary_types import SummaryBuildContext

    due_d = date(2026, 2, 1)
    finish_dt = datetime(2026, 2, 2, 0, 0, 0)
    expected_due_exclusive = datetime(2026, 2, 2, 0, 0, 0)

    assert due_exclusive(due_d) == expected_due_exclusive, "共享 due_exclusive 不一致"

    batch = SimpleNamespace(batch_id="B001", due_date="2026-02-01", priority="normal", quantity=1)
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

    metrics = compute_metrics([result], {"B001": batch})
    assert compute_metrics([result], {"B001": batch}, prepared=prepare_evaluation_context(batches={"B001": batch})).to_dict() == metrics.to_dict()
    assert metrics.overdue_count == 1, f"evaluation overdue_count 应为 1，实际={metrics.overdue_count}"
    assert abs(metrics.total_tardiness_hours - 0.0) < 1e-9, f"边界拖期应为 0，实际={metrics.total_tardiness_hours}"

    svc = _StubSvc()
    cfg = SimpleNamespace(freeze_window_enabled="no", auto_assign_enabled="no", freeze_window_days=0, objective="min_overdue")
    summary = SimpleNamespace(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=[],
        errors=[],
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
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        downtime_meta={},
        simulate=False,
        t0=time.time(),
    )
    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        svc,
        ctx=summary_ctx,
    )
    overdue_batches = result_summary_obj.get("overdue_batches") or {}
    assert int(overdue_batches.get("count") or 0) == 1, f"schedule_summary overdue_count 应为 1，实际={overdue_batches}"

    scheduled, unscheduled, _as_of = compute_overdue_buckets(
        [{"batch_id": "B001", "due_date": "2026-02-01", "finish_time": "2026-02-02 00:00:00"}],
        now_dt=finish_dt,
    )
    assert len(scheduled) == 1, f"report scheduled overdue 应为 1，实际={scheduled}"
    assert len(unscheduled) == 0, f"report unscheduled overdue 应为 0，实际={unscheduled}"


def test_due_exclusive_max_due_sentinel_end_to_end_not_overdue() -> None:
    """端到端回归：交期填 9999-12-31（ERP 常用"无交期"哨兵）时，排产评估与逾期报表
    都不得抛 OverflowError，且口径与 None→datetime.max 一致——永远判为不逾期。"""

    from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
    from core.algorithms.types import ScheduleResult
    from core.services.common.overdue_calculations import compute_overdue_bucket_groups

    finish_dt = datetime(2026, 2, 2, 0, 0, 0)
    batch = SimpleNamespace(batch_id="B900", due_date="9999-12-31", priority="normal", quantity=1)
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

    metrics = compute_metrics([result], {"B900": batch})
    assert compute_metrics([result], {"B900": batch}, prepared=prepare_evaluation_context(batches={"B900": batch})).to_dict() == metrics.to_dict()
    assert metrics.overdue_count == 0, f"9999-12-31 哨兵交期不应判逾期，实际 overdue_count={metrics.overdue_count}"
    assert abs(metrics.total_tardiness_hours - 0.0) < 1e-9, f"9999-12-31 哨兵交期拖期应为 0，实际={metrics.total_tardiness_hours}"

    scheduled, unscheduled, invalid_time, _as_of = compute_overdue_bucket_groups(
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
    from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
    from core.algorithms.evaluation_completion import collect_batch_completion
    from core.algorithms.types import ScheduleResult

    batches = {
        " B1 ": SimpleNamespace(due_date="2026-01-01", priority="critical"),
        "B1": SimpleNamespace(due_date=date(2026, 1, 2), priority="normal"),
        " B3 ": SimpleNamespace(due_date="bad-due", priority="urgent"),
        "B2": SimpleNamespace(due_date=None, priority="normal"),
    }
    operation = SimpleNamespace(id=1, batch_id="B1")
    result = ScheduleResult(op_id=1, op_code="OP1", batch_id="B1", seq=1, machine_id="M1", operator_id="O1",
                            start_time=datetime(2026, 1, 1, 8), end_time=datetime(2026, 1, 3, 1), source="internal")
    prepared = prepare_evaluation_context(batches=batches, expected_operations=[operation])
    metrics = compute_metrics([result], batches, prepared=prepared)
    assert (metrics.overdue_count, metrics.total_tardiness_hours, metrics.weighted_tardiness_hours) == (2, 26.0, 76.0)
    assert metrics.unscheduled_batch_ids_sample == ["B3(bad-due)", "B2"]
    assert metrics.invalid_due_batch_ids_sample == ["B3"]
    absent = collect_batch_completion([], batches, failure_details=[{"op_id": 1}], prepared=prepared)
    assert absent.incomplete_work_weight == 4.0  # normalized B1 uses its last source's normal weight.
    empty = compute_metrics([], batches, prepared=prepared)
    assert empty.unscheduled_batch_ids_sample == ["B1(2026-01-01)", "B1(2026-01-02)", "B3(bad-due)", "B2"]

    batches["B1"].priority = "critical"
    batches["B1"].due_date = "2026-01-04"
    standalone = compute_metrics([result], batches)
    assert standalone.completion is None
    assert (standalone.overdue_count, standalone.total_tardiness_hours, standalone.weighted_tardiness_hours) == (1, 25.0, 75.0)
    operation.id = 2
    current = compute_metrics([result], batches, expected_operations=[operation])
    assert current.completion.missing_operation_count == current.completion.unexpected_result_count == 1
    for evidence in ({"seed_results": []}, {"failure_details": []}):
        with pytest.raises(ValueError, match="Completion evidence requires expected_operations"):
            compute_metrics([result], batches, **evidence)

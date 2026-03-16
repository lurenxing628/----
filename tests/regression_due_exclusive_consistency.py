import os
import sys
import time
from datetime import date, datetime
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.dispatch_rules import _due_exclusive as dispatch_due_exclusive
    from core.algorithms.evaluation import _due_exclusive as eval_due_exclusive
    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.ortools_bottleneck import _due_exclusive as ort_due_exclusive
    from core.algorithms.types import ScheduleResult
    from core.services.report.calculations import compute_overdue_buckets
    from core.services.scheduler.schedule_summary import build_result_summary

    due_d = date(2026, 2, 1)
    finish_dt = datetime(2026, 2, 2, 0, 0, 0)
    expected_due_exclusive = datetime(2026, 2, 2, 0, 0, 0)

    assert eval_due_exclusive(due_d) == expected_due_exclusive, "evaluation due_exclusive 不一致"
    assert dispatch_due_exclusive(due_d) == expected_due_exclusive, "dispatch_rules due_exclusive 不一致"
    assert ort_due_exclusive(due_d) == expected_due_exclusive, "ortools due_exclusive 不一致"

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
    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        svc,
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
    overdue_batches = result_summary_obj.get("overdue_batches") or {}
    assert int(overdue_batches.get("count") or 0) == 1, f"schedule_summary overdue_count 应为 1，实际={overdue_batches}"

    scheduled, unscheduled, _as_of = compute_overdue_buckets(
        [{"batch_id": "B001", "due_date": "2026-02-01", "finish_time": "2026-02-02 00:00:00"}],
        now_dt=finish_dt,
    )
    assert len(scheduled) == 1, f"report scheduled overdue 应为 1，实际={scheduled}"
    assert len(unscheduled) == 0, f"report unscheduled overdue 应为 0，实际={unscheduled}"

    print("OK")


if __name__ == "__main__":
    main()

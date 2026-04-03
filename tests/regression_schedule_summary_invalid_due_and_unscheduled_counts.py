from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace


class _SummarySvc:
    logger = None

    @staticmethod
    def _normalize_text(value):
        return "" if value is None else str(value).strip()

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import ScheduleResult
    from core.algorithms.evaluation import compute_metrics
    from core.services.scheduler.schedule_summary import build_result_summary

    start_dt = datetime(2026, 4, 1, 8, 0, 0)
    result_end = datetime(2026, 4, 1, 12, 0, 0)

    batches = {
        "B_DONE": SimpleNamespace(batch_id="B_DONE", due_date="2099-12-31", priority="normal", quantity=1),
        "B_DUE_BAD": SimpleNamespace(batch_id="B_DUE_BAD", due_date="2026-02-31", priority="high", quantity=1),
        "B_PENDING": SimpleNamespace(batch_id="B_PENDING", due_date="2099-12-30", priority="normal", quantity=1),
    }
    results = [
        ScheduleResult(
            op_id=1,
            op_code="OP-1",
            batch_id="B_DONE",
            seq=10,
            source="internal",
            machine_id="MC100",
            operator_id="OP100",
            op_type_name="数车",
            start_time=start_dt,
            end_time=result_end,
        )
    ]
    summary = SimpleNamespace(success=False, total_ops=3, scheduled_ops=1, failed_ops=2, warnings=[], errors=["部分工序失败"])
    metrics = compute_metrics(results, batches)

    overdue_items, result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(
        _SummarySvc(),
        cfg={"freeze_window_enabled": "no", "auto_assign_enabled": "no"},
        version=7,
        normalized_batch_ids=["B_DONE", "B_DUE_BAD", "B_PENDING"],
        start_dt=start_dt,
        end_date=None,
        batches=batches,
        operations=[],
        results=results,
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(2.0, 0.0, 4.0, 0.0, 0.0),
        best_metrics=metrics,
        best_order=["B_DONE", "B_DUE_BAD", "B_PENDING"],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        simulate=False,
        t0=time.time() - 0.02,
    )

    assert result_status == "partial", f"result_status 应为 partial，实际 {result_status!r}"
    assert overdue_items == [], f"本例不应生成超期清单，实际 {overdue_items!r}"
    assert int(result_summary_obj.get("invalid_due_count") or 0) == 1, result_summary_obj
    assert result_summary_obj.get("invalid_due_batch_ids_sample") == ["B_DUE_BAD"], result_summary_obj
    assert int(result_summary_obj.get("unscheduled_batch_count") or 0) == 2, result_summary_obj

    unscheduled_sample = list(result_summary_obj.get("unscheduled_batch_ids_sample") or [])
    assert any(str(item).startswith("B_DUE_BAD") for item in unscheduled_sample), unscheduled_sample
    assert any(str(item).startswith("B_PENDING") for item in unscheduled_sample), unscheduled_sample

    counts = dict(result_summary_obj.get("counts") or {})
    assert int(counts.get("unscheduled_batch_count") or 0) == 2, counts

    algo_metrics = dict((result_summary_obj.get("algo") or {}).get("metrics") or {})
    assert int(algo_metrics.get("invalid_due_count") or 0) == 1, algo_metrics
    assert int(algo_metrics.get("unscheduled_batch_count") or 0) == 2, algo_metrics

    warnings = list(result_summary_obj.get("warnings") or [])
    assert any("due_date 格式不合法" in w for w in warnings), warnings
    assert any("未形成完工结果" in w for w in warnings), warnings

    print("OK")


if __name__ == "__main__":
    main()

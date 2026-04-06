import os
import sqlite3
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _base_input() -> Any:
    return SimpleNamespace(
        cfg=SimpleNamespace(),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        algo_ops_to_schedule=[SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal")],
        batches={"B001": SimpleNamespace(batch_id="B001")},
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        operations=[SimpleNamespace(id=1)],
        reschedulable_operations=[SimpleNamespace(id=1)],
        reschedulable_op_ids={1},
        normalized_batch_ids=["B001"],
        freeze_meta={"loaded": True},
        algo_input_outcome=SimpleNamespace(value=[], counters={}),
        downtime_meta={"load_ok": True},
        resource_pool_meta={"build_ok": True},
        algo_warnings=["freeze warning"],
        frozen_op_ids=set(),
        t0=0.0,
        optimizer_seed_version=6,
        run_label="排产",
        prev_version=5,
        created_by_text="tester",
        missing_internal_resource_op_ids=set(),
    )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.schedule_orchestrator import orchestrate_schedule_run
    from core.services.scheduler.schedule_service import ScheduleService
    from core.services.scheduler.schedule_summary_types import SummaryBuildContext

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    svc = ScheduleService(conn, logger=None, op_logger=None)

    # 场景 1：没有可落库行时，不应分配版本号
    captured_empty: Dict[str, Any] = {"allocate_calls": 0}

    def _unexpected_allocate_next_version():
        captured_empty["allocate_calls"] += 1
        raise AssertionError("无有效排程行时不应分配版本号")

    svc.history_repo.allocate_next_version = _unexpected_allocate_next_version  # type: ignore[assignment]

    def _stub_optimize_empty(**kwargs):
        captured_empty["optimize_strict_mode"] = kwargs.get("strict_mode")
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=0,
            failed_ops=1,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return SimpleNamespace(
            results=[],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            metrics=None,
            best_score=(0.0,),
            best_order=[],
            attempts=[],
            improvement_trace=[],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=1,
            algo_stats={},
        )

    rejected = False
    try:
        orchestrate_schedule_run(
            svc,
            schedule_input=_base_input(),
            simulate=False,
            strict_mode=True,
            optimize_schedule_fn=_stub_optimize_empty,
            has_actionable_schedule_rows_fn=lambda *_args, **_kwargs: False,
            build_result_summary_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("空结果不应构建摘要")),
        )
    except ValidationError as exc:
        rejected = getattr(exc, "details", {}).get("reason") == "no_actionable_schedule_rows"
    assert rejected, "无有效排程行场景应抛出 no_actionable_schedule_rows"
    assert captured_empty.get("allocate_calls") == 0, captured_empty
    assert captured_empty.get("optimize_strict_mode") is True, captured_empty

    # 场景 2：有可落库行时，先分配版本号，再构建摘要，并保留 warning 合并语义
    captured_ok: Dict[str, Any] = {"allocate_calls": 0}

    def _allocate_next_version():
        captured_ok["allocate_calls"] += 1
        return 7

    svc.history_repo.allocate_next_version = _allocate_next_version  # type: ignore[assignment]

    def _stub_optimize_ok(**kwargs):
        captured_ok["optimize_strict_mode"] = kwargs.get("strict_mode")
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=["optimizer warning"],
            errors=[],
            duration_seconds=0.0,
        )
        return SimpleNamespace(
            results=[SimpleNamespace(op_id=1)],
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={"dispatch": "fifo"},
            metrics={"makespan": 1},
            best_score=(0.0,),
            best_order=["B001"],
            attempts=[{"score": [0.0]}],
            improvement_trace=[{"score": [0.0]}],
            algo_mode="greedy",
            objective_name="min_overdue",
            time_budget_seconds=3,
            algo_stats={"fallback_counts": {"x": 1}},
        )

    def _stub_build_result_summary(_svc, **kwargs):
        captured_ok["summary_kwargs"] = dict(kwargs or {})
        return [{"batch_id": "B001"}], "success", {"algo": {"ok": 1}}, '{"algo":{"ok":1}}', 34

    collected = _base_input()
    outcome = orchestrate_schedule_run(
        svc,
        schedule_input=collected,
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=_stub_optimize_ok,
        has_actionable_schedule_rows_fn=lambda *_args, **_kwargs: True,
        build_result_summary_fn=_stub_build_result_summary,
    )
    conn.close()

    assert captured_ok.get("allocate_calls") == 1, captured_ok
    assert captured_ok.get("optimize_strict_mode") is True, captured_ok
    assert outcome.version == 7, outcome
    assert outcome.result_status == "success", outcome
    assert outcome.time_cost_ms == 34, outcome
    assert outcome.has_actionable_schedule is True, outcome
    assert outcome.algo_warnings == ["freeze warning"], outcome
    assert list(outcome.summary.warnings) == ["optimizer warning", "freeze warning"], outcome.summary.warnings

    summary_kwargs = captured_ok.get("summary_kwargs") or {}
    summary_ctx = summary_kwargs.get("ctx")
    assert isinstance(summary_ctx, SummaryBuildContext), summary_kwargs
    assert summary_ctx.version == 7, summary_ctx
    assert summary_ctx.simulate is True, summary_ctx
    assert summary_ctx.algo_warnings == ["freeze warning"], summary_ctx
    assert summary_ctx.warning_merge_status == {
        "summary_merge_attempted": True,
        "summary_merge_failed": False,
        "summary_merge_error": None,
    }, summary_ctx
    assert summary_ctx.input_build_outcome is collected.algo_input_outcome, summary_ctx

    print("OK")


if __name__ == "__main__":
    main()

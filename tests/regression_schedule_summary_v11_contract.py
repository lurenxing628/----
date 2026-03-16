import json
import os
import sys
import time
from datetime import datetime
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


def _build_summary(*, objective_name: str, warnings, improvement_trace):
    from core.algorithms.evaluation import ScheduleMetrics
    from core.services.scheduler.schedule_summary import build_result_summary

    cfg = SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="improve",
        time_budget_seconds=10,
        objective=objective_name,
        freeze_window_enabled="no",
        freeze_window_days=0,
    )
    summary = SimpleNamespace(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=list(warnings or []),
        errors=[],
    )
    metrics = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=10.0,
        makespan_hours=100.0,
        changeover_count=2,
        weighted_tardiness_hours=20.0,
    )
    return build_result_summary(
        _StubSvc(),
        cfg=cfg,
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=datetime(2026, 2, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name=objective_name,
        time_budget_seconds=10,
        best_score=(0.0, 20.0, 1.0, 10.0, 100.0, 2.0),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[{"tag": "start:priority_first|sgs:slack", "dispatch_mode": "sgs", "dispatch_rule": "slack", "score": [0.0]}],
        improvement_trace=list(improvement_trace or []),
        frozen_op_ids=set(),
        downtime_meta={},
        simulate=False,
        t0=time.time(),
    )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    _overdue, _status, result_summary_obj, result_summary_json, _ms = _build_summary(
        objective_name="min_weighted_tardiness",
        warnings=[],
        improvement_trace=[],
    )
    assert result_summary_obj.get("summary_schema_version") == "1.1", "summary_schema_version 未升到 1.1"

    algo = result_summary_obj.get("algo") or {}
    assert algo.get("comparison_metric") == "weighted_tardiness_hours", f"comparison_metric 错误：{algo.get('comparison_metric')!r}"
    schema_keys = [it.get("key") for it in (algo.get("best_score_schema") or []) if isinstance(it, dict)]
    assert schema_keys[:3] == [
        "failed_ops",
        "weighted_tardiness_hours",
        "overdue_count",
    ], f"best_score_schema 错误：{schema_keys}"
    config_snapshot = algo.get("config_snapshot") or {}
    assert config_snapshot.get("objective") == "min_weighted_tardiness", f"config_snapshot 未落盘 objective：{config_snapshot}"

    ctx = build_analysis_context(
        selected_ver=1,
        raw_hist=[{"version": 1, "result_summary": result_summary_json}],
        selected_item={"version": 1, "result_summary": result_summary_json},
    )
    assert ctx.get("objective_key") == "weighted_tardiness_hours", f"analysis_context 未使用 comparison_metric：{ctx.get('objective_key')!r}"

    old_summary_json = json.dumps(
        {
            "version": 1,
            "algo": {
                "objective": "min_tardiness",
                "metrics": {
                    "total_tardiness_hours": 12.0,
                    "overdue_count": 1,
                },
            },
        },
        ensure_ascii=False,
    )
    old_ctx = build_analysis_context(
        selected_ver=1,
        raw_hist=[{"version": 1, "result_summary": old_summary_json}],
        selected_item={"version": 1, "result_summary": old_summary_json},
    )
    assert old_ctx.get("objective_key") == "total_tardiness_hours", f"旧 summary 兼容回退异常：{old_ctx.get('objective_key')!r}"

    huge_warnings = [f"W{i}:" + ("x" * 6000) for i in range(120)]
    huge_trace = [{"tag": "T" + ("y" * 4000), "elapsed_ms": i, "metrics": {"weighted_tardiness_hours": float(i)}} for i in range(200)]
    _overdue2, _status2, big_obj, big_json, _ms2 = _build_summary(
        objective_name="min_weighted_tardiness",
        warnings=huge_warnings,
        improvement_trace=huge_trace,
    )
    assert bool(big_obj.get("summary_truncated")), "超大 summary 未标记 summary_truncated"
    assert int(big_obj.get("original_size_bytes") or 0) > len(big_json.encode("utf-8")), "original_size_bytes 未记录原始大小"
    assert len(big_json.encode("utf-8")) <= 512 * 1024, "summary 截断后仍超过 512KB"

    print("OK")


if __name__ == "__main__":
    main()

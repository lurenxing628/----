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
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        return str(value)


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.schedule_summary import build_result_summary

    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _StubSvc(),
        cfg={"auto_assign_enabled": "no", "freeze_window_enabled": "no", "freeze_window_days": 0},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        downtime_meta={},
        resource_pool_meta={},
        algo_stats={
            "fallback_counts": {
                "seed_duplicate_dropped_count": 2,
                "dispatch_key_proc_hours_fallback_count": 0,
            },
            "param_fallbacks": {
                "dispatch_rule_defaulted_count": 1,
            },
        },
        algo_warnings=[],
        warning_merge_status={},
        simulate=False,
        t0=time.time(),
    )

    algo = result_summary_obj.get("algo") or {}
    fallback_counts = algo.get("fallback_counts") or {}
    param_fallbacks = algo.get("param_fallbacks") or {}

    assert int(fallback_counts.get("seed_duplicate_dropped_count") or 0) == 2, f"fallback_counts 输出异常：{algo!r}"
    assert "dispatch_key_proc_hours_fallback_count" not in fallback_counts, f"0 值计数不应输出：{fallback_counts!r}"
    assert int(param_fallbacks.get("dispatch_rule_defaulted_count") or 0) == 1, f"param_fallbacks 输出异常：{algo!r}"

    print("OK")


if __name__ == "__main__":
    main()

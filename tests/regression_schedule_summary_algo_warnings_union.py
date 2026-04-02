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

    _overdue, result_status, result_summary_obj, _json_text, _ms = build_result_summary(
        _StubSvc(),
        cfg={"auto_assign_enabled": "yes", "freeze_window_enabled": "yes", "freeze_window_days": 3},
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
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={
            "resource_pool_attempted": True,
            "resource_pool_build_ok": False,
            "resource_pool_build_error": "pool boom",
        },
        algo_warnings=[
            "【冻结窗口】读取冻结计划失败，已跳过冻结约束",
            "自动分配资源池构建失败，已降级为不自动分配（请查看日志）。",
        ],
        warning_merge_status={
            "summary_merge_attempted": True,
            "summary_merge_failed": True,
            "summary_merge_error": "summary.warnings broken",
        },
        simulate=False,
        t0=time.time(),
    )

    assert result_status == "success", f"result_status 异常：{result_status!r}"
    warnings = list(result_summary_obj.get("warnings") or [])
    assert any("读取冻结计划失败" in item for item in warnings), f"algo_warnings 未透传到 summary.warnings：{warnings!r}"
    assert any("自动分配资源池构建失败" in item for item in warnings), f"resource_pool warning 未透传：{warnings!r}"

    algo = result_summary_obj.get("algo") or {}
    freeze_window = algo.get("freeze_window") or {}
    resource_pool = algo.get("resource_pool") or {}
    warning_pipeline = algo.get("warning_pipeline") or {}

    assert bool(freeze_window.get("degraded")), f"freeze_window 降级标记缺失：{freeze_window!r}"
    assert "读取冻结计划失败" in str(freeze_window.get("degradation_reason") or ""), (
        f"freeze_window 降级原因未从 algo_warnings union 提取：{freeze_window!r}"
    )
    assert bool(resource_pool.get("degraded")), f"resource_pool 降级标记缺失：{resource_pool!r}"
    assert "pool boom" in str(resource_pool.get("degradation_reason") or ""), f"resource_pool 降级原因异常：{resource_pool!r}"
    assert bool(warning_pipeline.get("summary_merge_failed")), f"warning_pipeline 未标记 merge 失败：{warning_pipeline!r}"
    assert int(warning_pipeline.get("algo_warning_count") or 0) == 2, f"algo_warning_count 异常：{warning_pipeline!r}"

    print("OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from types import SimpleNamespace


class _Calendar:
    @staticmethod
    def add_calendar_days(start: datetime, days: float) -> datetime:
        return start + timedelta(days=float(days))


class _Scheduler:
    def __init__(self) -> None:
        self.calendar = _Calendar()
        self._last_algo_stats = {}


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

    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.greedy.external_groups import schedule_external
    from core.services.scheduler.schedule_summary import build_result_summary

    scheduler = _Scheduler()
    base_time = datetime(2026, 4, 2, 8, 0, 0)
    batch = SimpleNamespace(batch_id="B_EXT", due_date="2099-12-31", priority="normal", quantity=1)
    op = SimpleNamespace(id=11, op_code="EXT-001", batch_id="B_EXT", seq=10, ext_days=None, op_type_name="热处理")

    errors = []
    result, blocked = schedule_external(
        scheduler,
        op=op,
        batch=batch,
        batch_progress={},
        external_group_cache={},
        base_time=base_time,
        errors=errors,
        end_dt_exclusive=None,
        strict_mode=False,
    )
    assert blocked is False, f"兼容模式不应阻断，实际 blocked={blocked!r}"
    assert not errors, f"兼容模式不应产生日志错误，实际 {errors!r}"
    assert result is not None, "兼容模式应返回排产结果"
    assert result.start_time == base_time, result
    assert result.end_time == base_time + timedelta(days=1), result

    fallback_counts = dict((scheduler._last_algo_stats or {}).get("fallback_counts") or {})
    assert int(fallback_counts.get("legacy_external_days_defaulted_count") or 0) == 1, fallback_counts

    try:
        schedule_external(
            _Scheduler(),
            op=op,
            batch=batch,
            batch_progress={},
            external_group_cache={},
            base_time=base_time,
            errors=[],
            end_dt_exclusive=None,
            strict_mode=True,
        )
    except Exception:
        pass
    else:
        raise AssertionError("严格模式下 ext_days=None 应抛错，不能静默回退到 1.0 天")

    metrics = compute_metrics([result], {"B_EXT": batch})
    summary = SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[])
    _overdue_items, result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(
        _SummarySvc(),
        cfg={"freeze_window_enabled": "no", "auto_assign_enabled": "no"},
        version=8,
        normalized_batch_ids=["B_EXT"],
        start_dt=base_time,
        end_date=None,
        batches={"B_EXT": batch},
        operations=[],
        results=[result],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0, 0.0, 24.0, 0.0, 0.0),
        best_metrics=metrics,
        best_order=["B_EXT"],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        algo_stats=scheduler._last_algo_stats,
        simulate=False,
        t0=time.time() - 0.02,
    )

    assert result_status == "success", result_status
    assert int(result_summary_obj.get("legacy_external_days_defaulted_count") or 0) == 1, result_summary_obj

    degradation_counters = dict(result_summary_obj.get("degradation_counters") or {})
    assert int(degradation_counters.get("legacy_external_days_defaulted") or 0) == 1, degradation_counters

    warnings = list(result_summary_obj.get("warnings") or [])
    assert any("历史兼容周期 1.0 天" in w for w in warnings), warnings

    print("OK")


if __name__ == "__main__":
    main()

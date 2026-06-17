"""回归测试：build_result_summary 输出 algo.fallback_counts / param_fallbacks 时，只保留正整数计数，丢弃 0 值，并拒绝把坏值/布尔/Decimal/Fraction/NaN/Inf/负数伪装成计数；遇到坏值时打 fallback_count_parse_failed 标记、保留错误样例、并向 warnings 和 degradation_events 暴露降级。"""

import time
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace


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


def test_schedule_summary_fallback_counts_output() -> None:

    from core.services.scheduler.summary.schedule_summary import build_result_summary

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
                "bad_fallback_count": "bad",
                "bool_fallback_count": True,
                "decimal_fallback_count": Decimal("1.5"),
                "fraction_fallback_count": Fraction(3, 2),
                "nan_fallback_count": float("nan"),
                "inf_fallback_count": float("inf"),
                "negative_fallback_count": -1,
            },
            "param_fallbacks": {
                "dispatch_rule_defaulted_count": 1,
                "fractional_param_fallback": "1.5",
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
    assert "bad_fallback_count" not in fallback_counts, f"坏值不应伪装成正常 fallback count：{fallback_counts!r}"
    assert "bool_fallback_count" not in fallback_counts, f"布尔值不应伪装成正常 fallback count：{fallback_counts!r}"
    assert "decimal_fallback_count" not in fallback_counts, f"Decimal 小数不应伪装成正常 fallback count：{fallback_counts!r}"
    assert "fraction_fallback_count" not in fallback_counts, f"Fraction 小数不应伪装成正常 fallback count：{fallback_counts!r}"
    assert "nan_fallback_count" not in fallback_counts, f"NaN 不应伪装成正常 fallback count：{fallback_counts!r}"
    assert "inf_fallback_count" not in fallback_counts, f"Inf 不应伪装成正常 fallback count：{fallback_counts!r}"
    assert "negative_fallback_count" not in fallback_counts, f"负数不应伪装成正常 fallback count：{fallback_counts!r}"
    assert int(param_fallbacks.get("dispatch_rule_defaulted_count") or 0) == 1, f"param_fallbacks 输出异常：{algo!r}"
    assert "fractional_param_fallback" not in param_fallbacks, f"小数不应伪装成正常 param fallback：{param_fallbacks!r}"
    assert bool(algo.get("fallback_count_parse_failed")), f"坏 fallback count 应有 parse_failed 标记：{algo!r}"
    assert len(list(algo.get("fallback_count_parse_errors") or [])) >= 8, f"坏 fallback count 应保留错误样例：{algo!r}"
    assert any("降级统计记录异常" in str(item) for item in list(result_summary_obj.get("warnings") or [])), (
        f"坏 fallback count 应进入 warnings：{result_summary_obj!r}"
    )
    assert any(
        str(event.get("code") or "") == "fallback_count_parse_failed"
        for event in list(result_summary_obj.get("degradation_events") or [])
    ), f"坏 fallback count 应进入 degradation_events：{result_summary_obj!r}"

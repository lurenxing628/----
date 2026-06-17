"""回归测试：当排产结果只含外协工序（无内部机时）时，compute_metrics 的 makespan_internal_hours 与 internal_horizon_hours 应为 0、util_defined 为 False，且 to_dict() 投影保持同样语义（不把无内部产能误判为已定义利用率）。"""

from datetime import datetime, timedelta


def test_metrics_horizon_semantics() -> None:

    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.types import ScheduleResult

    # 仅外协结果：internal horizon=0 -> util_defined=False（util_avg 仍为 0.0 占位）
    st = datetime(2026, 1, 1, 8, 0, 0)
    et = st + timedelta(days=1)
    results = [
        ScheduleResult(
            op_id=1,
            op_code="E1",
            batch_id="B001",
            seq=1,
            machine_id=None,
            operator_id=None,
            start_time=st,
            end_time=et,
            source="external",
            op_type_name=None,
        )
    ]
    metrics = compute_metrics(results, batches={})
    assert metrics.makespan_internal_hours == 0.0, f"internal makespan 应为 0：{metrics.makespan_internal_hours!r}"
    assert metrics.internal_horizon_hours == 0.0, f"internal_horizon_hours 应为 0：{metrics.internal_horizon_hours!r}"
    assert metrics.util_defined is False, f"util_defined 应为 False：{metrics.util_defined!r}"

    d = metrics.to_dict()
    assert d.get("util_defined") is False, f"to_dict util_defined 异常：{d!r}"
    assert float(d.get("internal_horizon_hours") or 0.0) == 0.0, f"to_dict internal_horizon_hours 异常：{d!r}"

"""回归测试：ScheduleMetrics.to_dict 与 evaluation 负荷统计（_finite_non_negative/_cv）遇到 NaN/Infinity、无法转 float 的坏值或内部计算错误时必须抛错（提示“有限数字”），不得静默归零。"""


def test_metrics_to_dict_nonfinite_safe() -> None:

    from core.algorithms import evaluation
    from core.algorithms.evaluation import ScheduleMetrics

    m = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=float("nan"),
        makespan_hours=float("inf"),
        changeover_count=0,
        weighted_tardiness_hours=float("nan"),
        makespan_internal_hours=float("inf"),
        machine_busy_hours_total=float("inf"),
        operator_busy_hours_total=float("nan"),
        machine_util_avg=float("inf"),
        operator_util_avg=float("nan"),
        machine_load_cv=float("inf"),
        operator_load_cv=float("nan"),
        internal_horizon_hours=float("inf"),
        util_defined=True,
    )
    try:
        m.to_dict()
    except ValueError as exc:
        assert "有限数字" in str(exc), exc
    else:
        raise AssertionError("NaN/Infinity 指标不能静默变成 0")

    class BadFloat:
        def __float__(self):
            raise RuntimeError("bad float should not become zero")

    bad = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=BadFloat(),
        makespan_hours=1.0,
        changeover_count=0,
    )
    try:
        bad.to_dict()
    except RuntimeError:
        pass
    else:
        raise AssertionError("内部坏指标不能静默变成 0")

    try:
        evaluation._finite_non_negative({"ok": 1.0, "bad": "坏数据"})
    except ValueError:
        pass
    else:
        raise AssertionError("负荷统计坏值不能被跳过后继续算")

    real_pstdev = evaluation.statistics.pstdev

    def fail_pstdev(_values):
        raise RuntimeError("pstdev failed")

    evaluation.statistics.pstdev = fail_pstdev
    try:
        try:
            evaluation._cv([1.0, 2.0])
        except RuntimeError:
            pass
        else:
            raise AssertionError("负荷波动内部计算错误不能静默变 0")
    finally:
        evaluation.statistics.pstdev = real_pstdev



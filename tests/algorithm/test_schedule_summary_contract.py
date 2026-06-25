"""回归测试：ScheduleSummary 状态和计数只接收严格类型，不能把 bool/字符串/小数混成合法值。"""

from __future__ import annotations

import pytest

from core.algorithms.types import ScheduleSummary


def _summary(**overrides):
    data = {
        "success": True,
        "total_ops": 1,
        "scheduled_ops": 1,
        "failed_ops": 0,
        "warnings": [],
        "errors": [],
        "duration_seconds": 0.0,
    }
    data.update(overrides)
    return ScheduleSummary(**data)


def test_schedule_summary_counts_must_be_non_negative_ints() -> None:
    assert _summary().total_ops == 1

    bad_values = ("1", 1.0, True, -1)
    for field in ("total_ops", "scheduled_ops", "failed_ops"):
        for value in bad_values:
            with pytest.raises((TypeError, ValueError)):
                _summary(**{field: value})


def test_schedule_summary_success_must_be_bool() -> None:
    assert _summary(success=True).success is True
    assert _summary(success=False).success is False

    for value in ("false", "true", 0, 1, None):
        with pytest.raises(TypeError):
            _summary(success=value)

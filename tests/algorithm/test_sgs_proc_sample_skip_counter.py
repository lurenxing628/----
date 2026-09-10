"""守护 SGS 均值预扫留痕契约：非 strict 模式下工时非法的 internal 工序被跳出均值样本时，必须以
dispatch_key_avg_proc_hours_sample_skipped_count 计数留痕（部分跳样本致均值偏移不许查无此事）；
全部样本为空时原有 dispatch_key_avg_proc_hours_fallback_count 兜底计数保持不变。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

import pytest

import core.algorithms.greedy.dispatch.sgs as sgs_module


class _CountingCtx:
    def __init__(self) -> None:
        self.counters: Dict[str, int] = {}

    def increment(self, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
        assert bucket == "fallback_counts"
        self.counters[key] = self.counters.get(key, 0) + int(amount)


def _batch(batch_id: str) -> Any:
    return SimpleNamespace(batch_id=batch_id, quantity=1)


def _internal_op(op_id: int, batch_id: str, setup_hours: Any) -> Any:
    return SimpleNamespace(
        id=op_id,
        batch_id=batch_id,
        seq=1,
        source="internal",
        setup_hours=setup_hours,
        unit_hours=0.0,
    )


def test_partially_skipped_samples_leave_counter_trace() -> None:
    ctx = _CountingCtx()
    avg, total_by_op = sgs_module._average_proc_hours(
        ctx,
        ops_by_batch={"B1": [_internal_op(1, "B1", 4.0), _internal_op(2, "B1", "abc"), _internal_op(3, "B1", 8.0)]},
        batches={"B1": _batch("B1")},
        strict_mode=False,
    )

    assert avg == pytest.approx(6.0), "均值只按合法样本计算"
    assert total_by_op == {1: 4.0, 3: 8.0}
    assert ctx.counters.get("dispatch_key_avg_proc_hours_sample_skipped_count") == 1, "跳样本必须计数留痕"
    assert "dispatch_key_avg_proc_hours_fallback_count" not in ctx.counters, "有样本时不该触发全空兜底计数"


def test_all_samples_skipped_records_both_counters() -> None:
    ctx = _CountingCtx()
    avg, total_by_op = sgs_module._average_proc_hours(
        ctx,
        ops_by_batch={"B1": [_internal_op(1, "B1", "abc"), _internal_op(2, "B1", "xyz")]},
        batches={"B1": _batch("B1")},
        strict_mode=False,
    )

    assert avg == 1.0, "全空样本时保持既有 1.0 兜底"
    assert total_by_op == {}
    assert ctx.counters.get("dispatch_key_avg_proc_hours_sample_skipped_count") == 2
    assert ctx.counters.get("dispatch_key_avg_proc_hours_fallback_count") == 1


def test_valid_samples_produce_no_skip_counter() -> None:
    ctx = _CountingCtx()
    avg, _ = sgs_module._average_proc_hours(
        ctx,
        ops_by_batch={"B1": [_internal_op(1, "B1", 2.0)]},
        batches={"B1": _batch("B1")},
        strict_mode=False,
    )

    assert avg == pytest.approx(2.0)
    assert ctx.counters == {}, "全部样本合法时不该有任何降级计数"

"""回归测试：种子结果的「类型边界」职责划分——run 层 coerce_seed_results 是原始 dict 入口，负责把合法种子转成强类型 ScheduleResult，并对非法种子/字符串时间/会被截断的非正整数 op_id 与 seq 直接抛 ValidationError(field=seed_results) 并累计 invalid 计数；算法层 normalize_seed_results 不是原始边界，不回填负身份、不忽略坏 seq，遇不匹配则丢弃并产出警告。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.algorithms.greedy.seed import normalize_seed_results
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results


def test_run_layer_coerces_raw_seed_dict_to_typed_schedule_result() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}}

    results = coerce_seed_results(
        [
            {
                "op_id": 7,
                "op_code": "B001_10",
                "batch_id": "B001",
                "seq": 10,
                "machine_id": "MC001",
                "operator_id": "OP001",
                "start_time": start,
                "end_time": end,
            }
        ],
        optimizer_algo_stats=stats,
    )

    assert len(results) == 1
    assert results[0].op_id == 7
    assert results[0].start_time == start
    assert int((stats.get("fallback_counts") or {}).get("optimizer_seed_result_invalid_count") or 0) == 0


def test_run_layer_rejects_invalid_raw_seed_before_algorithm_cleanup() -> None:
    stats = {"fallback_counts": {}, "param_fallbacks": {}}

    with pytest.raises(ValidationError) as exc_info:
        coerce_seed_results(
            [{"op_id": 7, "start_time": None, "end_time": None}, "bad-seed"],
            optimizer_algo_stats=stats,
        )

    details = getattr(exc_info.value, "details", {}) or {}
    assert exc_info.value.field == "seed_results"
    assert details.get("reason") == "invalid_seed_results"
    assert int(details.get("invalid_seed_count") or 0) == 2
    assert int((stats.get("fallback_counts") or {}).get("optimizer_seed_result_invalid_count") or 0) == 2


def test_run_layer_rejects_string_seed_times_before_algorithm_cleanup() -> None:
    stats = {"fallback_counts": {}, "param_fallbacks": {}}

    with pytest.raises(ValidationError) as exc_info:
        coerce_seed_results(
            [
                {
                    "op_id": 7,
                    "op_code": "B001_10",
                    "batch_id": "B001",
                    "seq": 10,
                    "start_time": "2026-04-01 08:00:00",
                    "end_time": "2026-04-01 10:00:00",
                }
            ],
            optimizer_algo_stats=stats,
        )

    details = getattr(exc_info.value, "details", {}) or {}
    assert exc_info.value.field == "seed_results"
    assert details.get("reason") == "invalid_seed_results"
    assert int(details.get("invalid_seed_count") or 0) == 1
    assert "有效时间" in str((details.get("invalid_seed_samples") or [{}])[0].get("error") or "")


@pytest.mark.parametrize(
    "payload, expected_text",
    [
        ({"op_id": 7.5, "seq": 10}, "工序编号必须是正整数"),
        ({"op_id": True, "seq": 10}, "工序编号必须是正整数"),
        ({"op_id": -7, "seq": 10}, "工序编号必须是正整数"),
        ({"op_id": "-7", "seq": 10}, "工序编号必须是正整数"),
        ({"op_id": 0, "seq": 1.5}, "工序号必须是正整数"),
        ({"op_id": 0, "seq": -1}, "工序号必须是正整数"),
    ],
)
def test_run_layer_rejects_seed_identity_values_that_would_be_truncated(payload, expected_text) -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}}
    item = {
        "op_code": "B001_10",
        "batch_id": "B001",
        "start_time": start,
        "end_time": end,
    }
    item.update(payload)

    with pytest.raises(ValidationError) as exc_info:
        coerce_seed_results([item], optimizer_algo_stats=stats)

    details = getattr(exc_info.value, "details", {}) or {}
    assert exc_info.value.field == "seed_results"
    assert details.get("reason") == "invalid_seed_results"
    assert expected_text in str((details.get("invalid_seed_samples") or [{}])[0].get("error") or "")


def test_algorithm_seed_normalizer_is_not_the_raw_dict_boundary() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)

    normalized, seed_op_ids, warnings = normalize_seed_results(
        seed_results=[
            {
                "op_id": 7,
                "op_code": "B001_10",
                "batch_id": "B001",
                "seq": 10,
                "start_time": start,
                "end_time": end,
            }
        ],
        operations=[SimpleNamespace(id=7, op_code="B001_10", batch_id="B001", seq=10)],
        algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
    )

    assert normalized == []
    assert seed_op_ids == set()
    assert warnings == []


def test_algorithm_seed_normalizer_does_not_filter_operation_for_string_time_seed() -> None:
    normalized, seed_op_ids, warnings = normalize_seed_results(
        seed_results=[
            SimpleNamespace(
                op_id=7,
                op_code="B001_10",
                batch_id="B001",
                seq=10,
                start_time="2026-04-01 08:00:00",
                end_time="2026-04-01 10:00:00",
            )
        ],
        operations=[SimpleNamespace(id=7, op_code="B001_10", batch_id="B001", seq=10)],
        algo_stats={"fallback_counts": {}, "param_fallbacks": {}},
    )

    assert normalized == []
    assert seed_op_ids == set()
    assert any("格式不正确" in warning for warning in warnings)


def test_algorithm_seed_normalizer_does_not_backfill_negative_identity() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}}

    normalized, seed_op_ids, warnings = normalize_seed_results(
        seed_results=[
            SimpleNamespace(
                op_id=-7,
                op_code="B001_10",
                batch_id="B001",
                seq=10,
                start_time=start,
                end_time=end,
            ),
            SimpleNamespace(
                op_id=0,
                op_code="",
                batch_id="B001",
                seq="-10",
                start_time=start,
                end_time=end,
            ),
        ],
        operations=[SimpleNamespace(id=7, op_code="B001_10", batch_id="B001", seq=10)],
        algo_stats=stats,
    )

    assert normalized == []
    assert seed_op_ids == set()
    assert int((stats.get("fallback_counts") or {}).get("seed_invalid_dropped_count") or 0) == 2
    assert any("无法匹配" in warning for warning in warnings)


@pytest.mark.parametrize("seq", [-1, "-1", 1.5, "1.5", True])
def test_algorithm_seed_normalizer_does_not_ignore_bad_seq_when_op_code_matches(seq) -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}}

    normalized, seed_op_ids, warnings = normalize_seed_results(
        seed_results=[
            SimpleNamespace(
                op_id=0,
                op_code="B001_10",
                batch_id="B001",
                seq=seq,
                start_time=start,
                end_time=end,
            )
        ],
        operations=[SimpleNamespace(id=7, op_code="B001_10", batch_id="B001", seq=10)],
        algo_stats=stats,
    )

    assert normalized == []
    assert seed_op_ids == set()
    assert int((stats.get("fallback_counts") or {}).get("seed_invalid_dropped_count") or 0) == 1
    assert any("无法匹配" in warning for warning in warnings)

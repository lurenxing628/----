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

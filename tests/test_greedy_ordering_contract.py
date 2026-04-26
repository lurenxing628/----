from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from core.algorithms.ordering import (
    build_batch_sort_inputs,
    build_normalized_batches_map,
    normalize_batch_order_override,
    normalize_text_id,
    operation_sort_key,
)
from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError


def test_normalized_batches_keep_first_duplicate_and_warn() -> None:
    first = SimpleNamespace(batch_id="B1")
    second = SimpleNamespace(batch_id="B1")
    warnings: list[str] = []

    normalized = build_normalized_batches_map({" B1 ": first, "B1": second}, warnings=warnings)

    assert normalized == {"B1": first}
    assert warnings and "批次ID规范化冲突" in warnings[0]


def test_override_keeps_first_valid_batch_id_only() -> None:
    batches = {"B1": object(), "B2": object(), "B3": object()}

    assert normalize_batch_order_override(["B2", "B1", "B2", "", "MISSING", "B3"], batches) == ["B2", "B1", "B3"]


def test_strict_ready_date_error_is_not_hidden_by_full_override() -> None:
    batches = {
        "B1": SimpleNamespace(
            batch_id="B1",
            priority="normal",
            due_date=date(2026, 1, 2),
            ready_status="yes",
            ready_date="bad-ready-date",
            created_at=None,
        )
    }

    with pytest.raises(ValidationError) as exc_info:
        build_batch_sort_inputs(batches, strict_mode=True, strategy=SortStrategy.PRIORITY_FIRST)

    assert exc_info.value.field == "ready_date"


def test_bad_str_conversion_is_normalized_to_empty_text_id() -> None:
    class BadStr:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    assert normalize_text_id(BadStr()) == ""


def test_operation_sort_key_uses_shared_integer_contract() -> None:
    op = SimpleNamespace(batch_id="B1", seq="bad-seq", id=1)

    with pytest.raises(ValidationError) as exc_info:
        operation_sort_key(op, {"B1": 0})

    assert exc_info.value.field == "seq"

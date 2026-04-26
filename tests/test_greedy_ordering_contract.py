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


def test_normalized_batches_reject_duplicate_batch_id() -> None:
    first = SimpleNamespace(batch_id="B1")
    second = SimpleNamespace(batch_id="B1")

    with pytest.raises(ValidationError) as exc_info:
        build_normalized_batches_map({" B1 ": first, "B1": second})

    assert exc_info.value.field == "batch_id"


def test_normalized_batches_reject_empty_batch_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_normalized_batches_map({"": SimpleNamespace(batch_id="")})

    assert exc_info.value.field == "batch_id"


def test_override_keeps_valid_batch_ids_in_order() -> None:
    batches = {"B1": object(), "B2": object(), "B3": object()}

    assert normalize_batch_order_override(["B2", "B1", "B3"], batches) == ["B2", "B1", "B3"]


@pytest.mark.parametrize("override", [["B1", "B1"], ["MISSING"], [""]])
def test_override_rejects_invalid_batch_order_items(override: list[str]) -> None:
    batches = {"B1": object(), "B2": object()}

    with pytest.raises(ValidationError) as exc_info:
        normalize_batch_order_override(override, batches)

    assert exc_info.value.field == "batch_order_override"


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


def test_bad_str_conversion_is_rejected() -> None:
    class BadStr:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    with pytest.raises(ValidationError) as exc_info:
        normalize_text_id(BadStr())

    assert exc_info.value.field == "id"


def test_operation_sort_key_uses_shared_integer_contract() -> None:
    op = SimpleNamespace(batch_id="B1", seq="bad-seq", id=1)

    with pytest.raises(ValidationError) as exc_info:
        operation_sort_key(op, {"B1": 0})

    assert exc_info.value.field == "seq"

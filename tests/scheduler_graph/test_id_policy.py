from __future__ import annotations

import pytest

from core.services.scheduler.graph.id_policy import (
    display_id,
    make_machine_node_id,
    make_operation_node_id,
    make_operator_node_id,
    normalize_operation_row_id,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1, "1"),
        ("1", "1"),
        ("001", "1"),
        ("1.0", "1"),
        (1.0, "1"),
    ],
)
def test_normalize_operation_row_id_accepts_positive_integer_like_values(raw, expected) -> None:
    assert normalize_operation_row_id(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", 0, "0", 0.0, "0.0", False, True, -1, "-1", 1.5, "1.5", "abc"],
)
def test_normalize_operation_row_id_rejects_invalid_values(raw) -> None:
    assert normalize_operation_row_id(raw) is None


def test_make_operation_node_id_prefers_valid_row_id() -> None:
    assert make_operation_node_id("B001", "B001_10", 123) == "op:123"
    assert make_operation_node_id("B001", "B001_10", "00123") == "op:123"


@pytest.mark.parametrize("invalid_row_id", [None, "", 0, "0", False, True, "abc"])
def test_make_operation_node_id_falls_back_when_row_id_is_invalid(invalid_row_id) -> None:
    assert make_operation_node_id("B001", "B001_10", invalid_row_id) == "op:B001:B001_10"


def test_make_operation_node_id_trims_fallback_parts() -> None:
    assert make_operation_node_id(" B001 ", " B001_10 ") == "op:B001:B001_10"


def test_make_resource_node_ids_trim_text() -> None:
    assert make_machine_node_id(" CNC-01 ") == "machine:CNC-01"
    assert make_operator_node_id(" OP-01 ") == "operator:OP-01"


@pytest.mark.parametrize(
    ("node_id", "expected"),
    [
        ("op:123", "123"),
        ("machine:CNC-01", "CNC-01"),
        ("operator:OP-01", "OP-01"),
        ("unknown:X", "unknown:X"),
        (None, ""),
    ],
)
def test_display_id_strips_known_prefixes(node_id, expected) -> None:
    assert display_id(node_id) == expected

from __future__ import annotations

import pytest

from core.services.scheduler.graph.id_policy import (
    GraphNodeIdError,
    display_id,
    make_machine_node_id,
    make_operation_node_id,
    make_operator_node_id,
    normalize_operation_row_id,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (1, 1),
        ("1", 1),
        ("001", 1),
        ("1.0", 1),
        (1.0, 1),
        ("00123.000", 123),
    ],
)
def test_normalize_operation_row_id_accepts_positive_integer_shapes(raw, expected) -> None:
    assert normalize_operation_row_id(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", 0, False, True, -1, "abc", "1.5", "1E+3", b"123"])
def test_normalize_operation_row_id_rejects_unsafe_or_non_integer_values(raw) -> None:
    assert normalize_operation_row_id(raw) is None


def test_make_operation_node_id_with_row_id() -> None:
    assert make_operation_node_id("B001", "B001_10", 123) == "op:123"


@pytest.mark.parametrize("raw", ["1", "001", "1.0", 1.0])
def test_make_operation_node_id_normalizes_compatible_row_id(raw) -> None:
    assert make_operation_node_id("B001", "B001_10", raw) == "op:1"


@pytest.mark.parametrize("raw", [None, 0, False, True, "abc"])
def test_make_operation_node_id_falls_back_for_invalid_nonblank_row_id(raw) -> None:
    assert make_operation_node_id("B001", "B001_10", raw) == "op:B001:B001_10"


@pytest.mark.parametrize(
    "batch_id, op_code",
    [
        (None, "OP10"),
        ("", "OP10"),
        ("   ", "OP10"),
        ("B001", None),
        ("B001", ""),
        ("B001", "   "),
    ],
)
def test_make_operation_node_id_rejects_blank_fallback_parts(batch_id, op_code) -> None:
    with pytest.raises(GraphNodeIdError):
        make_operation_node_id(batch_id, op_code)


def test_make_operation_node_id_rejects_binary_row_id() -> None:
    with pytest.raises(GraphNodeIdError):
        make_operation_node_id("B001", "OP10", b"123")


@pytest.mark.parametrize("value", [b"B001", bytearray(b"B001")])
def test_make_operation_node_id_rejects_binary_fallback_parts(value) -> None:
    with pytest.raises(GraphNodeIdError):
        make_operation_node_id(value, "OP10")
    with pytest.raises(GraphNodeIdError):
        make_operation_node_id("B001", value)


def test_make_machine_node_id() -> None:
    assert make_machine_node_id("CNC-01") == "machine:CNC-01"


def test_make_operator_node_id() -> None:
    assert make_operator_node_id("OP-01") == "operator:OP-01"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_make_machine_node_id_rejects_blank_values(raw) -> None:
    with pytest.raises(GraphNodeIdError):
        make_machine_node_id(raw)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_make_operator_node_id_rejects_blank_values(raw) -> None:
    with pytest.raises(GraphNodeIdError):
        make_operator_node_id(raw)


@pytest.mark.parametrize("raw", [b"CNC-01", bytearray(b"CNC-01")])
def test_resource_node_ids_reject_binary_values(raw) -> None:
    with pytest.raises(GraphNodeIdError):
        make_machine_node_id(raw)
    with pytest.raises(GraphNodeIdError):
        make_operator_node_id(raw)


def test_display_id_is_tolerant_for_diagnostics() -> None:
    assert display_id("op:123") == "123"
    assert display_id("machine:CNC-01") == "CNC-01"
    assert display_id("operator:OP-01") == "OP-01"
    assert display_id(None) == ""

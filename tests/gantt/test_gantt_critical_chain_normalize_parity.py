"""Regression tests for critical-chain result normalization parity."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.services.scheduler.gantt_critical_chain import _normalize_critical_chain_result


def _default_edge_type_stats() -> Dict[str, int]:
    return {"process": 0, "machine": 0, "operator": 0, "unknown": 0}


def _expected(
    *,
    ids: Optional[List[str]] = None,
    edges: Optional[List[Dict[str, Any]]] = None,
    makespan_end: Optional[str] = None,
    edge_type_stats: Optional[Dict[str, int]] = None,
    edge_count: int = 0,
    available: bool = True,
    reason: str = "",
    reason_code: str = "",
) -> Dict[str, Any]:
    return {
        "ids": list(ids or []),
        "edges": list(edges or []),
        "makespan_end": makespan_end,
        "edge_type_stats": dict(edge_type_stats or _default_edge_type_stats()),
        "edge_count": edge_count,
        "available": available,
        "reason": reason,
        "reason_code": reason_code,
    }


_CASES: List[Tuple[str, Any, Dict[str, Any]]] = [
    ("empty dict", {}, _expected()),
    ("none raw", None, _expected()),
    ("integer raw", 123, _expected()),
    ("string raw", "not-a-result", _expected()),
    (
        "integer available stays truthy default",
        {"available": 0, "reason": "rows_exception", "reason_code": "custom_code"},
        _expected(),
    ),
    (
        "string available stays truthy default",
        {"available": "yes", "reason": "rows_exception", "reason_code": "custom_code"},
        _expected(),
    ),
    (
        "unavailable without reason code uses unknown",
        {"available": False},
        _expected(available=False, reason_code="unknown"),
    ),
    (
        "unavailable reason becomes reason code fallback",
        {"available": False, "reason": " rows_exception "},
        _expected(available=False, reason="rows_exception", reason_code="rows_exception"),
    ),
    (
        "unavailable custom reason code is preserved",
        {"available": False, "reason": " rows_exception ", "reason_code": " custom_code "},
        _expected(available=False, reason="rows_exception", reason_code="custom_code"),
    ),
    (
        "partial edge stats are not widened",
        {
            "ids": ("A", "B"),
            "edges": [{"from": "A", "to": "B", "edge_type": "process"}],
            "makespan_end": "2026-01-01 09:00:00",
            "edge_type_stats": {"process": 1},
            "edge_count": "1",
        },
        _expected(
            ids=["A", "B"],
            edges=[{"from": "A", "to": "B", "edge_type": "process"}],
            makespan_end="2026-01-01 09:00:00",
            edge_type_stats={"process": 1},
            edge_count=1,
        ),
    ),
    (
        "empty edge stats fall back to four default buckets",
        {"edge_type_stats": {}},
        _expected(),
    ),
]


@pytest.mark.parametrize(("case_name", "raw", "expected"), _CASES)
def test_critical_chain_normalize_single_helper_preserves_legacy_edges(
    case_name: str, raw: Any, expected: Dict[str, Any]
) -> None:
    assert _normalize_critical_chain_result(raw) == expected, case_name


def test_critical_chain_normalize_copies_edge_dicts() -> None:
    edge = {"from": "A", "to": "B", "edge_type": "process"}

    normalized = _normalize_critical_chain_result({"edges": [edge]})

    assert normalized["edges"] == [edge]
    assert normalized["edges"][0] is not edge

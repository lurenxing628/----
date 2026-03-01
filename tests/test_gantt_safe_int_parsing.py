from __future__ import annotations

from typing import Any

from core.services.scheduler import gantt_critical_chain, gantt_tasks
from core.services.scheduler._sched_utils import _safe_int


def test_safe_int_parses_integer_float_forms() -> None:
    assert _safe_int(5) == 5
    assert _safe_int(5.0) == 5
    assert _safe_int("5") == 5
    assert _safe_int("5.0") == 5
    assert _safe_int("5.00") == 5

    assert _safe_int(None) == 0
    assert _safe_int("") == 0
    assert _safe_int("   ") == 0
    assert _safe_int("abc") == 0
    assert _safe_int("5.5") == 0
    assert _safe_int(5.5) == 0
    assert _safe_int("5e0") == 0
    assert _safe_int(True) == 0

    assert _safe_int("abc", default=7) == 7
    assert _safe_int(5.5, default=7) == 7


def _task(*, tid: str, batch_id: Any, piece_id: Any, seq: Any) -> dict:
    return {
        "id": tid,
        "start": "2026-01-01 00:00:00",
        "dependencies": "",
        "edge_type": "",
        "meta": {
            "batch_id": batch_id,
            "piece_id": piece_id,
            "seq": seq,
        },
    }


def test_attach_process_dependencies_sorts_by_seq_even_when_seq_is_float() -> None:
    t10 = _task(tid="T10", batch_id="B1", piece_id="P1", seq=10.0)
    t5 = _task(tid="T5", batch_id="B1", piece_id="P1", seq=5.0)
    tasks = [t10, t5]

    gantt_tasks._attach_process_dependencies(tasks)

    assert t5["dependencies"] == ""
    assert t5["edge_type"] == ""
    assert t10["dependencies"] == "T5"
    assert t10["edge_type"] == "process"
    assert t10["meta"]["edge_type"] == "process"
    assert t10["meta"]["dependency_from"] == "T5"


def test_critical_chain_build_process_prev_respects_seq_even_when_seq_is_float() -> None:
    rows = [
        {
            "op_code": "A",
            "op_id": 1,
            "start_time": "2026-01-01 01:00:00",
            "end_time": "2026-01-01 02:00:00",
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 0,
            "machine_id": "M1",
            "operator_id": "O1",
        },
        {
            "op_code": "B",
            "op_id": 2,
            "start_time": "2026-01-01 00:00:00",
            "end_time": "2026-01-01 00:30:00",
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 5.0,
            "machine_id": "M1",
            "operator_id": "O1",
        },
        {
            "op_code": "C",
            "op_id": 3,
            "start_time": "2026-01-01 03:00:00",
            "end_time": "2026-01-01 04:00:00",
            "batch_id": "B1",
            "piece_id": "P1",
            "seq": 10.0,
            "machine_id": "M1",
            "operator_id": "O1",
        },
    ]

    nodes = gantt_critical_chain._build_nodes(rows)
    assert nodes["B"]["seq"] == 5

    proc_prev = gantt_critical_chain._build_process_prev(nodes)
    assert proc_prev["B"] == "A"
    assert proc_prev["C"] == "B"


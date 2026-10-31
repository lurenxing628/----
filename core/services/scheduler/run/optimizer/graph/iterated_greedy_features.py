"""Decoded-entry features the destroy generators read: start-sorted orders, machines and tardy/critical signals."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def entry_features(search: Any, entry: Any) -> Dict[str, Any]:
    """An entry is a successful decode, so every operation of the parent order has its decoded row."""
    if entry.features is None:
        entry.features = {}
    if "signals" not in entry.features:
        rows = {row.op_id: row for row in entry.candidate["results"]}
        starts: Dict[int, float] = {}
        machines: Dict[int, str] = {}
        for op_id in search.parent.order:
            row = rows[op_id]
            starts[op_id] = (row.start_time - search.start_dt).total_seconds() / 3600.0
            machines[op_id] = row.machine_id or ""
        by_start = tuple(sorted(entry.order, key=starts.__getitem__))
        loaded = [op_id for op_id in entry.order if machines[op_id]]
        grouped: Dict[str, List[int]] = {}
        for op_id in loaded:
            grouped.setdefault(machines[op_id], []).append(op_id)
        by_machine: Dict[str, Tuple[int, ...]] = {
            machine: tuple(sorted(ops, key=starts.__getitem__))
            for machine, ops in grouped.items()
        }
        machine_candidates = tuple(op_id for op_id in loaded if len(by_machine[machines[op_id]]) >= 2)
        entry.features.update(
            machines=machines,
            by_start=by_start,
            by_machine=by_machine,
            machine_candidates=machine_candidates,
            signals=tardy_signals(search, rows),
        )
    return entry.features


def tardy_signals(search: Any, rows: Dict[int, Any]) -> Dict[int, float]:
    """Tardiness in hours past the metric due deadline, plus a hair for critical-path operations."""
    signals: Dict[int, float] = {}
    for op_id in search.parent.order:
        metric = search.metrics[op_id]
        finish = (rows[op_id].end_time - search.start_dt).total_seconds() / 3600.0
        tardy = max(finish - metric["due_deadline_hours"], 0.0)
        signals[op_id] = tardy + (1e-3 if metric["is_on_critical_path"] else 0.0)
    return signals


__all__ = ["entry_features", "tardy_signals"]

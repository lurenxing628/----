"""Decoded-entry features the destroy generators read: start hours, machines and tardy/critical signals."""
from __future__ import annotations

from typing import Any, Dict


def entry_features(search: Any, entry: Any) -> Dict[str, Any]:
    if entry.features is None:
        rows = {int(row.op_id): row for row in entry.candidate["results"]}
        starts: Dict[int, float] = {}
        machines: Dict[int, str] = {}
        for op_id in search.parent.order:
            row = rows.get(op_id)
            if row is None:
                continue
            if row.start_time is not None:
                starts[op_id] = (row.start_time - search.start_dt).total_seconds() / 3600.0
            machines[op_id] = str(row.machine_id or "")
        entry.features = {"starts": starts, "machines": machines, "signals": tardy_signals(search, entry.candidate)}
    return entry.features


def tardy_signals(search: Any, candidate: Dict[str, Any]) -> Dict[int, float]:
    """Tardiness in hours past the metric due deadline, plus a hair for critical-path operations."""
    signals: Dict[int, float] = {}
    rows = {int(row.op_id): row for row in candidate["results"]}
    for op_id in search.parent.order:
        metric = search.metrics.get(op_id, {})
        row = rows.get(op_id)
        tardy = 0.0
        if row is not None and "due_deadline_hours" in metric:
            finish = (row.end_time - search.start_dt).total_seconds() / 3600.0
            tardy = max(finish - float(metric["due_deadline_hours"]), 0.0)
        signals[op_id] = tardy + (1e-3 if metric.get("is_on_critical_path") else 0.0)
    return signals


__all__ = ["entry_features", "tardy_signals"]

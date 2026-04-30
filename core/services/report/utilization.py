from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .calculation_helpers import is_internal_source, overlap_seconds, parse_dt


def compute_utilization(
    *,
    schedule_rows: Sequence[Mapping[str, Any]],
    start_dt: datetime,
    end_dt_excl: datetime,
    cap_hours: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_machine: Dict[str, Dict[str, Any]] = {}
    by_operator: Dict[str, Dict[str, Any]] = {}

    for r in schedule_rows:
        hours = _row_hours_in_window(r, start_dt, end_dt_excl)
        if hours is None:
            continue
        _add_machine_hours(by_machine, r, hours)
        _add_operator_hours(by_operator, r, hours)

    machine_rows = _build_utilization_rows(by_machine.values(), cap_hours, "machine_id")
    operator_rows = _build_utilization_rows(by_operator.values(), cap_hours, "operator_id")
    return machine_rows, operator_rows


def _row_hours_in_window(row: Mapping[str, Any], start_dt: datetime, end_dt_excl: datetime) -> Optional[float]:
    if not is_internal_source(row.get("source")):
        return None
    s_dt = parse_dt(row.get("start_time"))
    e_dt = parse_dt(row.get("end_time"))
    if not s_dt or not e_dt:
        return None
    sec = overlap_seconds(s_dt, e_dt, start_dt, end_dt_excl)
    if sec <= 0:
        return None
    return sec / 3600.0


def _add_machine_hours(items: Dict[str, Dict[str, Any]], row: Mapping[str, Any], hours: float) -> None:
    machine_id = str(row.get("machine_id") or "").strip()
    if not machine_id:
        return
    item = items.setdefault(
        machine_id,
        {"machine_id": machine_id, "machine_name": row.get("machine_name"), "hours": 0.0, "task_count": 0},
    )
    _add_hours(item, hours)


def _add_operator_hours(items: Dict[str, Dict[str, Any]], row: Mapping[str, Any], hours: float) -> None:
    operator_id = str(row.get("operator_id") or "").strip()
    if not operator_id:
        return
    item = items.setdefault(
        operator_id,
        {"operator_id": operator_id, "operator_name": row.get("operator_name"), "hours": 0.0, "task_count": 0},
    )
    _add_hours(item, hours)


def _add_hours(item: Dict[str, Any], hours: float) -> None:
    item["hours"] = float(item["hours"]) + float(hours)
    item["task_count"] = int(item["task_count"]) + 1


def _build_utilization_rows(items: Iterable[Dict[str, Any]], cap_hours: float, id_key: str) -> List[Dict[str, Any]]:
    rows = []
    for it in items:
        h = float(it["hours"])
        util = (h / cap_hours) if cap_hours > 0 else None
        rows.append(
            {
                **it,
                "hours": round(h, 2),
                "capacity_hours": round(cap_hours, 2),
                "utilization": round(util, 4) if util is not None else None,
            }
        )
    rows.sort(key=lambda x: (-(x.get("hours") or 0.0), x.get(id_key) or ""))
    return rows

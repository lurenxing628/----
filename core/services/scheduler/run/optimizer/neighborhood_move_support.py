from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.changeover_events import type_transition
from core.algorithm_contracts.date_parsers import due_exclusive, parse_date

_UNSET = object()


def latest_result(results: List[Any]) -> Optional[Any]:
    # Decoded rows carry their batch id and sequence (ScheduleResult, schedule_seed_contracts).
    rows = [row for row in results if row.end_time is not None]
    if not rows:
        return None
    return max(rows, key=lambda row: (row.end_time, row.batch_id, row.seq))


def finish_by_batch(results: List[Any]) -> Dict[str, datetime]:
    out: Dict[str, datetime] = {}
    for result in results:
        bid = result.batch_id
        end_time = result.end_time
        if not isinstance(end_time, datetime):
            continue
        current = out.get(bid)
        if current is None or end_time > current:
            out[bid] = end_time
    return out


def batch_due_date(batch: Any) -> Optional[date]:
    due_raw = batch.due_date
    if isinstance(due_raw, date) and not isinstance(due_raw, datetime):
        return due_raw
    if isinstance(due_raw, datetime):
        return due_raw.date()
    text = str(due_raw or "").strip()
    return parse_date(text) if text else None


def prepare_batch_due_dates(
    batches: Dict[str, Any],
    *,
    native_preparation: Any = None,
) -> Dict[str, Optional[date]]:
    if (
        native_preparation is not None
        and (batches is native_preparation.batches or set(batches) == set(native_preparation.batches))
        and native_preparation.all_batch_due_dates_valid()
    ):
        return dict(native_preparation.parsed_due_dates())
    return {bid: batch_due_date(batch) for bid, batch in batches.items()}


def most_tardy_batch(
    *,
    finish_by_batch_rows: Dict[str, datetime],
    batches: Dict[str, Any],
    due_by_batch: Optional[Dict[str, Optional[date]]] = None,
) -> Optional[str]:
    best: Optional[Tuple[str, float]] = None
    for bid, batch in batches.items():
        due_date = due_by_batch[bid] if due_by_batch is not None and bid in due_by_batch else batch_due_date(batch)
        finish_time = finish_by_batch_rows.get(bid)
        if due_date is None or finish_time is None:
            continue
        due_end = due_exclusive(due_date)
        if finish_time < due_end:
            continue
        tardiness = max((finish_time - due_end).total_seconds() / 3600.0, 0.0)
        if best is None or (tardiness, bid) > (best[1], best[0]):
            best = (bid, float(tardiness))
    return best[0] if best is not None else None


def earliest_due_pressure_batch(
    *,
    finish_by_batch_rows: Dict[str, datetime],
    batches: Dict[str, Any],
    due_by_batch: Optional[Dict[str, Optional[date]]] = None,
) -> str:
    best: Optional[Tuple[date, str]] = None
    for bid, batch in batches.items():
        due_date = due_by_batch[bid] if due_by_batch is not None and bid in due_by_batch else batch_due_date(batch)
        if due_date is None:
            continue
        finish_time = finish_by_batch_rows.get(bid)
        if finish_time is not None and finish_time < due_exclusive(due_date):
            continue
        key = (due_date, bid)
        if best is None or key < best:
            best = key
    return best[1] if best is not None else ""


def _group_by_machine(results: List[Any]) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for result in results:
        raw_machine = result.machine_id
        machine_id = str(raw_machine) if raw_machine is not None and str(raw_machine).strip() else ""
        if machine_id:
            grouped.setdefault(machine_id, []).append(result)
    return grouped


def _bottleneck_from_groups(grouped: Dict[str, List[Any]]) -> List[Any]:
    if not grouped:
        return []
    machine_id = max(grouped, key=lambda mid: (busy_hours(grouped[mid]), len(grouped[mid]), mid))
    return grouped[machine_id]


def bottleneck_machine_rows(results: List[Any]) -> List[Any]:
    return _bottleneck_from_groups(_group_by_machine(results))


def busy_hours(rows: List[Any]) -> float:
    total = 0.0
    for row in rows:
        start = row.start_time
        end = row.end_time
        if isinstance(start, datetime) and isinstance(end, datetime) and end > start:
            total += (end - start).total_seconds() / 3600.0
    return float(total)


def _changeover_from_groups(grouped: Dict[str, List[Any]]) -> Optional[Tuple[Any, Any]]:
    for rows in grouped.values():
        previous = None
        previous_type = ""
        for row in sorted(rows, key=result_time_key):
            # Point events neither switch nor separate their timed neighbours; an unknown type does.
            if row.start_time == row.end_time:
                continue
            current_type = op_type(row)
            if previous is not None and type_transition(previous_type, current_type, previous.op_id, row.op_id) == 1:
                return previous, row
            previous, previous_type = row, current_type
    return None


def first_changeover_pair(results: List[Any]) -> Optional[Tuple[Any, Any]]:
    return _changeover_from_groups(_group_by_machine(results))


class LocalSearchResultFacts:
    """Lazy per-result-list facts for ordinary local-search neighbourhood moves."""

    def __init__(
        self,
        results: List[Any],
        *,
        batches: Optional[Dict[str, Any]] = None,
        due_by_batch: Optional[Dict[str, Optional[date]]] = None,
    ) -> None:
        self.results = results
        self._batches = batches
        self._due_by_batch = due_by_batch
        self._finish_map: Any = _UNSET
        self._latest_row: Any = _UNSET
        self._most_tardy_batch_id: Any = _UNSET
        self._earliest_due_pressure_batch_id: Any = _UNSET
        self._machine_groups: Any = _UNSET
        self._bottleneck_rows: Any = _UNSET
        self._bottleneck_latest_row: Any = _UNSET
        self._changeover_pair: Any = _UNSET

    def due_by_batch(self, batches: Dict[str, Any]) -> Dict[str, Optional[date]]:
        if self._due_by_batch is None or (self._batches is not None and self._batches is not batches):
            self._batches = batches
            self._due_by_batch = prepare_batch_due_dates(batches)
        return self._due_by_batch

    def finish_map(self) -> Dict[str, datetime]:
        if self._finish_map is _UNSET:
            self._finish_map = finish_by_batch(self.results)
        return self._finish_map

    def latest_row(self) -> Optional[Any]:
        if self._latest_row is _UNSET:
            self._latest_row = latest_result(self.results)
        return self._latest_row

    def most_tardy_batch_id(self, batches: Dict[str, Any]) -> Optional[str]:
        if self._most_tardy_batch_id is _UNSET:
            self._most_tardy_batch_id = most_tardy_batch(
                finish_by_batch_rows=self.finish_map(),
                batches=batches,
                due_by_batch=self.due_by_batch(batches),
            )
        return self._most_tardy_batch_id

    def earliest_due_pressure_batch_id(self, batches: Dict[str, Any]) -> str:
        if self._earliest_due_pressure_batch_id is _UNSET:
            self._earliest_due_pressure_batch_id = earliest_due_pressure_batch(
                finish_by_batch_rows=self.finish_map(),
                batches=batches,
                due_by_batch=self.due_by_batch(batches),
            )
        return self._earliest_due_pressure_batch_id

    def machine_groups(self) -> Dict[str, List[Any]]:
        if self._machine_groups is _UNSET:
            self._machine_groups = _group_by_machine(self.results)
        return self._machine_groups

    def bottleneck_rows(self) -> List[Any]:
        if self._bottleneck_rows is _UNSET:
            self._bottleneck_rows = _bottleneck_from_groups(self.machine_groups())
        return self._bottleneck_rows

    def bottleneck_latest_row(self) -> Optional[Any]:
        if self._bottleneck_latest_row is _UNSET:
            rows = self.bottleneck_rows()
            self._bottleneck_latest_row = latest_result(rows) if rows else None
        return self._bottleneck_latest_row

    def changeover_pair(self) -> Optional[Tuple[Any, Any]]:
        if self._changeover_pair is _UNSET:
            self._changeover_pair = _changeover_from_groups(self.machine_groups())
        return self._changeover_pair


def result_time_key(row: Any) -> Tuple[datetime, datetime, int]:
    return (
        row.start_time,
        row.end_time,
        row.op_id,
    )


def op_type(result: Any) -> str:
    return result.op_type_id or ""


def pick_resource_pair(pool: Dict[str, Any]) -> Optional[Tuple[str, str, int]]:
    operators_by_machine = pool["operators_by_machine"]
    pair_rank = pool["pair_rank"]
    for machine_id in sorted(operators_by_machine, key=str):
        operators = operators_by_machine[machine_id]
        if len(operators) < 2:
            continue
        for operator_id in reversed(operators):
            # 排名都是 build_resource_pool 算出的整数（邻域降级覆盖为 -1）；没有排名的人机对
            # 与自动派工 auto_assign._pair_rank 同口径按 9999。
            rank = pair_rank.get((operator_id, machine_id), 9999)
            if rank > -1:
                return operator_id, machine_id, rank
    return None


__all__ = [
    "LocalSearchResultFacts",
    "bottleneck_machine_rows",
    "earliest_due_pressure_batch",
    "finish_by_batch",
    "first_changeover_pair",
    "latest_result",
    "most_tardy_batch",
    "pick_resource_pair",
    "prepare_batch_due_dates",
]

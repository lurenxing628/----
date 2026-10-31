from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, NoReturn, Optional, Protocol, Tuple, cast

from core.models.workbench_preflight import SCHEDULING_PREFERENCES_ACTION
from core.shared.local_datetime import format_local_datetime, parse_local_datetime
from core.shared.strict_json import load_strict_json

SQL_PARSE_FUNCTION = "aps_parse_dt"
NON_INPUT_RECEIPT_ACTIONS = (SCHEDULING_PREFERENCES_ACTION, "scheduling.run")
NON_INPUT_RECEIPT_PREFIXES = ("trial.", "dashboard.")
_REMEMBERED_RECEIPT_OUTCOME: ContextVar[Optional[Tuple[str, str]]] = ContextVar(
    "aps_remembered_receipt_outcome", default=None
)


@contextmanager
def remember_receipt_outcome(outcome_json: str, result: str) -> Iterator[None]:
    token = _REMEMBERED_RECEIPT_OUTCOME.set((outcome_json, result))
    try:
        yield
    finally:
        _REMEMBERED_RECEIPT_OUTCOME.reset(token)


def _unreadable_outcome() -> NoReturn:
    raise ValueError("Receipt outcome is not strict JSON")


def receipt_revision_category(action: Any, outcome_json: Any) -> str:
    if type(action) is str:
        if action in NON_INPUT_RECEIPT_ACTIONS or (
            action != "trial.scenario.adopt" and action.startswith(NON_INPUT_RECEIPT_PREFIXES)
        ):
            return ""
    if type(outcome_json) is str:
        remembered = _REMEMBERED_RECEIPT_OUTCOME.get()
        if remembered is not None and remembered[0] == outcome_json:
            result = remembered[1]
        else:
            try:
                outcome = load_strict_json(outcome_json, on_malformed=_unreadable_outcome)
            except ValueError:
                outcome = None
            result = outcome.get("result") if type(outcome) is dict else None
        if result == "unchanged":
            return ""
    if action == "trial.scenario.adopt":
        return "trial_adoption"
    return "production_input"


def parse_dt_for_sql(value: Any) -> Optional[str]:
    parsed = parse_local_datetime(value)
    return format_local_datetime(parsed) if parsed is not None else None


def require_dt_for_sql(value: Any, error_message: str) -> str:
    parsed = parse_dt_for_sql(value)
    if parsed is None:
        raise ValueError(error_message)
    return parsed


def _interval_values(start, end):
    # SQL callers retain TRIM(CAST(... AS TEXT)); the local parser owns the rules.
    return parse_dt_for_sql(start), parse_dt_for_sql(end)


def _interval_admitted(start, end, window_end, window_start):
    start, end = _interval_values(start, end)
    if start is None or end is None or end <= start:
        return 1
    return int(window_end is not None and window_start is not None and start < window_end and end > window_start)


class _IntervalSummary:
    def __init__(self):
        self.first, self.last, self.invalid = None, None, 0

    def step(self, row_id: Any, start: Any, end: Any, allow_points: int) -> None:
        if row_id is None:
            return
        start, end = _interval_values(start, end)
        if start is None or end is None or (end < start if allow_points else end <= start):
            self.invalid += 1
            return
        self.first = start if self.first is None else min(self.first, start)
        self.last = end if self.last is None else max(self.last, end)

    def finalize(self) -> str:
        return json.dumps((self.first, self.last, self.invalid), separators=(",", ":"))


class _IntervalAggregateConnection(Protocol):
    """SQLite accepts this four-input aggregate and its TEXT final value."""

    def create_aggregate(self, name: str, num_params: int,
                         aggregate_class: Callable[[], _IntervalSummary]) -> None: ...


def decode_interval_summary(value):
    return json.loads(value) if value is not None else (None, None, 0)


def register_schedule_time_sql_functions(conn: sqlite3.Connection) -> None:
    for name, count, function in (
        (SQL_PARSE_FUNCTION, 1, parse_dt_for_sql),
        ("aps_interval_admitted", 4, _interval_admitted),
        ("aps_receipt_revision_category", 2, receipt_revision_category),
    ):
        try:
            conn.create_function(name, count, function, deterministic=True)
        except sqlite3.NotSupportedError:
            conn.create_function(name, count, function)
    cast(_IntervalAggregateConnection, conn).create_aggregate("aps_interval_summary", 4, _IntervalSummary)


__all__ = [
    "NON_INPUT_RECEIPT_ACTIONS",
    "NON_INPUT_RECEIPT_PREFIXES",
    "SQL_PARSE_FUNCTION",
    "decode_interval_summary",
    "parse_dt_for_sql",
    "receipt_revision_category",
    "register_schedule_time_sql_functions",
    "remember_receipt_outcome",
    "require_dt_for_sql",
]

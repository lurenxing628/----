from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable, Optional, Protocol, cast

from core.shared.local_datetime import format_local_datetime, parse_local_datetime

_SQL_PARSE_FUNCTION = "aps_parse_dt"


def _time_column(alias: Optional[str], name: str) -> str:
    return f"{alias}.{name}" if alias else name


def _time_text(alias: Optional[str], name: str) -> str:
    return f"TRIM(CAST({_time_column(alias, name)} AS TEXT))"


def time_dt(alias: Optional[str], name: str) -> str:
    # 使用注册到 SQLite 连接上的 Python 解析函数，避免 SQLite datetime()
    # 对不存在日期、24 点、超出微秒精度等值过于宽松，和上层 Python 解析口径漂移。
    return f"{_SQL_PARSE_FUNCTION}({_time_text(alias, name)})"


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

    def step(self, row_id: Any, start: Any, end: Any) -> None:
        if row_id is None:
            return
        start, end = _interval_values(start, end)
        if start is None or end is None or end <= start:
            self.invalid += 1
            return
        self.first = start if self.first is None else min(self.first, start)
        self.last = end if self.last is None else max(self.last, end)

    def finalize(self) -> str:
        return json.dumps((self.first, self.last, self.invalid), separators=(",", ":"))


class _IntervalAggregateConnection(Protocol):
    """SQLite accepts this three-input aggregate and its TEXT final value."""

    def create_aggregate(self, name: str, num_params: int,
                         aggregate_class: Callable[[], _IntervalSummary]) -> None: ...


def interval_summary_sql(alias=None):
    return "aps_interval_summary(" + _time_column(alias, "id") + "," + _time_text(alias, "start_time") + "," + _time_text(alias, "end_time") + ")"


def decode_interval_summary(value):
    return json.loads(value) if value is not None else (None, None, 0)


def register_schedule_time_sql_functions(conn: sqlite3.Connection) -> None:
    register = getattr(conn, "create_function", None)
    if not callable(register):
        return
    for name, count, function in ((_SQL_PARSE_FUNCTION, 1, parse_dt_for_sql),
                                  ("aps_interval_admitted", 4, _interval_admitted)):
        try:
            register(name, count, function, deterministic=True)
        except sqlite3.NotSupportedError:
            register(name, count, function)
    cast(_IntervalAggregateConnection, conn).create_aggregate("aps_interval_summary", 3, _IntervalSummary)


def overlap_or_bad_time_sql(alias: Optional[str]) -> str:
    """区间与绑定参数 [?, ?]（顺序：end_param, start_param）重叠，或本身是坏时间行。

    用于"既捞回与查询窗重叠的有效区间、也把坏时间行兜回上层做降级提示"的查询，
    让 schedule 计划明细与设备停机明细对"坏时间/重叠"的判定来自同一处定义，避免漂移。
    """
    return "aps_interval_admitted(" + _time_text(alias, "start_time") + "," + _time_text(alias, "end_time") + ",?,?)"


DETAIL_OVERLAP_OR_BAD_TIME_SQL = overlap_or_bad_time_sql("s")


__all__ = [
    "DETAIL_OVERLAP_OR_BAD_TIME_SQL",
    "interval_summary_sql",
    "decode_interval_summary",
    "overlap_or_bad_time_sql",
    "parse_dt_for_sql",
    "require_dt_for_sql",
    "register_schedule_time_sql_functions",
    "time_dt",
]

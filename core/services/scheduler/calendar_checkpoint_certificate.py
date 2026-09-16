"""Calendar business contents for SGS checkpoints, independent of filled policy caches.

SQLite metadata is checked once per decode (and again while building new content).
Business tables are read again only after a version change, except writable
transactions: their rollback cannot be certified by total_changes, so their
uncommitted contents are never reused or put into the reusable cache.
"""
from __future__ import annotations

import hashlib
import sqlite3

from core.algorithm_runtime.native_snapshot import make_class_guard
from core.infrastructure.errors import ValidationError
from data.repositories.calendar_repo import CalendarRepository
from data.repositories.operator_calendar_repo import OperatorCalendarRepository
from data.repositories.operator_shift_repo import OperatorShiftRepository

from .calendar_engine import CalendarEngine
from .operator_shift_calendar import OperatorShiftCalendar

_GUARDS = {kind: make_class_guard(kind) for kind in (
    CalendarEngine, OperatorShiftCalendar, CalendarRepository, OperatorCalendarRepository, OperatorShiftRepository,
)}
# Include every field read by CalendarEngine / OperatorShiftCalendar; names and remarks do not affect time.
_BUSINESS_QUERIES = (
    "SELECT date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent FROM WorkCalendar ORDER BY date",
    "SELECT operator_id,date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent FROM OperatorCalendar ORDER BY operator_id,date",
    "SELECT operator_id,shift_profile_id FROM WorkbenchOperatorProfiles ORDER BY operator_id",
    "SELECT profile_id,anchor_date,cycle_days,status FROM WorkbenchShiftProfiles ORDER BY profile_id",
    "SELECT profile_id,day_offset,is_rest,shift_start,shift_end FROM WorkbenchShiftPatternDays ORDER BY profile_id,day_offset",
)
_METADATA_STATEMENTS = ("PRAGMA main.data_version", "PRAGMA main.schema_version",
                        "PRAGMA temp.schema_version", "PRAGMA query_only")


def calendar_checkpoint_snapshot(service):
    fields = vars(service)
    connection = fields.get("conn")
    if not _native_connection(connection) or not _native_engine(fields.get("_engine"), connection):
        return None
    try:
        metadata = _metadata(connection)
        reusable = not connection.in_transaction or metadata[-1] == 1
        cached = fields.get("_decode_checkpoint_calendar_cache")
        if reusable and cached is not None and cached[0] is connection and cached[1] == metadata:
            return cached[2]
        rows = tuple(tuple(tuple(row) for row in connection.execute(query).fetchall()) for query in _BUSINESS_QUERIES)
        after = _metadata(connection)
        if metadata != after:
            raise ValidationError("读取断点日历证书时日历输入发生变化，请重新排产。", field="decode_checkpoint",
                                  details={"reason": "decode_checkpoint_calendar_changed_during_read"})
        signature = "calendar-business-v1", hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()
        if reusable:
            fields["_decode_checkpoint_calendar_cache"] = connection, metadata, signature
        else:
            # A later rollback+BEGIN may keep every SQLite counter unchanged.
            fields.pop("_decode_checkpoint_calendar_cache", None)
        return signature
    except sqlite3.Error as exc:
        raise ValidationError("无法读取断点所需的日历业务证书，请使用全量解码。", field="decode_checkpoint",
                              details={"reason": "decode_checkpoint_calendar_unavailable"}) from exc


def _native_connection(connection):
    return (type(connection) is sqlite3.Connection
            and (connection.row_factory is None or connection.row_factory is sqlite3.Row)
            and connection.text_factory is str)


def _metadata(connection):
    values = []
    for statement in _METADATA_STATEMENTS:
        row = connection.execute(statement).fetchone()
        if row is None or len(row) != 1 or type(row[0]) is not int:
            raise ValidationError("日历数据库版本证据无效，请使用全量解码。", field="decode_checkpoint",
                                  details={"reason": "decode_checkpoint_calendar_unavailable"})
        values.append(row[0])
    return connection.total_changes, connection.in_transaction, *values


def _native_engine(engine, connection):
    if not _GUARDS[CalendarEngine](engine) or vars(engine).get("conn") is not connection:
        return False
    fields = vars(engine)
    shifts = fields.get("operator_shift_calendar")
    if not _GUARDS[OperatorShiftCalendar](shifts):
        return False
    repositories = ((fields.get("repo"), CalendarRepository),
                    (fields.get("operator_calendar_repo"), OperatorCalendarRepository),
                    (vars(shifts).get("repo"), OperatorShiftRepository))
    return all(_GUARDS[kind](repository) and vars(repository).get("conn") is connection
               for repository, kind in repositories)

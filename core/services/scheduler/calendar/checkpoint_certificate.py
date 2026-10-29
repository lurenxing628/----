"""Calendar business contents for SGS checkpoints, independent of filled policy caches.

SQLite metadata is checked once per decode. An already captured run supplies its
fixed business rows directly. Live business tables are read again only after a
version change, except writable transactions: their rollback cannot be certified
by total_changes, so their uncommitted contents are never reused or put into the
reusable cache.
"""
from __future__ import annotations

import sqlite3

from core.errors import AppError, ValidationError
from core.infrastructure.connection_guards import connection_snapshot_metadata
from data.repositories.calendar_checkpoint_repo import CalendarCheckpointRepository


def calendar_checkpoint_snapshot(service):
    fields = vars(service)
    connection = fields.get("conn")
    engine = fields.get("_engine")
    if connection is None or engine is None:
        return None
    try:
        metadata = _metadata(connection)
        reusable = not connection.in_transaction or metadata[-1] == 1
        cached = fields.get("_decode_checkpoint_calendar_cache")
        if reusable and cached is not None and cached[0] is connection and cached[1] == metadata:
            return cached[2]
        # The fixed business SELECTs already return immutable row tuples in a stable order.
        rows = CalendarCheckpointRepository(connection).calendar_signature_rows(capture=engine.capture)
        signature = "calendar-business-v1", rows
        if reusable:
            fields["_decode_checkpoint_calendar_cache"] = connection, metadata, signature
        else:
            # A later rollback+BEGIN may keep every SQLite counter unchanged.
            fields.pop("_decode_checkpoint_calendar_cache", None)
        return signature
    except (sqlite3.Error, AppError) as exc:
        # BaseRepository translates sqlite3 errors into AppError (cause kept); both mean the certificate is unreadable.
        raise ValidationError("无法读取断点所需的日历业务证书，请使用全量解码。", field="decode_checkpoint",
                              details={"reason": "decode_checkpoint_calendar_unavailable"}) from exc


def _metadata(connection):
    try:
        values = connection_snapshot_metadata(connection)
    except ValueError:
        raise ValidationError("日历数据库版本证据无效，请使用全量解码。", field="decode_checkpoint",
                              details={"reason": "decode_checkpoint_calendar_unavailable"}) from None
    return (connection.total_changes, connection.in_transaction) + values

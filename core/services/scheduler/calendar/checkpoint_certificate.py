"""Calendar business contents for SGS checkpoints, independent of filled policy caches.

SQLite metadata is checked once per decode. An already captured run supplies its
fixed business rows directly. Live business tables are read again only after a
version change, except writable transactions: their rollback cannot be certified
by total_changes, so their uncommitted contents are never reused or put into the
reusable cache.
"""
from __future__ import annotations

import sqlite3
from typing import Tuple

from core.errors import AppError, ValidationError
from core.infrastructure.connection_guards import connection_snapshot_metadata
from data.repositories.calendar_checkpoint_repo import CalendarCheckpointRepository


def read_checkpoint_connection_metadata(conn) -> Tuple[Tuple[int, bool, int, int, int, int], bool]:
    try:
        v0, v1, v2, v3 = connection_snapshot_metadata(conn)
        metadata = (conn.total_changes, conn.in_transaction, v0, v1, v2, v3)
    except sqlite3.Error as exc:
        raise ValidationError("无法读取断点所需的日历业务证书，请使用全量解码。", field="decode_checkpoint",
                              details={"reason": "decode_checkpoint_calendar_unavailable"}) from exc
    return metadata, (not conn.in_transaction or v3 == 1)


def read_calendar_checkpoint_signature(conn, *, capture=None) -> Tuple[str, tuple]:
    try:
        # The fixed business SELECTs already return immutable row tuples in a stable order.
        rows = CalendarCheckpointRepository(conn).calendar_signature_rows(capture=capture)
    except (sqlite3.Error, AppError) as exc:
        # BaseRepository translates sqlite3 errors into AppError (cause kept); both mean the certificate is unreadable.
        raise ValidationError("无法读取断点所需的日历业务证书，请使用全量解码。", field="decode_checkpoint",
                              details={"reason": "decode_checkpoint_calendar_unavailable"}) from exc
    return "calendar-business-v1", rows

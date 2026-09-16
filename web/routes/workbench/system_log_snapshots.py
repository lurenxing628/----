"""Keep an immutable, sanitized log window for paging and its exact export."""

import json
import time
from dataclasses import dataclass
from threading import RLock

from flask import current_app

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.services.workbench import messages
from core.services.workbench.run_data_context import restored_context_ref

from .read_context import bind_read_snapshot
from .system_context import database_scope, journal

_EXTENSION = "workbench_system_log_snapshots_v1"
_TTL_SECONDS = 900
_MAX_WINDOWS = 32
_MAX_BYTES = 64 * 1024 * 1024
_LOCK = RLock()


@dataclass(frozen=True)
class _LogWindow:
    document: str
    expires_at: float
    size_bytes: int


def _windows():
    windows = current_app.extensions.setdefault(_EXTENSION, {})
    now = time.monotonic()
    for token in list(windows):
        if windows[token].expires_at <= now:
            del windows[token]
    return windows


def _bound_scope(scope):
    event_journal = journal() if current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR") else None
    generation = restored_context_ref(event_journal.database_scope, event_journal.records()) if event_journal else restored_context_ref(database_scope(), [])
    return {**scope, "data_context_ref": generation}


def retain_log_snapshot(scope, rows, sources):
    data = {"rows": rows, "sources": sources}
    document = canonical_json(data)
    size = len(document.encode("utf-8"))
    if size > _MAX_BYTES:
        raise WorkbenchCommandRejected("snapshot_capacity_exceeded", "这段日志超过暂存容量，请缩小筛选范围后重新查询。", 503)
    snapshot = bind_read_snapshot(_bound_scope(scope), input_fingerprint(data))
    with _LOCK:
        windows = _windows()
        if snapshot["snapshot_ref"] not in windows:
            while windows and (len(windows) >= _MAX_WINDOWS or sum(item.size_bytes for item in windows.values()) + size > _MAX_BYTES):
                del windows[min(windows, key=lambda token: windows[token].expires_at)]
            windows[snapshot["snapshot_ref"]] = _LogWindow(document, time.monotonic() + _TTL_SECONDS, size)
    return snapshot


def resolve_log_snapshot(scope, token):
    with _LOCK:
        window = _windows().get(token)
        if window is None:
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        data = json.loads(window.document)
    snapshot = bind_read_snapshot(_bound_scope(scope), input_fingerprint(data), token)
    return data["rows"], data["sources"], snapshot

"""Process-local original preview objects, never reconstructed from browser facts.

The single-machine host uses one process with threaded requests. A restart loses
pending previews, not persisted command receipts. Live previews are never evicted
to make room for new ones; capacity failure asks the caller to finish/wait first.
"""

from datetime import datetime
from threading import RLock
from typing import Dict

from flask import current_app

from core.models.workbench_calendar import MAX_CALENDAR_RANGE_DAYS, CalendarRangePreview
from core.models.workbench_command import WorkbenchCommandRejected

_EXTENSION = "workbench_calendar_previews_v1"
_LOCK = RLock()
_MAX_PREVIEWS = 32
_MAX_RETAINED_DAYS = MAX_CALENDAR_RANGE_DAYS * 2


def calendar_now() -> datetime:
    return datetime.now()


def _store() -> Dict[str, CalendarRangePreview]:
    return current_app.extensions.setdefault(_EXTENSION, {})


def retain_preview(preview: CalendarRangePreview) -> None:
    now = calendar_now().isoformat(timespec="seconds")
    with _LOCK:
        store = _store()
        for ref in list(store):
            if store[ref].expires_at <= now:
                del store[ref]
        if (len(store) >= _MAX_PREVIEWS
                or sum(len(value.dates) for value in store.values()) + len(preview.dates) > _MAX_RETAINED_DAYS):
            raise WorkbenchCommandRejected("preview_capacity", "待确认的日历变更太多，这次没有算出变更内容。请先完成或关掉已有的变更，再点「预览变更」。", 503)
        if preview.preview_ref in store:
            raise RuntimeError("同一个预览变更编号重复登记，不能替换已有内容。")
        store[preview.preview_ref] = preview


def resolve_preview(ref: str) -> CalendarRangePreview:
    """Only call from the receipt-first command guard; the domain checks TTL/facts."""
    with _LOCK:
        preview = _store().get(ref)
        if preview is None:
            raise WorkbenchCommandRejected("snapshot_stale", "预览变更已过期，日历没有修改。请重新点「预览变更」。")
        return preview


def release_preview(ref: str) -> None:
    with _LOCK:
        _store().pop(ref, None)

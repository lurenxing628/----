"""Explicit native calendar evidence for checkpoint decodes; ordinary decodes do not require it."""
from __future__ import annotations

from typing import NoReturn

from core.errors import ValidationError

from .native_snapshot import UNSUPPORTED, content_snapshot

_CERTIFICATES = {}


def register_checkpoint_calendar(calendar_type, snapshot):
    """Register alongside the original class definition."""
    _CERTIFICATES[calendar_type] = snapshot


def checkpoint_calendar_signature(calendar):
    snapshot = _CERTIFICATES.get(type(calendar))
    if snapshot is None:
        unsupported_calendar()
    value = snapshot(calendar)
    if value is None or content_snapshot(value) is UNSUPPORTED:
        unsupported_calendar()
    return value


def unsupported_calendar() -> NoReturn:
    raise ValidationError("当前日历缺少可靠的断点输入证书，请使用全量解码。", field="decode_checkpoint",
                          details={"reason": "decode_checkpoint_unsupported_calendar"})

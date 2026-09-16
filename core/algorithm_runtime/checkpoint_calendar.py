"""Explicit native calendar evidence for checkpoint decodes; ordinary decodes do not require it."""
from __future__ import annotations

from core.infrastructure.errors import ValidationError

from .native_snapshot import UNSUPPORTED, content_snapshot, make_class_guard

_CERTIFICATES = {}


def register_checkpoint_calendar(calendar_type, snapshot):
    """Register alongside the original class definition, before any runtime overrides."""
    _CERTIFICATES[calendar_type] = make_class_guard(calendar_type), snapshot


def register_stateless_checkpoint_calendar(calendar_type):
    """A declared continuous calendar is reusable only while its class and empty state are intact."""
    register_checkpoint_calendar(calendar_type, lambda calendar: () if not vars(calendar) else None)


def checkpoint_calendar_signature(calendar):
    certificate = _CERTIFICATES.get(type(calendar))
    if certificate is None or not certificate[0](calendar):
        unsupported_calendar()
    value = certificate[1](calendar)
    if value is None or content_snapshot(value) is UNSUPPORTED:
        unsupported_calendar()
    return value


def unsupported_calendar():
    raise ValidationError("当前日历缺少可靠的断点输入证书，请使用全量解码。", field="decode_checkpoint",
                          details={"reason": "decode_checkpoint_unsupported_calendar"})

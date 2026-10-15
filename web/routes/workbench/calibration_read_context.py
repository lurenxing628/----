"""Snapshot clock and binding shared only by calibration list and facet reads."""

from datetime import datetime

from flask import request

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages

from .read_context import bind_read_snapshot, resolve_read_snapshot


def page_integer(key: str, default: str) -> int:
    value = request.args.get(key, default)
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value) > 7:
        raise WorkbenchCommandRejected("invalid_input", "页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
    return int(value)


def as_of(token, binding=None):
    if token is None:
        return datetime.now().replace(microsecond=0)
    try:
        payload = resolve_read_snapshot(token) if binding is None else binding
        value = datetime.fromisoformat(payload.as_of)
        if value.tzinfo is not None:
            raise ValueError("Factory-local time required")
        return value
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE) from exc


def bind(query, content, token, clock, *, snapshot_scope=None, binding=None):
    scope = query.scope() if snapshot_scope is None else snapshot_scope
    return bind_read_snapshot(scope, content, token, as_of=clock, binding=binding)

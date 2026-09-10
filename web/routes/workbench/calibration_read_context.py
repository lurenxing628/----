"""Snapshot clock and binding shared only by calibration list and facet reads."""

import json
from datetime import datetime

from flask import request

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from web.public_token_registry import issue_public_token, resolve_public_token

from .read_context import _SCOPE, bind_read_snapshot


def page_integer(key: str, default: str) -> int:
    value = request.args.get(key, default)
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value) > 7:
        raise WorkbenchCommandRejected("invalid_input", "分页参数必须为有效正整数。", 400)
    return int(value)


def as_of(token):
    if token is None:
        return datetime.now().replace(microsecond=0)
    try:
        payload = json.loads(resolve_public_token(_SCOPE, token, message="读取快照已失效。", field="snapshot_ref"))
        value = datetime.fromisoformat(payload["as_of"])
        if value.tzinfo is not None:
            raise ValueError("Factory-local time required")
        return value
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "快照已失效，请明确刷新后重试；未切换范围。") from exc


def bind(query, fingerprint, token, clock, *, snapshot_scope=None):
    scope = query.scope() if snapshot_scope is None else snapshot_scope
    if token is not None:
        return bind_read_snapshot(scope, fingerprint, token)
    stamp = clock.isoformat(timespec="seconds")
    payload = {"version": 2, "source": "production", "scope_hash": input_fingerprint(scope),
               "fingerprint": fingerprint, "as_of": stamp}
    token = issue_public_token(_SCOPE, canonical_json(payload), ttl_seconds=900)
    return {"snapshot_ref": token, "as_of": stamp}

"""A page or download can only reuse its original, still-current read scope."""

from __future__ import annotations

import json
from datetime import datetime
from datetime import datetime as DateTimeValue

from core.errors import ValidationError
from core.models.content import content_text, same, unpacked
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench import messages
from web.public_token_registry import issue_public_token, resolve_public_token

_SCOPE = "workbench-read-v1"


def _matches_scope(payload, scope):
    return type(payload.get("version")) is int and payload["version"] == 1 and same(payload.get("scope"), scope)


def bind_read_snapshot(scope, fingerprint, token=None, *, as_of=None):
    if token is not None:
        try:
            payload = unpacked(json.loads(resolve_public_token(_SCOPE, token, message=messages.STALE, field="snapshot_ref")))
        except (ValidationError, ValueError, TypeError) as exc:
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE) from exc
        if (not isinstance(payload, dict) or payload.get("source") != "production"
                or not _matches_scope(payload, scope) or not same(payload.get("fingerprint"), fingerprint)
                or not isinstance(payload.get("as_of"), str)):
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        return {"snapshot_ref": token, "as_of": payload["as_of"]}
    if as_of is None:
        as_of = datetime.now()
    if isinstance(as_of, DateTimeValue):
        as_of = as_of.isoformat(timespec="seconds")
    payload = {"version": 1, "source": "production", "scope": scope, "fingerprint": fingerprint, "as_of": as_of}
    reference = issue_public_token(_SCOPE, content_text(payload), ttl_seconds=900)
    return {"snapshot_ref": reference, "as_of": as_of}

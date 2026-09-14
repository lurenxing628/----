"""A page or download can only reuse its original, still-current read scope."""

from __future__ import annotations

import json
from datetime import datetime

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.services.workbench import messages
from web.public_token_registry import issue_public_token, resolve_public_token

_SCOPE = "workbench-read-v1"


def _matches_scope(payload, scope):
    version = payload.get("version")
    if type(version) is not int:
        return False
    if version == 1:
        return payload.get("scope") == scope
    return version == 2 and payload.get("scope_hash") == input_fingerprint(scope)


def bind_read_snapshot(scope, fingerprint, token=None):
    if token is not None:
        try:
            payload = json.loads(resolve_public_token(_SCOPE, token, message=messages.STALE, field="snapshot_ref"))
        except (ValidationError, ValueError, TypeError) as exc:
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE) from exc
        if (not isinstance(payload, dict) or payload.get("source") != "production"
                or not _matches_scope(payload, scope) or payload.get("fingerprint") != fingerprint
                or not isinstance(payload.get("as_of"), str)):
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        return {"snapshot_ref": token, "as_of": payload["as_of"]}
    as_of = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    payload = {"version": 2, "source": "production", "scope_hash": input_fingerprint(scope),
               "fingerprint": fingerprint, "as_of": as_of}
    reference = issue_public_token(_SCOPE, canonical_json(payload), ttl_seconds=900)
    return {"snapshot_ref": reference, "as_of": as_of}

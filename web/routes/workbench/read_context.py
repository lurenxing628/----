"""Read bindings retain one canonical fact value and their original clock."""

from dataclasses import dataclass
from datetime import datetime
from datetime import datetime as DateTimeValue

from core.errors import ValidationError
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from web.public_token_registry import PublicTokenIssuer, resolve_public_token

_SCOPE = "workbench-read-v1"


def fact_value(value):
    """Canonical facts already produced by their owner stay the same object."""
    return ("text", value) if isinstance(value, str) else ("content", content_text(value))


@dataclass(frozen=True)
class ReadBinding:
    scope: str
    fingerprint: tuple
    as_of: str


def resolve_read_snapshot(token):
    try:
        return resolve_public_token(_SCOPE, token, message=messages.STALE, field="snapshot_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE) from exc


def bind_read_snapshot(scope, fingerprint, token=None, *, as_of=None, binding=None):
    scope_value, facts = content_text(scope), fact_value(fingerprint)
    if token is not None:
        payload = resolve_read_snapshot(token) if binding is None else binding
        if payload.scope != scope_value or payload.fingerprint != facts:
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        return {"snapshot_ref": token, "as_of": payload.as_of}
    if as_of is None:
        as_of = datetime.now()
    if isinstance(as_of, DateTimeValue):
        as_of = as_of.isoformat(timespec="seconds")
    issuer = PublicTokenIssuer(_SCOPE, group=facts, ttl_seconds=900)
    reference, _ = issuer.issue_bound_with_expiry(
        lambda canonical: ReadBinding(scope_value, canonical, as_of), key=(scope_value, as_of))
    return {"snapshot_ref": reference, "as_of": as_of}

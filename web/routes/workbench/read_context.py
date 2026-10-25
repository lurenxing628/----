"""Read bindings retain one canonical fact value and their original clock."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Tuple

from core.errors import ValidationError
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from web.public_token_registry import PublicTokenIssuer, resolve_public_token

_SCOPE = "workbench-read-v1"


def fact_value(facts: Any) -> Tuple[str, str]:
    """Share one canonical fact string across read and write registries while keeping type separation."""
    return ("text", facts) if isinstance(facts, str) else ("canonical", content_text(facts))


@dataclass(frozen=True)
class ReadBinding:
    scope: str
    fingerprint: tuple
    as_of: str

    @property
    def as_of_time(self) -> datetime:
        return datetime.fromisoformat(self.as_of)


def current_snapshot_time() -> datetime:
    return datetime.now().replace(microsecond=0)


def resolve_read_snapshot(token):
    try:
        return resolve_public_token(_SCOPE, token, message=messages.STALE, field="snapshot_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE) from exc


def read_snapshot_time(token) -> Tuple[datetime, Optional[ReadBinding]]:
    if token is None:
        return current_snapshot_time(), None
    payload = resolve_read_snapshot(token)
    return payload.as_of_time, payload


def page_integer(value: str, *, max_digits=6,
                 message="页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。") -> int:
    if not value.isascii() or not value.isdigit() or len(value) > max_digits:
        raise WorkbenchCommandRejected("invalid_input", message, 400)
    number = int(value)
    if number < 1:
        raise WorkbenchCommandRejected("invalid_input", message, 400)
    return number


def bind_read_snapshot(scope, fingerprint, token=None, *, as_of=None, binding=None, stale_message=messages.STALE):
    scope_value, facts = content_text(scope), fact_value(fingerprint)
    if token is not None:
        payload = resolve_read_snapshot(token) if binding is None else binding
        if payload.scope != scope_value:
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        if payload.fingerprint != facts:
            raise WorkbenchCommandRejected("snapshot_stale", stale_message)
        return {"snapshot_ref": token, "as_of": payload.as_of}
    if as_of is None:
        as_of = current_snapshot_time()
    if not isinstance(as_of, str):
        as_of = as_of.isoformat(timespec="seconds")
    issuer = PublicTokenIssuer(_SCOPE, group=facts, ttl_seconds=900)
    reference, _ = issuer.issue_bound_with_expiry(
        lambda canonical: ReadBinding(scope_value, canonical, as_of), key=(scope_value, as_of))
    return {"snapshot_ref": reference, "as_of": as_of}

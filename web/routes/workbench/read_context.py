"""Read bindings retain one canonical fact value and their original clock."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from flask import current_app

from core.errors import ValidationError
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from web.public_token_registry import PublicTokenIssuer, drop_public_token, resolve_public_token
from web.runtime_host import wall_clock

_SCOPE = "workbench-read-v1"


def fact_value(facts: Any) -> Tuple[str, str]:
    """Share one canonical fact string across read and write registries while keeping type separation."""
    return ("text", facts) if isinstance(facts, str) else ("canonical", content_text(facts))


@dataclass(frozen=True)
class ReadBinding:
    """``revisions`` are the source revisions the issuing read was admitted under, kept for a read that checks
    them before loading anything; a read without that precheck binds ``None``."""

    scope: str
    fingerprint: tuple
    as_of: str
    revisions: Optional[Mapping[str, int]]

    @property
    def as_of_time(self) -> datetime:
        return datetime.fromisoformat(self.as_of)


def current_snapshot_time() -> datetime:
    """一次读或预览请求的“现在”：入口只取这一次，再显式交给服务、快照绑定和出口元数据。"""
    return wall_clock(current_app)().replace(microsecond=0)


def _as_of_text(as_of) -> str:
    """One factory-local second clock text for bound and unbound read metadata."""
    return as_of if isinstance(as_of, str) else as_of.isoformat(timespec="seconds")


def unbound_snapshot(as_of):
    """Read metadata for documents with no rebindable snapshot (previews, receipts, assembled pages)."""
    return {"snapshot_ref": None, "as_of": _as_of_text(as_of)}


def resolve_read_snapshot(token):
    try:
        return resolve_public_token(_SCOPE, token, message=messages.STALE, field="snapshot_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE) from exc


def drop_read_snapshot(token: str) -> None:
    drop_public_token(_SCOPE, token)


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


def rebind_read_snapshot(scope, fingerprint, token, *, binding=None, stale_message=messages.STALE):
    """A later read of the snapshot ``token`` names keeps that snapshot's as_of and never reads the clock;
    ``binding`` is the token already resolved at the request entry."""
    payload = resolve_read_snapshot(token) if binding is None else binding
    if payload.scope != content_text(scope):
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
    if payload.fingerprint != fact_value(fingerprint):
        raise WorkbenchCommandRejected("snapshot_stale", stale_message)
    return {"snapshot_ref": token, "as_of": payload.as_of}


def bind_read_snapshot(scope, fingerprint, token=None, *, as_of, binding=None, stale_message=messages.STALE,
                       revisions=None):
    """Rebind ``token``, or issue a fresh snapshot at ``as_of``, the request's one reading of the clock."""
    if token is not None:
        return rebind_read_snapshot(scope, fingerprint, token, binding=binding, stale_message=stale_message)
    scope_value, facts, as_of_text = content_text(scope), fact_value(fingerprint), _as_of_text(as_of)
    issuer = PublicTokenIssuer(_SCOPE, group=facts, ttl_seconds=900)
    reference, _ = issuer.issue_bound_with_expiry(
        lambda canonical: ReadBinding(scope_value, canonical, as_of_text, revisions), key=(scope_value, as_of_text))
    return {"snapshot_ref": reference, "as_of": as_of_text}


def snapshot_binder(token):
    """The ``bind_snapshot(scope, state)`` callback a read service calls before projecting; the read's as_of is
    taken here, once, when the route builds the callback."""
    as_of, binding = read_snapshot_time(token)
    return lambda scope, state: bind_read_snapshot(scope, state, token, as_of=as_of, binding=binding)

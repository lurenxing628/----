"""Short-lived edit context, separate from permanent database entity references."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Tuple

from flask import g, request

from core.errors import ValidationError
from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.services.workbench import messages
from web.public_token_registry import PublicTokenIssuer, issue_public_token_with_expiry, resolve_public_token

from .read_context import fact_value

_SCOPE = "workbench-write-v1"
_TTL_SECONDS = 15 * 60


def command_body(subject: str) -> Dict[str, Any]:
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", f"提交的内容格式不正确，{subject}还没有保存。请刷新页面后重新填写。", 400)
    body = request.get_json()
    if not isinstance(body, dict) or set(body) != {"request_key", "write_token", "input"}:
        raise WorkbenchCommandRejected("invalid_input", f"提交的内容不完整或有多余项，{subject}还没有保存。请刷新页面后重新填写。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if not isinstance(body["write_token"], str) or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", f"本页数据已过期，{subject}还没有保存。请点「刷新资料」后重新填写。", 400)
    return body


@dataclass(frozen=True)
class WriteBinding:
    subject_ref: str
    actions: tuple
    snapshot: tuple


class WriteContextFactory:
    """A single context or a batch of subjects bound to one canonical snapshot."""

    def __call__(self, subject_ref: str, actions: Iterable[str], snapshot: Any) -> Dict[str, Any]:
        return self.for_snapshot(snapshot)(subject_ref, actions)

    def for_snapshot(self, snapshot: Any) -> Callable[[str, Iterable[str]], Dict[str, Any]]:
        """The actual page/operation owns this issuer; rows supply only small keys."""
        facts = fact_value(snapshot)
        issuer = PublicTokenIssuer(_SCOPE, group=facts, ttl_seconds=_TTL_SECONDS)

        def issue(subject_ref: str, actions: Iterable[str]) -> Dict[str, Any]:
            actions_value = tuple(sorted(set(actions)))
            token, expiry = issuer.issue_bound_with_expiry(
                lambda canonical: WriteBinding(subject_ref, actions_value, canonical), key=(subject_ref, actions_value))
            return {"write_token": token, "expires_at": datetime.fromtimestamp(expiry).isoformat(timespec="seconds"),
                    "capabilities": {action: True for action in actions_value}, "blocked_reasons": []}

        return issue


issue_write_context = WriteContextFactory()


def validate_write_context(token: str, subject_ref: str, action: str, current_snapshot: Any) -> None:
    """Call from the command guard, with facts re-read under its write transaction.

    Never refresh a token or repair facts here. A committed request is replayed by
    the command service before this guard, even if the original context has expired.
    """
    try:
        binding = resolve_public_token(_SCOPE, token, message=messages.STALE, field="write_token")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("stale_write", messages.STALE) from exc
    if binding.subject_ref != subject_ref or action not in binding.actions:
        raise WorkbenchCommandRejected("stale_write", "本页数据和这次操作对不上，还没有保存。请刷新页面后重新填写。")
    if binding.snapshot != fact_value(current_snapshot):
        raise WorkbenchCommandRejected("stale_write", messages.STALE)


def preview_write_context(preview_ref: str, expires_at: str, actions: Iterable[str]) -> Dict[str, Any]:
    """Reuse the retained preview's opaque token and expiry for confirmation.

    The preview registry owns the immutable document and permitted operation.
    Confirmation resolves that registry and rebuilds current business facts;
    issuing another token for the same preview adds no independent state.
    """
    return {"write_token": preview_ref, "expires_at": expires_at,
            "capabilities": {action: True for action in actions}, "blocked_reasons": []}


def validate_preview_confirmation(write_token: str, preview_ref: str) -> None:
    """Call after resolving the live preview and checking its operation."""
    if write_token != preview_ref:
        raise WorkbenchCommandRejected("stale_write", "预检结果和这次操作对不上，还没有保存。请重新预检。")


def retain_action_preview(scope: str, preview: AtomicActionPreview) -> Tuple[str, str]:
    """Retain the frozen preview itself; the same document reissues the same ref, which is also its write token."""
    token, expiry = issue_public_token_with_expiry(scope, preview, key=preview.document, ttl_seconds=_TTL_SECONDS)
    return token, datetime.fromtimestamp(expiry).isoformat(timespec="seconds")


def resolve_action_preview(scope: str, ref: str, operation: str, write_token: str, *,
                           expired_message: str, mismatch_message: str) -> AtomicActionPreview:
    """The retained preview of this operation, confirmed with its own ref as write token."""
    try:
        preview = resolve_public_token(scope, ref, message=expired_message, field="preview_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("stale_write", expired_message) from exc
    if preview.as_dict()["operation"] != operation:
        raise WorkbenchCommandRejected("stale_write", mismatch_message)
    validate_preview_confirmation(write_token, ref)
    return preview

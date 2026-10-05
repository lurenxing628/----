"""Short-lived edit context, separate from permanent database entity references."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.services.workbench import messages
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

_SCOPE = "workbench-write-v1"
_TTL_SECONDS = 15 * 60


def issue_write_context(subject_ref: str, actions: Iterable[str], snapshot: Any) -> Dict[str, Any]:
    """Issue only for production facts; callers select permitted domain actions.

    Snapshot is normalized authoritative state (including relevant revisions),
    not display labels, the current wall clock, or browser-provided saved state.
    None is for creation with no selected relation facts; business uniqueness
    still belongs to the domain write transaction, rather than a list snapshot.
    """
    if not isinstance(subject_ref, str) or not subject_ref:
        raise ValueError("缺少要编辑的对象。")
    allowed = list(actions) if not isinstance(actions, str) else []
    if not allowed or any(not isinstance(action, str) or not action for action in allowed):
        raise ValueError("未提供允许执行的操作。")
    binding = {"version": 1, "source": "production", "subject_ref": subject_ref,
               "actions": sorted(set(allowed)), "snapshot_hash": input_fingerprint(snapshot) if snapshot is not None else None}
    token, expiry = issue_public_token_with_expiry(_SCOPE, canonical_json(binding), ttl_seconds=_TTL_SECONDS)
    return {"write_token": token, "expires_at": datetime.fromtimestamp(expiry).isoformat(timespec="seconds"),
            "capabilities": {action: True for action in binding["actions"]}, "blocked_reasons": []}


def validate_write_context(token: str, subject_ref: str, action: str, current_snapshot: Any) -> None:
    """Call from the command guard, with facts re-read under its write transaction.

    Never refresh a token or repair facts here. A committed request is replayed by
    the command service before this guard, even if the original context has expired.
    """
    try:
        raw = resolve_public_token(_SCOPE, token, message=messages.STALE, field="write_token")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("stale_write", messages.STALE) from exc
    try:
        binding = json.loads(raw)
        valid = (isinstance(binding, dict) and binding.get("version") == 1 and binding.get("source") == "production"
                 and binding.get("subject_ref") == subject_ref and isinstance(binding.get("actions"), list)
                 and action in binding["actions"])
    except (ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("stale_write", messages.STALE) from exc
    if not valid:
        raise WorkbenchCommandRejected("stale_write", "本页数据和这次操作对不上，还没有保存。请刷新页面后重新填写。")
    expected = input_fingerprint(current_snapshot) if current_snapshot is not None else None
    if binding.get("snapshot_hash") != expected:
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

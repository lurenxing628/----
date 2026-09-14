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
    """
    if not isinstance(subject_ref, str) or not subject_ref:
        raise ValueError("缺少要编辑的对象。")
    allowed = list(actions) if not isinstance(actions, str) else []
    if not allowed or any(not isinstance(action, str) or not action for action in allowed):
        raise ValueError("未提供允许执行的操作。")
    binding = {"version": 1, "source": "production", "subject_ref": subject_ref,
               "actions": sorted(set(allowed)), "snapshot_hash": input_fingerprint(snapshot)}
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
    if binding.get("snapshot_hash") != input_fingerprint(current_snapshot):
        raise WorkbenchCommandRejected("stale_write", messages.STALE)

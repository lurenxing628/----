from __future__ import annotations

from typing import Any, Dict, Optional


def build_requested_history_resolution(
    *,
    requested_version: Optional[int],
    selected_history: Optional[Any],
    missing_message: Optional[str] = None,
) -> Dict[str, Any]:
    requested = int(requested_version) if requested_version is not None else None
    history_missing = requested is not None and selected_history is None
    message = None
    if history_missing:
        message = (
            str(missing_message or "").strip()
            or f"v{requested} 无对应排产历史，当前仅能展示仍然可用的页面信息。"
        )
    return {
        "requested_version": requested,
        "history_missing": bool(history_missing),
        "message": message,
    }


__all__ = ["build_requested_history_resolution"]

#!/usr/bin/env python3
"""Block high-risk shell commands before Codex runs them."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Dict

from authorization import AuthorizationError, command_risks, is_authorized


def _load_payload() -> Dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _command_from_payload(payload: Dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or tool_input.get("cmd")
        if isinstance(command, str):
            return command
    return ""


def _decision(decision: str, reason: str, command: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": (
                f"{reason}。\n命令：{command}"
            ),
        }
    }
    print(json.dumps(output, ensure_ascii=False))


def main() -> int:
    payload = _load_payload()
    command = _command_from_payload(payload).strip()
    if not command:
        return 0

    risks = command_risks(command)
    if not risks:
        return 0
    try:
        if is_authorized(payload, command, risks):
            _decision("allow", "已核对当前仓库、会话和具体操作的用户授权", command)
            return 0
    except (AuthorizationError, OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError, KeyError) as exc:
        detail = str(exc) if isinstance(exc, AuthorizationError) else type(exc).__name__
        _decision("deny", "授权核对失败：" + detail, command)
        return 0
    reasons = ["强推会改远端历史" if risk == "force_push" else risk for risk in risks]
    _decision("deny", "未找到覆盖这条命令的明确授权：" + "；".join(reasons), command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

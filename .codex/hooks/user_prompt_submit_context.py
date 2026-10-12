#!/usr/bin/env python3
"""Add APS project context to relevant user prompts."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any, Dict

from authorization import AuthorizationError, record_user_prompt

KEYWORDS = (
    "改",
    "实现",
    "优化",
    "审查",
    "review",
    "路线图",
    "提交",
    "commit",
    "push",
    "合并",
    "merge",
    "门禁",
    "quality",
    "修",
    "bug",
    "重构",
    "refactor",
    "文档",
    "说明书",
    "测试",
    "验证",
    "proof",
    "回归",
    "subagent",
    "agent",
    "继续",
)

CONTEXT = """APS 项目导航：遵守当前仓库 AGENTS.md。
项目注意事项位于 .codestable/attention.md，本轮已读且未变化时复用。
项目技能在 .limcode/skills/<技能名>/SKILL.md，按当前任务选择；只有介绍或选择完整流程时才读 .codestable/reference/system-overview.md。
验证命令与证明边界按需查 开发文档/README.md 的“质量治理入口”。本提醒只提供路径，不增加授权、初始化、修复或全量测试要求。"""


def _load_payload() -> Dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _should_add_context(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(keyword.lower() in lowered for keyword in KEYWORDS) or bool(re.search(r"\bcs-\w+", lowered))


def main() -> int:
    payload = _load_payload()
    prompt = payload.get("prompt", "")
    try:
        record_user_prompt(payload)
    except (AuthorizationError, OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError, KeyError) as exc:
        detail = str(exc) if isinstance(exc, AuthorizationError) else type(exc).__name__
        print(json.dumps({"decision": "block", "reason": "项目 hook 授权记录失败：" + detail}, ensure_ascii=False))
        return 0
    if not isinstance(prompt, str) or not _should_add_context(prompt):
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": CONTEXT,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from typing import Any, Optional

from web.public_token_registry import issue_public_token, resolve_public_token

_PLAN_CONTEXT_TOKEN_SCOPE = "scheduler-plan-context-v1"
_PLAN_CONTEXT_TOKEN_MESSAGE = "方案预览入口已失效，请刷新页面后重试。"


def plan_context_token(scenario_id: Optional[str]) -> str:
    text = str(scenario_id or "").strip()
    if not text:
        return ""
    return issue_public_token(_PLAN_CONTEXT_TOKEN_SCOPE, text)


def scenario_id_from_plan_context_token(token: Optional[str]) -> Optional[str]:
    text = str(token or "").strip()
    if not text:
        return None
    return resolve_public_token(
        _PLAN_CONTEXT_TOKEN_SCOPE,
        text,
        message=_PLAN_CONTEXT_TOKEN_MESSAGE,
        field="plan_context",
    )


def request_scenario_id_from_args(args: Any) -> Optional[str]:
    token = str(args.get("plan_context_token") or "").strip()
    if token:
        return scenario_id_from_plan_context_token(token)
    text = str(args.get("scenario_id") or "").strip()
    return text or None

"""方案上下文 token 的颁发与解析。

设计口径(深审 finding-11,2026-06-23 评估结案):
本应用为无登录、单租户、全无网单机离线交付,不存在用户/权限边界。
``plan_context_token`` 仅用于 URL 脱敏(避免真实 scenario_id 直接出现在链接里),
是进程内存、12 小时过期的随机串→scenario_id 映射,**不是访问权限控制**。
因此 ``request_scenario_id_from_args`` 在无 token 时回退裸 scenario_id 属 by-design,
不得据此当作越权漏洞删除;若未来引入登录态/多租户,需重新评估此回退。
"""

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
    # 无 token 时回退裸 scenario_id:仅 URL 脱敏、非权限门,无登录态下不构成越权(见模块 docstring)
    text = str(args.get("scenario_id") or "").strip()
    return text or None

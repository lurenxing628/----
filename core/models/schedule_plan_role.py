from __future__ import annotations

from typing import Optional

ROLE_ADOPTED = "adopted"
VALID_PLAN_ROLES = (ROLE_ADOPTED,)

SOURCE_SCHEDULE = "schedule"

# 计划“完整成功完成”的 schedule_result_status 集合（单一真相源）。partial/failed/preview 等不在内。
# 既用于判定“当前可执行正式方案”（派工、现场写入、默认复盘），也用于判定“可只读复盘的正式方案”——
# 两类判定在 result_status 维度共用同一口径，其余差异（当前/历史、是否被新版本取代）由各自的其他谓词处理。
# 此前该集合散落在 identity builder / 报表模板 / 复盘合同 / 资源派工四处，收口于此避免某次放开漏改一处造成入口间漂移。
COMPLETED_RESULT_STATUSES = frozenset({"success"})

PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "正式采用方案",
}


def _normalize_role(role: Optional[str]) -> str:
    text = str(role or "").strip()
    return text or ROLE_ADOPTED


def plan_role_label(role: Optional[str]) -> str:
    normalized = _normalize_role(role)
    return PLAN_ROLE_LABELS.get(normalized, "未知方案身份")


__all__ = [
    "COMPLETED_RESULT_STATUSES",
    "PLAN_ROLE_LABELS",
    "ROLE_ADOPTED",
    "SOURCE_SCHEDULE",
    "VALID_PLAN_ROLES",
    "plan_role_label",
]

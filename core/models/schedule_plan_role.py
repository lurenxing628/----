from __future__ import annotations

from typing import Optional

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"
ROLE_MIN_OVERDUE = "min_overdue"
ROLE_MIN_TARDINESS = "min_tardiness"
ROLE_MIN_CHANGEOVER = "min_changeover"
ROLE_MIN_WEIGHTED_TARDINESS = "min_weighted_tardiness"
VALID_PLAN_ROLES = (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    ROLE_MIN_OVERDUE,
    ROLE_MIN_TARDINESS,
    ROLE_MIN_CHANGEOVER,
    ROLE_MIN_WEIGHTED_TARDINESS,
)
PLAN_ROLE_ORDER = VALID_PLAN_ROLES

SOURCE_SCHEDULE = "schedule"
SOURCE_CANDIDATE_ROWS = "candidate_rows"
SOURCE_ADJUSTMENT_SCENARIO_ROWS = "adjustment_scenario_rows"

# 计划“完整成功完成”的 schedule_result_status 集合（单一真相源）。partial/failed/preview 等不在内。
# 既用于判定“当前可执行正式方案”（派工、现场写入、默认复盘），也用于判定“可只读复盘的正式方案”——
# 两类判定在 result_status 维度共用同一口径，其余差异（当前/历史、是否被新版本取代）由各自的其他谓词处理。
# 此前该集合散落在 identity builder / 报表模板 / 复盘合同 / 资源派工四处，收口于此避免某次放开漏改一处造成入口间漂移。
COMPLETED_RESULT_STATUSES = frozenset({"success"})

PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "正式采用方案",
    ROLE_BASELINE_BEST: "原算法代表方案",
    ROLE_CRITICAL_BEST: "重点工序优先代表方案",
    ROLE_MIN_OVERDUE: "交期优先代表方案",
    ROLE_MIN_TARDINESS: "拖期更轻代表方案",
    ROLE_MIN_CHANGEOVER: "切换更少代表方案",
    ROLE_MIN_WEIGHTED_TARDINESS: "加权拖期更轻代表方案",
}


def plan_role_order_sql(column: str) -> str:
    """Order fixed repository role columns by the same public role catalog."""
    cases = " ".join("WHEN '" + role + "' THEN " + str(index) for index, role in enumerate(PLAN_ROLE_ORDER, 1))
    return "CASE " + column + " " + cases + " ELSE 99 END"


def _normalize_role(role: Optional[str]) -> str:
    text = str(role or "").strip()
    return text or ROLE_ADOPTED


def is_comparison_source(source_table: str) -> bool:
    return source_table in (SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS)


def is_comparison_role(role: Optional[str]) -> bool:
    return role in VALID_PLAN_ROLES and role != ROLE_ADOPTED


def is_comparison_plan(
    *,
    requested_role: Optional[str] = None,
    selected_role: Optional[str] = None,
    role: Optional[str] = None,
    source_table: str,
    is_scenario_preview: bool = False,
) -> bool:
    if is_scenario_preview:
        return True
    return (
        is_comparison_role(requested_role or role)
        or is_comparison_role(selected_role)
        or is_comparison_source(source_table)
    )


def plan_role_label(role: Optional[str]) -> str:
    normalized = _normalize_role(role)
    return PLAN_ROLE_LABELS.get(normalized, "未知方案身份")


def plan_candidate_label(label: Optional[str], *, role: str, candidate_key: Optional[str] = None) -> str:
    if role in VALID_PLAN_ROLES[3:]:
        return plan_role_label(role)
    text = str(label or "").strip()
    key = str(candidate_key or "").strip()
    if text and text != key:
        return (
            text.replace("关键链候选", "重点工序优先方案")
            .replace("原算法候选", "原算法方案")
            .replace("重点工序优先方案最好", "重点工序优先代表方案")
            .replace("重点工序优先最好", "重点工序优先代表方案")
            .replace("关键链最好", "重点工序优先代表方案")
            .replace("原算法最好", "原算法代表方案")
            .replace("最终采用方案", "正式采用方案")
            .replace("最终采用", "正式采用方案")
        )
    if key == "baseline":
        return "原算法方案"
    if key.startswith("graph_w") and "_of_" in key:
        parts = key.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return plan_role_label(role)


__all__ = [
    "PLAN_ROLE_LABELS",
    "PLAN_ROLE_ORDER",
    "ROLE_ADOPTED",
    "ROLE_BASELINE_BEST",
    "ROLE_CRITICAL_BEST",
    "ROLE_MIN_OVERDUE",
    "ROLE_MIN_TARDINESS",
    "ROLE_MIN_CHANGEOVER",
    "ROLE_MIN_WEIGHTED_TARDINESS",
    "SOURCE_CANDIDATE_ROWS",
    "SOURCE_ADJUSTMENT_SCENARIO_ROWS",
    "SOURCE_SCHEDULE",
    "VALID_PLAN_ROLES",
    "is_comparison_plan",
    "is_comparison_role",
    "is_comparison_source",
    "plan_candidate_label",
    "plan_role_label",
    "plan_role_order_sql",
]

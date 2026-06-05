from __future__ import annotations

from typing import Optional

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"
VALID_PLAN_ROLES = (ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)

SOURCE_SCHEDULE = "schedule"
SOURCE_CANDIDATE_ROWS = "candidate_rows"
SOURCE_ADJUSTMENT_SCENARIO_ROWS = "adjustment_scenario_rows"

PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "正式采用方案",
    ROLE_BASELINE_BEST: "原算法代表方案",
    ROLE_CRITICAL_BEST: "重点工序优先代表方案",
}


def _normalize_role(role: Optional[str]) -> str:
    text = str(role or "").strip()
    return text or ROLE_ADOPTED


def is_comparison_source(source_table: Optional[str]) -> bool:
    return str(source_table or "").strip() in (SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS)


def is_comparison_role(role: Optional[str]) -> bool:
    return str(role or "").strip() in (ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)


def is_comparison_plan(
    *,
    requested_role: Optional[str] = None,
    selected_role: Optional[str] = None,
    role: Optional[str] = None,
    source_table: Optional[str] = None,
    is_scenario_preview: bool = False,
) -> bool:
    if bool(is_scenario_preview):
        return True
    return (
        is_comparison_role(requested_role or role)
        or is_comparison_role(selected_role)
        or is_comparison_source(source_table)
    )


def plan_role_label(role: Optional[str]) -> str:
    normalized = _normalize_role(role)
    return PLAN_ROLE_LABELS.get(normalized, "未知方案身份")


def plan_candidate_label(label: Optional[str], *, role: Optional[str] = None, candidate_key: Optional[str] = None) -> str:
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
    "ROLE_ADOPTED",
    "ROLE_BASELINE_BEST",
    "ROLE_CRITICAL_BEST",
    "SOURCE_CANDIDATE_ROWS",
    "SOURCE_ADJUSTMENT_SCENARIO_ROWS",
    "SOURCE_SCHEDULE",
    "VALID_PLAN_ROLES",
    "is_comparison_plan",
    "is_comparison_role",
    "is_comparison_source",
    "plan_candidate_label",
    "plan_role_label",
]

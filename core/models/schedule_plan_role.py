from __future__ import annotations

from typing import Optional

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"
VALID_PLAN_ROLES = (ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)

SOURCE_SCHEDULE = "schedule"
SOURCE_CANDIDATE_ROWS = "candidate_rows"

PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "最终采用",
    ROLE_BASELINE_BEST: "原算法最好",
    ROLE_CRITICAL_BEST: "重点工序优先方案最好",
}


def _normalize_role(role: Optional[str]) -> str:
    text = str(role or "").strip()
    return text or ROLE_ADOPTED


def is_comparison_source(source_table: Optional[str]) -> bool:
    return str(source_table or "").strip() == SOURCE_CANDIDATE_ROWS


def plan_role_label(role: Optional[str]) -> str:
    normalized = _normalize_role(role)
    return PLAN_ROLE_LABELS.get(normalized, normalized)


def plan_candidate_label(label: Optional[str], *, role: Optional[str] = None, candidate_key: Optional[str] = None) -> str:
    text = str(label or "").strip()
    key = str(candidate_key or "").strip()
    if text and text != key:
        return text.replace("关键链候选", "重点工序优先方案")
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
    "SOURCE_SCHEDULE",
    "VALID_PLAN_ROLES",
    "is_comparison_source",
    "plan_candidate_label",
    "plan_role_label",
]

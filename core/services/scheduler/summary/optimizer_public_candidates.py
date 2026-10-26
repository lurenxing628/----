from __future__ import annotations

from typing import Any, Dict, List

from core.services.scheduler.contracts.optimizer_public_safety import (
    public_int,
    safe_attempt_text,
    safe_metric_key,
)


def public_candidate_label(value: Any) -> str:
    raw_text = str(value).strip()
    if raw_text == "baseline":
        return "原算法方案"
    if raw_text.startswith("graph_w") and "_of_" in raw_text:
        parts = raw_text.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    text = safe_attempt_text(raw_text)
    if not text:
        return ""
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in text)
    has_ascii_letter = any(("a" <= ch.lower() <= "z") for ch in text)
    if "_" in text or (has_ascii_letter and not has_chinese):
        return ""
    return text


def project_best_score_schema(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        row = _project_score_schema_item(item)
        if row:
            out.append(row)
    return out


def _project_score_schema_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    key = safe_metric_key(item.get("key"))
    if not key:
        return {}
    row: Dict[str, Any] = {"key": key}
    index = public_int(item.get("index"))
    if index is not None:
        row["index"] = index
    label = public_candidate_label(item.get("label"))
    if label:
        row["label"] = label
    return row


def project_candidate_comparison(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    # This version is prepared by the shared optimizer's single public adapter.
    # Nullable score components and the run's process are already canonical.
    fields = (
        "enabled", "generation_policy_version", "primary_objective", "target_objectives",
        "planned_candidate_count", "completed_candidate_count", "failed_candidate_count",
        "skipped_candidate_count", "reused_candidate_count", "time_budget_reached", "run_time_budget_seconds",
        "skipped_candidate_labels", "selection_policy_version", "selection_reason_code", "selection", "unified_process",
    )
    out = {key: value[key] for key in fields if key in value}
    if "candidates" in value:
        out["candidates"] = [_project_business_candidate(candidate) for candidate in value["candidates"]]
    return out


def _project_business_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    fields = (
        "label", "kind", "status", "score", "metrics", "health", "graph_enabled", "critical_weight",
        "impact_weight", "downstream_weight", "elapsed_ms", "elapsed_seconds", "detail_saved", "roles",
        "generation_policy_version", "representative_objectives", "evaluations", "origin", "first_found_elapsed_ms",
        "search_evidence_ref", "adopted_dispatch_rule", "configured_dispatch_rule", "failure_reason",
        "reused_from_label", "input_certification",
    )
    return {key: candidate[key] for key in fields if key in candidate}


__all__ = [
    "project_best_score_schema",
    "project_candidate_comparison",
    "public_candidate_label",
]

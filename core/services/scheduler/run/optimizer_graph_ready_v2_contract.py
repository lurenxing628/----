from __future__ import annotations

from core.infrastructure.errors import ValidationError

GRAPH_READY_V2_FEATURE_FIELD = "graph_ready_v2_features"
GRAPH_READY_V2_FORMULA_FIELD = "graph_ready_v2_formula"
GRAPH_READY_CANDIDATE_POLICY_FIELD = "graph_ready_candidate_policy"

GRAPH_READY_V2_CONTRACT_FIELDS = {
    GRAPH_READY_V2_FEATURE_FIELD,
    GRAPH_READY_V2_FORMULA_FIELD,
    GRAPH_READY_CANDIDATE_POLICY_FIELD,
}

GRAPH_READY_V2_CONTRACT_REASONS = {
    "graph_ready_bad_v2_feature",
    "graph_ready_missing_v2_feature",
    "graph_ready_bad_v2_formula",
    "graph_ready_bad_candidate_policy",
    "graph_ready_v2_bad_due_date",
}


def graph_ready_validation_reason(exc: ValidationError) -> str:
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return ""
    return str(details.get("reason") or "")


def is_graph_ready_v2_contract_error(exc: ValidationError) -> bool:
    field = str(getattr(exc, "field", "") or "")
    if field in GRAPH_READY_V2_CONTRACT_FIELDS:
        return True
    return graph_ready_validation_reason(exc) in GRAPH_READY_V2_CONTRACT_REASONS


__all__ = [
    "GRAPH_READY_CANDIDATE_POLICY_FIELD",
    "GRAPH_READY_V2_CONTRACT_REASONS",
    "GRAPH_READY_V2_FEATURE_FIELD",
    "GRAPH_READY_V2_FORMULA_FIELD",
    "graph_ready_validation_reason",
    "is_graph_ready_v2_contract_error",
]

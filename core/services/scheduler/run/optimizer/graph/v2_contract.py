from __future__ import annotations

from core.errors import ValidationError

GRAPH_READY_V2_FEATURE_FIELD = "graph_ready_v2_features"
GRAPH_READY_V2_FORMULA_FIELD = "graph_ready_v2_formula"
GRAPH_READY_CANDIDATE_POLICY_FIELD = "graph_ready_candidate_policy"

GRAPH_READY_V2_CONTRACT_FIELDS = {
    GRAPH_READY_V2_FEATURE_FIELD,
    GRAPH_READY_V2_FORMULA_FIELD,
    GRAPH_READY_CANDIDATE_POLICY_FIELD,
}


def is_graph_ready_v2_contract_error(exc: ValidationError) -> bool:
    return exc.field in GRAPH_READY_V2_CONTRACT_FIELDS


__all__ = ["is_graph_ready_v2_contract_error"]

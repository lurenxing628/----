"""Persisted algorithm selection, independent of the user's viewing reference."""

from core.services.workbench.facts.candidate_values import corrupt

from .decision_selection_explanation import selection_explanation, unselected_explanation


def selection_basis(receipt, candidates):
    """The business-objective selection a run saved with its candidates.

    Queued, running and failed runs saved no candidates and no selection yet.
    """
    saved = (receipt or {}).get("selection")
    if saved is None:
        if candidates:
            corrupt()
        return _unselected_basis()
    if saved.get("selection_policy_version") != "business_objectives_v1":
        corrupt()
    by_ref = {row["candidate_ref"]: row for row in candidates}
    selected = saved["selected_candidate_ref"]
    if selected not in by_ref or any(ref is not None and ref not in by_ref for ref in saved["objective_winners"].values()):
        corrupt()
    result = dict(saved)
    result["explanation"] = selection_explanation(result)
    return result


def _unselected_basis():
    return {"generation_policy_version": None, "selection_policy_version": None, "primary_objective": None,
            "target_objectives": [], "selected_candidate_ref": None, "objective_winners": {},
            "objective_winner_reasons": {}, "objective_field_order": {}, "selected_score": [],
            "reason_code": None, "scoring_scope": None, "evidence_state": "unavailable",
            "explanation": unselected_explanation()}


def selection_roles(candidate, basis):
    roles = ["recommended"] if candidate["candidate_ref"] == basis["selected_candidate_ref"] else []
    return roles + [target for target in basis["target_objectives"]
                    if basis["objective_winners"][target] == candidate["candidate_ref"]]

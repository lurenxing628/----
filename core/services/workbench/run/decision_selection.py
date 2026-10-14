"""Persisted algorithm selection, independent of the user's viewing reference."""

from core.models.objective import best_score_schema
from core.services.workbench.facts.candidate_values import corrupt

from .decision_selection_explanation import selection_explanation


def selection_basis(receipt, candidates):
    saved = (receipt or {}).get("selection") or {}
    by_key = {row["artifact"].get("candidate_key"): row["candidate_ref"] for row in candidates}
    by_ref = {row["candidate_ref"]: row for row in candidates}

    def identity(current, legacy):
        value = saved.get(current) if current in saved else by_key.get(saved.get(legacy))
        if value is not None and value not in by_ref:
            corrupt()
        return value

    selected = identity("selected_candidate_ref", "selected_candidate_key")
    raw_best = identity("raw_score_best_candidate_ref", "raw_score_best_key")
    health_reference = identity("health_reference_candidate_ref", "baseline_best_key")
    artifact = by_ref[selected]["artifact"] if selected else {}
    objective = saved.get("objective_name") or artifact.get("objective_name") or artifact.get("objective")
    evidence = saved.get("decision_evidence")
    health_evidence = (artifact.get("health") or {}).get("decision_evidence")
    result = {"selected_candidate_ref": selected, "raw_score_best_candidate_ref": raw_best,
            "health_reference_candidate_ref": health_reference, "selection_policy": saved.get("selection_policy"),
            "selection_policy_version": saved.get("selection_policy_version"), "reason_code": saved.get("reason_code"),
            "objective_name": objective, "objective_field_order": saved.get("objective_field_order") or
            ([field["key"] for field in best_score_schema(objective)] if objective else []),
            "selected_score": saved.get("selected_score") or [],
            "overdue_tolerance_count": saved.get("overdue_tolerance_count"),
            "tardiness_tolerance_ratio": saved.get("tardiness_tolerance_ratio"),
            "raw_score_comparison": _raw_comparison(artifact, by_ref.get(raw_best), evidence),
            "health_comparison": {"reference_candidate_ref": health_reference, "health": artifact.get("health")},
            "selection_evidence_version": evidence.get("version") if evidence else None,
            "decision_evidence": evidence, "health_decision_evidence": health_evidence,
            "evidence_state": "complete" if selected and evidence and health_evidence else "partial" if selected else "unavailable"}
    result["explanation"] = selection_explanation(result, artifact, candidates)
    return result


def _raw_comparison(selected, reference, evidence=None):
    previous = reference["artifact"] if reference else {}
    if evidence:
        current, raw = evidence.get("selected") or {}, (evidence.get("anchors") or {}).get("raw_score_best") or {}
        return {"selected_score": current.get("score"), "reference_score": raw.get("score"),
                "overdue_count_delta": _difference(current, raw, "overdue_count"),
                "total_tardiness_hours_delta": _difference(current, raw, "total_tardiness_hours")}
    metrics, before = selected.get("metrics") or {}, previous.get("metrics") or {}
    return {"selected_score": selected.get("score"), "reference_score": previous.get("score"),
            "overdue_count_delta": _difference(metrics, before, "overdue_count"),
            "total_tardiness_hours_delta": _difference(metrics, before, "total_tardiness_hours")}


def _difference(selected, reference, key):
    after, before = selected.get(key), reference.get(key)
    return after - before if type(after) in (int, float) and type(before) in (int, float) else None


def selection_roles(candidate, basis):
    roles = []
    for field, role in (("selected_candidate_ref", "recommended"), ("raw_score_best_candidate_ref", "raw_score_best"),
                        ("health_reference_candidate_ref", "health_reference")):
        if candidate["candidate_ref"] == basis[field]:
            roles.append(role)
    if candidate["artifact"].get("kind") == "baseline":
        roles.append("algorithm_baseline")
    return roles

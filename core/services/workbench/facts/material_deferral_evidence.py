"""Pure archived material deferral evidence, independent of saved-source reads."""

from core.models.scheduler_history_parser import ResultSummaryParseResult


def archived_deferred_operation_evidence(parsed: ResultSummaryParseResult):
    """Read the pending identities a saved summary declared, from the caller's one parse of it."""
    return archived_deferred_payload_evidence(parsed.payload)


def archived_deferred_payload_evidence(payload):
    """Every adoption audit records ``deferred_operation_ids``; a stage policy without them is damaged evidence."""
    if not isinstance(payload, dict):
        return set(), []
    ids = payload.get("deferred_operation_ids")
    if ids is None:
        policy = payload.get("material_policy", {})
        stage = isinstance(policy, dict) and policy.get("material_strategy") == "stage" and policy.get("ready_check") is True
        return set(), ["deferred_operation_evidence_invalid"] if stage else []
    if type(ids) is not list or any(type(value) is not int or value <= 0 for value in ids):
        return set(), ["deferred_operation_evidence_invalid"]
    return set(ids), []

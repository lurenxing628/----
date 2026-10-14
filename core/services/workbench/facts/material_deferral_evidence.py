"""Pure archived material deferral evidence, independent of saved-source reads."""

from core.models.scheduler_history_parser import parse_result_summary_payload


def archived_deferred_operation_evidence(record):
    """Read declared pending identities without consulting replacement entities."""
    parsed = parse_result_summary_payload(record.get("summary"))
    payload = parsed.payload if not parsed.parse_failed else None
    return archived_deferred_payload_evidence(payload)


def archived_deferred_payload_evidence(payload):
    if not isinstance(payload, dict):
        return set(), []
    ids = payload.get("deferred_operation_ids")
    if ids is not None:
        if type(ids) is not list or any(type(value) is not int or value <= 0 for value in ids):
            return set(), ["deferred_operation_evidence_invalid"]
        return set(ids), []
    policy = payload.get("material_policy", {})
    if not isinstance(policy, dict) or policy.get("material_strategy") != "stage" or policy.get("ready_check") is not True:
        return set(), []
    return set(), ["deferred_operation_evidence_missing"]

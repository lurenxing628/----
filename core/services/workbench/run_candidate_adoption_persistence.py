"""Append-only official publish adapter; caller owns one immediate transaction."""

from core.models.workbench_command import WorkbenchCommandOutcome

from .official_plan_persistence import persist_official_plan_in_tx


def persist_adoption_in_tx(conn, evidence, intent, request_key, *, application_operator):
    audit = {"source": "workbench_candidate_adoption", "action": "adopt_run_candidate", "request_key": request_key,
             "candidate_ref": evidence.candidate_ref, "run_ref": evidence.run_ref,
             "proof": evidence.snapshot, "reason": intent["reason"],
             "declared_operator": intent["declared_operator"]}
    data = persist_official_plan_in_tx(conn, prepared=evidence.prepared, payload=evidence.payload,
                                      baseline=evidence.baseline, audit=audit,
                                      application_operator=application_operator)
    data["official_plan"]["source_run_ref"] = evidence.run_ref
    return WorkbenchCommandOutcome("committed", {"candidate_ref": evidence.candidate_ref,
        "run_ref": evidence.run_ref, **data})

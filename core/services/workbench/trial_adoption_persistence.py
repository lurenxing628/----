"""Scenario provenance wrapper; official plan insertion belongs to shared adapter."""

from core.models.workbench_command import WorkbenchCommandOutcome

from .official_plan_persistence import persist_official_plan_in_tx


def persist_trial_adoption_in_tx(conn, evidence, intent, request_key, *, application_operator):
    audit = {"source": "workbench_trial_adoption", "action": "adopt_trial_scenario",
             "request_key": request_key, "scenario_ref": evidence.scenario_ref, "draft_ref": evidence.draft_ref,
             "proof": evidence.snapshot, "reason": intent["reason"], "declared_operator": intent["declared_operator"]}
    result = persist_official_plan_in_tx(conn, prepared=evidence.prepared, payload=evidence.payload,
        baseline=evidence.baseline, audit=audit, application_operator=application_operator)
    result["official_plan"].update(source_scenario_ref=evidence.scenario_ref, source_draft_ref=evidence.draft_ref)
    return WorkbenchCommandOutcome("committed", {"scenario_ref": evidence.scenario_ref,
        "draft_ref": evidence.draft_ref, **result})

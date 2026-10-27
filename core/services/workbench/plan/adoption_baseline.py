"""Resolve a new official baseline from its recorded adoption, never version - 1."""

from core.infrastructure.read_evidence import verified_read
from core.models.content import content_text, same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.facts.adoption_baseline_sources import (
    candidate_source_evidence,
    decoded_baseline,
    trial_source_evidence,
)
from core.services.workbench.facts.adoption_baseline_values import (
    fail,
    require,
    stored,
)
from core.shared.strict_json import canonical_json
from data.repositories.workbench_command_repo import WorkbenchCommandRepository

from .adoption_baseline_identity import baseline_tasks, verify_arranged, verify_capture

_SOURCES = {"workbench_candidate_adoption": ("candidate_adoption", "scheduling.candidate.adopt", "candidate_ref", "run_ref"),
            "workbench_trial_adoption": ("trial_adoption", "trial.scenario.adopt", "scenario_ref", "draft_ref")}


def read_adoption_record(conn, *, plan_ref, version, history, receipt=None, receipt_result=None):
    """Verify one recorded adoption and its receipt, retaining its exact official version."""
    raw = history.get("result_summary") if history else None
    return verified_read(conn, ("adoption_record", plan_ref, version, raw), lambda: _read_adoption_record(
        conn, plan_ref, version, raw, receipt=receipt, receipt_result=receipt_result))


def _read_adoption_record(conn, plan_ref, version, raw, *, receipt, receipt_result):
    # Every official version is written by a candidate or trial adoption together with its audit.
    if raw is None:
        fail("adoption_evidence_missing", "ScheduleHistory")
    audit = stored(raw)
    source = audit.get("source")
    if type(source) is not str or source not in _SOURCES:
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_source")
    required = {"request_key", "baseline_ref", "baseline_version", "version", "proof", "row_count",
                "validation", "is_simulation", "reason", "declared_operator"}
    if not required <= set(audit):
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_fields")
    basis, _, context, parent = _SOURCES[source]
    if context not in audit or parent not in audit:
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_source_refs")
    require(all(type(audit[key]) is str for key in ("request_key", context, parent, "reason", "declared_operator")),
            "adoption.history_fields")
    require(audit["baseline_ref"] is None or type(audit["baseline_ref"]) is str, "adoption.baseline_ref_shape")
    require(audit["baseline_version"] is None or type(audit["baseline_version"]) is int,
            "adoption.baseline_version_shape")
    require(type(audit["version"]) is int and audit["version"] == version and audit["validation"] == "valid"
            and audit["is_simulation"] is False and type(audit["row_count"]) is int and audit["row_count"] > 0,
            "adoption.history_identity")
    _proof_fields(audit, basis)
    return basis, audit, _receipt(conn, plan_ref, version, audit, receipt=receipt, result=receipt_result)


def _proof_fields(audit, basis):
    require(type(audit["proof"]) is dict, "adoption.proof_shape")
    if audit["proof"].get("proof_version") != "content_refs_v1":
        fail("adoption_snapshot_invalid", "adoption.proof_version")
    names = ({"proof_version", "candidate_ref", "run_ref", "baseline_ref", "baseline_version"}
             if basis == "candidate_adoption" else
             {"proof_version", "scenario_ref", "draft_ref", "scenario_revision", "baseline_ref", "baseline_version"})
    missing = names - set(audit["proof"])
    if missing:
        fail("adoption_evidence_missing", "adoption.proof." + ",".join(sorted(missing)))


def _receipt(conn, plan_ref, version, audit, *, receipt, result):
    _, action, context, parent = _SOURCES[audit["source"]]
    repo = WorkbenchCommandRepository(conn)
    receipt = repo.get(audit["request_key"]) if receipt is None else receipt
    if receipt is None:
        fail("adoption_evidence_missing", "adoption.command_receipt")
    require(receipt["request_key"] == audit["request_key"], "adoption.receipt_request")
    result = stored(receipt["outcome_json"]) if result is None else result
    require(result.get("result") == "committed", "adoption.receipt_committed")
    require(type(result.get("data")) is dict, "adoption.receipt_data_shape")
    data = result["data"]
    require(type(data.get("official_plan")) is dict, "adoption.receipt_official_shape")
    official = data["official_plan"]
    expected = {"plan_ref": plan_ref, "version": version, "kind": "official", "baseline_ref": audit["baseline_ref"]}
    fields = ("source_run_ref",) if context == "candidate_ref" else ("source_scenario_ref", "source_draft_ref")
    require(expected.keys() <= official.keys() and set(fields) <= official.keys(), "adoption.receipt_official_fields")
    require({context, parent, "row_count"} <= data.keys(), "adoption.receipt_scope_fields")
    require(same({key: official[key] for key in expected}, expected), "adoption.receipt_official_identity")
    require((receipt["action"], receipt["context_ref"]) == (action, audit[context]), "adoption.receipt_source")
    intent = {"confirm": True, "reason": audit["reason"], "declared_operator": audit["declared_operator"]}
    require(repo.input_content(receipt) == content_text(intent), "adoption.receipt_intent")
    require(data[context] == audit[context] and data[parent] == audit[parent]
            and same(data["row_count"], audit["row_count"]), "adoption.receipt_scope")
    require(all(official[key] == audit[key[len("source_"):]] for key in fields), "adoption.receipt_provenance")
    return receipt


def read_adoption_source(conn, *, plan_ref, version, history, recorded=None, context=None):
    """Reuse full adoption proof only in the existing caller-owned read snapshot.

    The caller's exact version and history are part of this binding; an earlier
    official plan is always a separate source, even when its operations match.
    """
    if context is not None:
        return context.adoption_source(plan_ref, version, history, recorded=recorded)
    return load_adoption_source(conn, plan_ref=plan_ref, version=version, history=history, recorded=recorded)


def load_adoption_source(conn, *, plan_ref, version, history, recorded, context=None):
    recorded = read_adoption_record(conn, plan_ref=plan_ref, version=version, history=history) if recorded is None else recorded
    key = ("adoption_source", plan_ref, version, canonical_json(recorded[1]))
    return verified_read(conn, key, lambda: _read_adoption_source(
        conn, plan_ref=plan_ref, version=version, recorded=recorded, context=context,
    ))


def _read_adoption_source(conn, *, plan_ref, version, recorded, context):
    basis, audit, receipt = recorded
    prepared_candidate = prepared_trial = None
    if basis == "candidate_adoption":
        prepared_candidate = candidate_source_evidence(conn, audit)
        baseline, tables, arranged, generation, origin = (prepared_candidate[key] for key in
            ("baseline", "tables", "arranged", "generation_facts", "provenance"))
    else:
        evidence, prepared_trial = trial_source_evidence(conn, audit)
        baseline, tables, arranged, origin = evidence
        generation = None
    admission_proof = prepared_candidate["admission_proof"] if prepared_candidate is not None else None
    baseline = admission_proof.baseline if admission_proof is not None else decoded_baseline(baseline)
    require(same((baseline["plan_ref"], baseline["version"]), (audit["baseline_ref"], audit["baseline_version"])),
            "adoption.recorded_baseline")
    verify_capture(baseline, tables, admission_proof=admission_proof)
    require(len(arranged) == audit["row_count"], "adoption.complete_row_count")
    current = verify_arranged(conn, plan_ref, version, tables, arranged, context=context)
    return {"basis": basis, "audit": audit, "receipt": receipt, "baseline": baseline,
            "tables": tables, "arranged": arranged, "selected": current, "generation_facts": generation,
            "candidate_source": prepared_candidate, "trial_source": prepared_trial,
            "provenance": {"state": "available", "reason": None, **origin, "adopted_at": audit.get("adopted_at")}}


def read_adoption_baseline(conn, *, plan_ref, version, history, facts, point_annotator, context):
    """Return captured tasks and locator, or raise a classified evidence gap."""
    try:
        evidence = context.adoption_source(plan_ref, version, history, recorded=None)
        basis, audit, receipt = (evidence[key] for key in ("basis", "audit", "receipt"))
        facts["adoption"] = {"basis": basis, "audit": audit, "receipt": receipt}
        baseline, tables, current = evidence["baseline"], evidence["tables"], evidence["selected"]
        facts["provenance"] = evidence["provenance"]
        facts["adoption"].update(baseline=baseline, selected_rows=current)
        if baseline["version"] is None:
            fail("no_adoption_baseline", "recorded_empty_official_baseline")
        require(baseline["version"] < version and baseline["plan_ref"] != plan_ref, "adoption.baseline_precedes_selected")
        before = baseline_tasks(conn, baseline, tables, facts["adoption"], point_annotator=point_annotator, context=context)
        return {"basis": basis, "baseline": baseline, "tasks": before}
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        fail("adoption_snapshot_invalid", exc.code)
    except WorkbenchPlanReferenceError as exc:
        fail("adoption_reference_invalid", exc.code)

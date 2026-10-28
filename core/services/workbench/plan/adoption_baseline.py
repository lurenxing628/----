"""Resolve a new official baseline from its recorded adoption, never version - 1."""

from core.infrastructure.read_evidence import verified_read
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.facts.adoption_baseline_sources import (
    candidate_source_evidence,
    decoded_baseline,
    trial_source_evidence,
)
from core.services.workbench.facts.adoption_baseline_values import (
    fail,
    read_adoption_record,
    require,
)
from core.shared.strict_json import canonical_json

from .adoption_baseline_identity import baseline_tasks, verify_arranged, verify_capture


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

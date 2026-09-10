"""Resolve a new official baseline from its recorded adoption, never version - 1."""

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from data.repositories.workbench_command_repo import WorkbenchCommandRepository

from .plan_adoption_baseline_identity import baseline_tasks, verify_arranged, verify_capture
from .plan_adoption_baseline_sources import candidate_source, decoded_baseline, trial_source
from .plan_adoption_baseline_values import AdoptionBaselineUnavailable, fail, has_table, require, same, stored

_SOURCES = {"workbench_candidate_adoption": ("candidate_adoption", "scheduling.candidate.adopt", "candidate_ref", "run_ref"),
            "workbench_trial_adoption": ("trial_adoption", "trial.scenario.adopt", "scenario_ref", "draft_ref")}


def _audit(conn, plan_ref, version, history):
    raw = history.get("result_summary") if history else None
    if raw is None:
        return None
    audit = stored(raw)
    source = audit.get("source")
    if source not in _SOURCES:
        if "proof" in audit or "baseline_ref" in audit:
            fail("adoption_evidence_missing", "ScheduleHistory.adoption_source")
        return None
    required = {"request_key", "baseline_ref", "baseline_version", "version", "proof", "row_count",
                "validation", "is_simulation", "reason", "declared_operator"}
    if not required <= set(audit):
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_fields")
    basis, _, context, parent = _SOURCES[source]
    if context not in audit or parent not in audit:
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_source_refs")
    require(type(audit["version"]) is int and audit["version"] == version and audit["validation"] == "valid"
            and audit["is_simulation"] is False and type(audit["row_count"]) is int and audit["row_count"] > 0,
            "adoption.history_identity")
    _proof_fields(audit, basis)
    return basis, audit, _receipt(conn, plan_ref, version, audit)


def _proof_fields(audit, basis):
    require(type(audit["proof"]) is dict, "adoption.proof_shape")
    names = ({"candidate_ref", "run_ref", "facts_hash", "baseline_ref", "baseline_version", "baseline_hash", "candidate_hash"}
             if basis == "candidate_adoption" else
             {"scenario_ref", "draft_ref", "scenario_hash", "admission_hash", "execution_hash", "baseline_hash", "rows_hash"})
    missing = names - set(audit["proof"])
    if missing:
        fail("adoption_evidence_missing", "adoption.proof." + ",".join(sorted(missing)))


def _receipt(conn, plan_ref, version, audit):
    _, action, context, parent = _SOURCES[audit["source"]]
    if not has_table(conn, "WorkbenchCommandReceipts"):
        fail("adoption_evidence_missing", "WorkbenchCommandReceipts")
    receipt = WorkbenchCommandRepository(conn).get(audit["request_key"])
    if receipt is None:
        fail("adoption_evidence_missing", "adoption.command_receipt")
    result = stored(receipt["outcome_json"])
    require(result.get("result") == "committed", "adoption.receipt_committed")
    data = result["data"]
    official = data["official_plan"]
    expected = {"plan_ref": plan_ref, "version": version, "kind": "official", "baseline_ref": audit["baseline_ref"]}
    require(same({key: official[key] for key in expected}, expected), "adoption.receipt_official_identity")
    require((receipt["action"], receipt["context_ref"]) == (action, audit[context]), "adoption.receipt_source")
    intent = {"confirm": True, "reason": audit["reason"], "declared_operator": audit["declared_operator"]}
    require(receipt["input_hash"] == input_fingerprint(intent), "adoption.receipt_intent")
    require(data[context] == audit[context] and data[parent] == audit[parent]
            and same(data["row_count"], audit["row_count"]), "adoption.receipt_scope")
    fields = ("source_run_ref",) if context == "candidate_ref" else ("source_scenario_ref", "source_draft_ref")
    require(all(official[key] == audit[key[len("source_"):]] for key in fields), "adoption.receipt_provenance")
    return receipt


def read_adoption_baseline(conn, *, plan_ref, version, history, facts, point_annotator=None):
    """Return captured tasks and locator, or raise a classified evidence gap."""
    try:
        recorded = _audit(conn, plan_ref, version, history)
        if recorded is None:
            return None
        basis, audit, receipt = recorded
        facts["adoption"] = {"basis": basis, "audit": audit, "receipt": receipt}
        load = candidate_source if basis == "candidate_adoption" else trial_source
        baseline, tables, arranged = load(conn, audit)
        baseline = decoded_baseline(baseline)
        require(same((baseline["plan_ref"], baseline["version"]), (audit["baseline_ref"], audit["baseline_version"])),
                "adoption.recorded_baseline")
        verify_capture(baseline, tables)
        require(len(arranged) == audit["row_count"], "adoption.complete_row_count")
        current = verify_arranged(conn, plan_ref, version, tables, arranged)
        facts["adoption"].update(baseline=baseline, selected_rows=current)
        if baseline["version"] is None:
            fail("no_adoption_baseline", "recorded_empty_official_baseline")
        require(baseline["version"] < version and baseline["plan_ref"] != plan_ref, "adoption.baseline_precedes_selected")
        before = baseline_tasks(conn, baseline, tables, facts["adoption"], point_annotator=point_annotator)
        return {"basis": basis, "baseline": baseline, "tasks": before}
    except AdoptionBaselineUnavailable:
        raise
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        fail("adoption_snapshot_invalid", exc.code)
    except WorkbenchPlanReferenceError as exc:
        fail("adoption_reference_invalid", exc.code)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        fail("adoption_snapshot_invalid", "stored_evidence_shape:" + type(exc).__name__)

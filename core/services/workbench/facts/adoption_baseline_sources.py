"""Reuse RunBaseline verification and CQ's immutable saved-scenario contract."""

from dataclasses import dataclass
from typing import Tuple, Union

from core.infrastructure.read_evidence import verified_read
from core.infrastructure.schema_probe import table_exists
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline, unpack_blob
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import baseline_capture, candidate_origin
from core.services.workbench.facts.candidate_tasks import task_resource
from core.services.workbench.facts.candidate_values import gap
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository

from .adoption_baseline_values import fail, require

_TABLES = ("Schedule", "ScheduleHistory", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
           "WorkbenchEntityRefs", "BatchOperations", "Batches")


@dataclass(frozen=True)
class CandidateAdmissionProof:
    """One source's verified fields, separate from mutable baseline displays."""

    baseline: dict
    tables: dict


def _source_exists(conn, table, field, ref):
    if not WorkbenchPlanBaselineRepository(conn).source_exists(table, field, ref):
        fail("adoption_source_archived", table + "." + field)


def _tables_exist(conn, names):
    for name in names:
        if not table_exists(conn, name):
            fail("adoption_evidence_missing", name)


def _decode_rows(rows):
    require(type(rows) is list, "archived_table_rows")
    return [{key: unpack_blob(value) for key, value in row.items()} for row in rows]


def candidate_source_evidence(conn, audit):
    """Private complete proof and its parsed facts, including without reuse."""
    key = ("candidate_adoption_source", audit["candidate_ref"], audit["run_ref"])
    try:
        candidate, capture, evidence = verified_read(
            conn, key, lambda: _candidate_source(conn, audit))
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        fail(gap="candidate_source:" + exc.code)
    require(candidate["run_ref"] == audit["run_ref"], "candidate.run_ref")
    proof = audit["proof"]
    values = [("run_ref", audit["run_ref"]), ("candidate_ref", audit["candidate_ref"]),
              ("baseline_ref", capture["baseline"]["plan_ref"]),
              ("baseline_version", capture["baseline"]["version"])]
    if proof.get("proof_version") is None:
        values.append(("facts_hash", capture["facts_hash"]))
    else:
        require(proof.get("proof_version") == "content_refs_v1", "candidate.proof_version")
    for name, value in values:
        require(same(proof[name], value), "candidate.proof." + name)
    return evidence


def _candidate_source(conn, audit):
    candidate_ref, run_ref = audit["candidate_ref"], audit["run_ref"]
    _tables_exist(conn, ("WorkbenchRunJobs", "WorkbenchRunCandidates", "WorkbenchRunReceipts", "WorkbenchRunCandidateTasks"))
    _source_exists(conn, "WorkbenchRunJobs", "run_ref", run_ref)
    _source_exists(conn, "WorkbenchRunCandidates", "candidate_ref", candidate_ref)
    run, candidate, scope, tasks, capture, _ = load_adoption_candidate(conn, candidate_ref)
    facts = GenerationFacts(capture)
    tables = _candidate_tables(facts)
    AdmissionBaseline(capture, facts, scope)
    prepared = CandidateAdmissionProof(decoded_baseline(capture["baseline"]), tables)
    evidence = {"baseline": capture["baseline"], "tables": tables,
                "arranged": [row["payload"] for row in tasks], "generation_facts": facts,
                "provenance": candidate_origin(candidate, run, capture),
                "candidate": candidate, "tasks": tasks, "admission_proof": prepared}
    return candidate, capture, evidence


def _candidate_tables(facts):
    tables = {}
    for name in _TABLES:
        rows = facts.table(name)
        if rows is None:
            fail("adoption_evidence_missing", "run.facts." + name)
        tables[name] = _decode_rows(rows)
    return tables


def trial_source_evidence(conn, audit):
    """Return adoption evidence and its once-prepared scenario resources."""
    key = ("trial_adoption_source", audit["scenario_ref"], audit["draft_ref"])
    try:
        prepared, evidence = verified_read(
            conn, key, lambda: _trial_source(conn, audit))
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        fail(gap="trial_source:" + exc.code)
    head = prepared.source[1]
    admission, proof = head["admission"], audit["proof"]
    require(head["draft_ref"] == audit["draft_ref"], "trial.draft_ref")
    values = [("scenario_ref", audit["scenario_ref"]), ("draft_ref", audit["draft_ref"])]
    if proof.get("proof_version") is None:
        values.append(("admission_hash", head["admission_hash"]))
    else:
        require(proof.get("proof_version") == "content_refs_v1", "trial.proof_version")
        values.extend((("scenario_revision", head["scenario_revision"]),
                       ("baseline_ref", admission["baseline"]["plan_ref"]),
                       ("baseline_version", admission["baseline"]["version"])))
    for name, value in values:
        require(same(proof[name], value), "trial.proof." + name)
    return evidence, prepared


def _trial_source(conn, audit):
    scenario_ref, draft_ref = audit["scenario_ref"], audit["draft_ref"]
    _tables_exist(conn, ("WorkbenchTrialScenarios", "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialScenarioRows"))
    _source_exists(conn, "WorkbenchTrialScenarios", "scenario_ref", scenario_ref)
    _source_exists(conn, "WorkbenchTrialDrafts", "draft_ref", draft_ref)
    prepared = trial_adoption_facts(conn, scenario_ref)
    saved, head, rows = prepared.source
    admission = head["admission"]
    archive = admission["facts"]
    tables = {}
    for name in _TABLES:
        if name not in archive["tables"] or name not in archive["columns"]:
            fail("adoption_evidence_missing", "trial.facts." + name)
        values, columns = archive["tables"][name], archive["columns"][name]
        require(type(values) is list and type(columns) is list, "trial.table_shape")
        require(all(type(row) is dict and set(row) == set(columns) for row in values), "trial.table_columns")
        tables[name] = values
    _scenario_row_bindings(conn, saved)
    arranged = [{"op_id": row["original"]["operation"]["id"], **row["current"],
                 "start_time": row["current"]["start"], "end_time": row["current"]["end"]} for row in rows]
    origin = {"source_kind": "trial_adoption", "source_ref": scenario_ref, "source_label": saved["name"],
              "run_ref": None, "accepted_at": head["created_at"], "finished_at": saved["saved_at"],
              "algorithm": None, "baseline": baseline_capture(admission["baseline"], head["created_at"],
                                                                kind="trial_creation_official")}
    return prepared, (admission["baseline"], tables, arranged, origin)


def _scenario_row_bindings(conn, saved):
    tasks = {row["row_ref"]: row for row in saved["tasks"]}
    rows = WorkbenchPlanBaselineRepository(conn).list_scenario_row_bindings(saved["scenario_ref"])
    require(len(tasks) == len(rows), "trial.scenario_rows")
    for row_ref, task_ref, source_row_ref in rows:
        task = tasks.get(row_ref)
        require(task is not None and (task["task_ref"], task["source_row_ref"]) == (task_ref, source_row_ref),
                "trial.scenario_task_identity")


def decoded_baseline(baseline):
    require(type(baseline) is dict and set(baseline) == {"plan_ref", "version", "rows"}, "baseline_shape")
    return dict(baseline, rows=_decode_rows(baseline["rows"]))


class _TrialResourceFacts:
    """Read the trial's archived dictionaries through the resource projector."""

    def __init__(self, archive):
        tables = archive["tables"]
        self.tables = {name: {row[key]: row for row in tables.get(name, [])} for name, key in (
            ("Suppliers", "supplier_id"), ("Machines", "machine_id"), ("Operators", "operator_id"), ("OpTypes", "op_type_id"))}
        self.entity_refs = {(row["kind"], row["entity_key"]): row["ref"]
                            for row in tables.get("WorkbenchEntityRefs", []) if row["active"] == 1}

    def related(self, name, key, field, gaps):
        row = self.tables[name].get(key) if type(key) in (str, int) else None
        if row is None:
            gaps.append(gap(field, "source_missing"))
        return row or {}


@dataclass(frozen=True)
class TrialAdoptionFacts:
    source: Tuple[dict, dict, list]
    resources: Union[GenerationFacts, _TrialResourceFacts]
    assigned_resources: _TrialResourceFacts
    operations: dict


def prepare_trial_adoption_facts(source):
    """Preserve original supplier metadata and draft-time assigned resources."""
    _saved, head, rows = source
    admission = head["admission"]
    assigned = _TrialResourceFacts(admission["facts"])
    capture = admission["source"].get("capture")
    resources = GenerationFacts(capture) if capture is not None else assigned
    operations = {row["original"]["operation"]["id"]: row["original"]["operation"] for row in rows}
    return TrialAdoptionFacts(source, resources, assigned, operations)


def trial_adoption_facts(conn, scenario_ref):
    return verified_read(conn, ("trial_adoption_facts", scenario_ref),
        lambda: prepare_trial_adoption_facts(load_saved_scenario(conn, scenario_ref)))


def read_adoption_operation_facts(conn, evidence):
    """Read actual adopted assignments and supplier identity from their frozen sources."""
    audit = evidence["audit"]
    source_ref = audit["candidate_ref"] if evidence["basis"] == "candidate_adoption" else audit["scenario_ref"]
    key = ("adoption_operation_facts", evidence["basis"], audit["version"], source_ref)
    return verified_read(conn, key, lambda: _adoption_operation_facts(evidence))


def _adoption_operation_facts(evidence):
    if evidence["basis"] == "candidate_adoption":
        resources = evidence["generation_facts"]
        assigned_resources = resources
        operations = resources.tables["BatchOperations"]
    else:
        prepared = evidence["trial_source"]
        operations = prepared.operations
        resources, assigned_resources = prepared.resources, prepared.assigned_resources
    result = {}
    for row in evidence["arranged"]:
        op = operations.get(row["op_id"], {})
        gaps = []
        source = op.get("source")
        if source not in ("internal", "external"):
            gaps.append(gap("source", "not_recorded" if source is None else "invalid_stored_value"))
            source = None
        if "supplier_id" not in op:
            supplier = None
            gaps.append(gap("supplier", "not_recorded"))
        else:
            supplier = task_resource(resources, "supplier", op["supplier_id"], gaps)
        assigned = {kind: task_resource(assigned_resources, kind, row[kind + "_id"], gaps) for kind in ("machine", "operator")}
        assigned["supplier"] = supplier
        directory = [{"kind": kind, "ref": value["ref"], "business_code": op["supplier_id"] if kind == "supplier" else row[kind + "_id"],
                      "label": value["label"]} for kind, value in assigned.items() if value is not None and value["ref"] is not None]
        result[row["op_id"]] = {"source": source, **assigned, "resource_directory": directory, "data_gaps": gaps}
    return result

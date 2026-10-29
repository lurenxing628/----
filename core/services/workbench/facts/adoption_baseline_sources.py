"""Reuse RunBaseline verification and CQ's immutable saved-scenario contract."""

from dataclasses import dataclass
from typing import Tuple, Union

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.infrastructure.read_evidence import verified_read
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_archive import load_adoption_candidate_with_key
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline, unpack_blob
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import baseline_capture, candidate_origin
from core.services.workbench.facts.candidate_store import cache_get, cache_memo, cached_generation_facts
from core.services.workbench.facts.candidate_tasks import task_resource
from core.services.workbench.facts.candidate_values import gap
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from data.repositories.schedule_time_sql import parse_dt_for_sql
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository

from .adoption_baseline_values import fail, indexed, require

_TABLES = ("Schedule", "ScheduleHistory", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
           "WorkbenchEntityRefs", "BatchOperations", "Batches")
_CANDIDATE_SOURCE_CACHE = {}


def _precompute_arranged_times(arranged):
    result = {}
    for row in arranged:
        if type(row) is not dict:
            continue
        op_id, start, end = row.get("op_id"), row.get("start_time"), row.get("end_time")
        if type(op_id) is int and type(start) is str and type(end) is str:
            s_sql, e_sql = parse_dt_for_sql(start), parse_dt_for_sql(end)
            if s_sql is not None and e_sql is not None:
                result[op_id] = (s_sql.replace(" ", "T"), e_sql.replace(" ", "T"))
    return result


def _precompute_indexed_tables(tables):
    source_refs = tables["WorkbenchPlanSourceRefs"]
    batch_ops = tables["BatchOperations"]
    batches = tables["Batches"]
    return {
        "BatchOperations": indexed(batch_ops, "id"),
        "Batches": indexed(batches, "batch_id"),
        "operation_sources": indexed(
            [row for row in source_refs if type(row) is dict and row.get("kind") == "operation" and row.get("active") == 1],
            "source_key",
        ),
        "source_refs_id": id(source_refs),
        "batch_operations_id": id(batch_ops),
        "batches_id": id(batches),
    }


@dataclass(frozen=True)
class CandidateAdmissionProof:
    """One source's verified fields, separate from mutable baseline displays."""

    baseline: dict
    tables: dict


def _source_exists(conn, table, field, ref):
    if not WorkbenchPlanBaselineRepository(conn).source_exists(table, field, ref):
        fail("adoption_source_archived", table + "." + field)


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
    # The recorded proof's version and field set were already checked with the audit.
    proof = audit["proof"]
    values = [("run_ref", audit["run_ref"]), ("candidate_ref", audit["candidate_ref"]),
              ("baseline_ref", capture["baseline"]["plan_ref"]),
              ("baseline_version", capture["baseline"]["version"])]
    for name, value in values:
        require(same(proof[name], value), "candidate.proof." + name)
    return evidence


def _candidate_source(conn, audit):
    candidate_ref, run_ref = audit["candidate_ref"], audit["run_ref"]
    _source_exists(conn, "WorkbenchRunJobs", "run_ref", run_ref)
    _source_exists(conn, "WorkbenchRunCandidates", "candidate_ref", candidate_ref)
    run, candidate, scope, tasks, capture, _, facts, raw_key = load_adoption_candidate_with_key(
        conn, candidate_ref, copy_on_read=False
    )
    cached = cache_get(_CANDIDATE_SOURCE_CACHE, raw_key) if raw_key is not None else None
    if cached is not None:
        tables, prepared, arranged, arranged_times, indexed_tables = cached
    else:
        tables = _candidate_tables(facts)
        AdmissionBaseline(capture, facts, scope)
        prepared = CandidateAdmissionProof(decoded_baseline(capture["baseline"]), tables)
        arranged = [row["payload"] for row in tasks]
        arranged_times = _precompute_arranged_times(arranged)
        indexed_tables = _precompute_indexed_tables(tables)
        if raw_key is not None:
            cache_memo(_CANDIDATE_SOURCE_CACHE, raw_key, (tables, prepared, arranged, arranged_times, indexed_tables))
    provenance = candidate_origin(candidate, run, capture)
    evidence = {"baseline": capture["baseline"], "tables": tables,
                "arranged": arranged, "arranged_times": arranged_times, "indexed_tables": indexed_tables,
                "generation_facts": facts,
                "provenance": provenance,
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
    values = [("scenario_ref", audit["scenario_ref"]), ("draft_ref", audit["draft_ref"]),
              ("scenario_revision", head["scenario_revision"]),
              ("baseline_ref", admission["baseline"]["plan_ref"]),
              ("baseline_version", admission["baseline"]["version"])]
    for name, value in values:
        require(same(proof[name], value), "trial.proof." + name)
    return evidence, prepared


def _trial_source(conn, audit):
    scenario_ref, draft_ref = audit["scenario_ref"], audit["draft_ref"]
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
    arranged_times = _precompute_arranged_times(arranged)
    indexed_tables = _precompute_indexed_tables(tables)
    origin = {"source_kind": "trial_adoption", "source_ref": scenario_ref, "source_label": saved["name"],
              "run_ref": None, "accepted_at": head["created_at"], "finished_at": saved["saved_at"],
              "algorithm": None, "baseline": baseline_capture(admission["baseline"], head["created_at"],
                                                                kind="trial_creation_official")}
    return prepared, (admission["baseline"], tables, arranged, origin, arranged_times, indexed_tables)


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
    resources = assigned if capture is None else cached_generation_facts(capture)
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
        if type(source) is not str or source not in OPERATION_SOURCES:
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

"""Reuse RunBaseline verification and CQ's immutable saved-scenario contract."""

from core.infrastructure.read_evidence import verified_read
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline, _blob
from core.services.workbench.facts.candidate_facts import GenerationFacts, _table
from core.services.workbench.facts.candidate_projection import baseline_capture, candidate_origin
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import _resource
from core.services.workbench.facts.candidate_values import gap
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository

from .adoption_baseline_values import fail, has_table, require, same

_TABLES = ("Schedule", "ScheduleHistory", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
           "WorkbenchEntityRefs", "BatchOperations", "Batches")


def _source_exists(conn, table, field, ref):
    if not has_table(conn, table):
        fail("adoption_evidence_missing", table)
    if not WorkbenchPlanBaselineRepository(conn).source_exists(table, field, ref):
        fail("adoption_source_archived", table + "." + field)


def _tables_exist(conn, names):
    for name in names:
        if not has_table(conn, name):
            fail("adoption_evidence_missing", name)


def _decode_rows(rows):
    require(type(rows) is list, "archived_table_rows")
    return [{key: _blob(value) for key, value in row.items()} for row in rows]


def candidate_source(conn, audit):
    return candidate_source_evidence(conn, audit)[:3]


def candidate_source_evidence(conn, audit):
    """Private complete proof and its parsed facts, including without reuse."""
    key = ("candidate_adoption_source", audit["candidate_ref"], audit["run_ref"])
    candidate, capture, evidence = verified_read(
        conn, key, lambda: _candidate_source(conn, audit))
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
    candidate, scope, tasks, capture = load_adoption_candidate(conn, candidate_ref)
    store = CandidateStore(conn)
    run = store.run(run_ref)
    facts = GenerationFacts(capture)
    # GenerationFacts parses the original immutable source and validates its shape.
    # Keep the adoption reader's original byte limit without parsing it again.
    if len(capture["facts_text"].encode("utf-8")) > 64 * 1024 * 1024:
        raise WorkbenchCommandRejected("query_too_large", "完整采用凭据超过 64 MB 上限。请缩小查询范围后重试。", 413)
    archive = facts.archive
    tables = _candidate_tables(archive)
    AdmissionBaseline(capture, facts, scope, run["accepted_at"])
    evidence = capture["baseline"], tables, [row["payload"] for row in tasks], facts, candidate_origin(candidate, run, capture)
    return candidate, capture, evidence


def _candidate_tables(archive):
    tables = {}
    for name in _TABLES:
        rows = _table(archive, name)
        if rows is None:
            fail("adoption_evidence_missing", "run.facts." + name)
        tables[name] = _decode_rows(rows)
    return tables


def trial_source(conn, audit):
    return trial_source_evidence(conn, audit)[:3]


def trial_source_evidence(conn, audit):
    key = ("trial_adoption_source", audit["scenario_ref"], audit["draft_ref"])
    head, evidence = verified_read(
        conn, key, lambda: _trial_source(conn, audit))
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
    return evidence


def _trial_source(conn, audit):
    scenario_ref, draft_ref = audit["scenario_ref"], audit["draft_ref"]
    _tables_exist(conn, ("WorkbenchTrialScenarios", "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialScenarioRows"))
    _source_exists(conn, "WorkbenchTrialScenarios", "scenario_ref", scenario_ref)
    _source_exists(conn, "WorkbenchTrialDrafts", "draft_ref", draft_ref)
    saved, head, rows = load_saved_scenario(conn, scenario_ref)
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
    return head, (admission["baseline"], tables, arranged, origin)


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
            ("Suppliers", "supplier_id"), ("Machines", "machine_id"), ("Operators", "operator_id"))}
        self.entity_refs = {(row["kind"], row["entity_key"]): row["ref"]
                            for row in tables.get("WorkbenchEntityRefs", []) if row["active"] == 1}

    def related(self, name, key, field, gaps):
        row = self.tables[name].get(key) if type(key) in (str, int) else None
        if row is None:
            gaps.append(gap(field, "source_missing"))
        return row or {}


def read_adoption_operation_facts(conn, evidence):
    """Read actual adopted assignments and supplier identity from their frozen sources."""
    audit = evidence["audit"]
    source_ref = audit["candidate_ref"] if evidence["basis"] == "candidate_adoption" else audit["scenario_ref"]
    key = ("adoption_operation_facts", evidence["basis"], audit["version"], source_ref)
    return verified_read(conn, key, lambda: _adoption_operation_facts(conn, evidence))


def _adoption_operation_facts(conn, evidence):
    if evidence["basis"] == "candidate_adoption":
        resources = evidence["generation_facts"]
        assigned_resources = resources
        operations = resources.tables["BatchOperations"]
    else:
        _, head, rows = load_saved_scenario(conn, evidence["audit"]["scenario_ref"])
        operations = {row["original"]["operation"]["id"]: row["original"]["operation"] for row in rows}
        admission = head["admission"]
        capture = admission["source"].get("capture")
        resources = GenerationFacts(capture) if capture is not None else _TrialResourceFacts(admission["facts"])
        assigned_resources = _TrialResourceFacts(admission["facts"])
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
            supplier = _resource(resources, "supplier", op["supplier_id"], gaps)
        assigned = {kind: _resource(assigned_resources, kind, row[kind + "_id"], gaps) for kind in ("machine", "operator")}
        assigned["supplier"] = supplier
        directory = [{"kind": kind, "ref": value["ref"], "business_code": op["supplier_id"] if kind == "supplier" else row[kind + "_id"],
                      "label": value["label"]} for kind, value in assigned.items() if value is not None and value["ref"] is not None]
        result[row["op_id"]] = {"source": source, **assigned, "resource_directory": directory, "data_gaps": gaps}
    return result

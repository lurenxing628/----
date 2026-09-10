"""Reuse RunBaseline verification and CQ's immutable saved-scenario contract."""

from core.models.workbench_command import input_fingerprint
from core.models.workbench_trial_codec import fingerprint

from .plan_adoption_baseline_values import fail, has_table, require, same, stored
from .run_candidate_adoption_storage import load_adoption_candidate
from .run_candidate_baseline import AdmissionBaseline, _blob
from .run_candidate_facts import GenerationFacts, _table
from .run_candidate_storage import CandidateStore
from .trial_adoption_storage import load_saved_scenario

_TABLES = ("Schedule", "ScheduleHistory", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
           "WorkbenchEntityRefs", "BatchOperations", "Batches")


def _source_exists(conn, table, field, ref):
    if not has_table(conn, table):
        fail("adoption_evidence_missing", table)
    if conn.execute("SELECT 1 FROM " + table + " WHERE " + field + "=?", (ref,)).fetchone() is None:
        fail("adoption_source_archived", table + "." + field)


def _tables_exist(conn, names):
    for name in names:
        if not has_table(conn, name):
            fail("adoption_evidence_missing", name)


def _decode_rows(rows):
    require(type(rows) is list, "archived_table_rows")
    return [{key: _blob(value) for key, value in row.items()} for row in rows]


def candidate_source(conn, audit):
    _tables_exist(conn, ("WorkbenchRunJobs", "WorkbenchRunCandidates", "WorkbenchRunReceipts", "WorkbenchRunCandidateTasks"))
    _source_exists(conn, "WorkbenchRunJobs", "run_ref", audit["run_ref"])
    _source_exists(conn, "WorkbenchRunCandidates", "candidate_ref", audit["candidate_ref"])
    candidate, scope, tasks, capture = load_adoption_candidate(conn, audit["candidate_ref"])
    store = CandidateStore(conn)
    run = store.run(audit["run_ref"])
    facts = GenerationFacts(capture)
    archive = stored(capture["facts_text"])
    tables = _candidate_tables(archive)
    AdmissionBaseline(capture, facts, scope, run["accepted_at"])
    require(candidate["run_ref"] == audit["run_ref"], "candidate.run_ref")
    proof = audit["proof"]
    for key, value in (("run_ref", audit["run_ref"]), ("candidate_ref", audit["candidate_ref"]),
                       ("facts_hash", capture["facts_hash"]), ("baseline_ref", capture["baseline"]["plan_ref"]),
                       ("baseline_version", capture["baseline"]["version"]),
                       ("baseline_hash", input_fingerprint(capture["baseline"])),
                       ("candidate_hash", input_fingerprint({"candidate": candidate, "tasks": tasks, "scope": scope}))):
        require(same(proof[key], value), "candidate.proof." + key)
    return capture["baseline"], tables, [row["payload"] for row in tasks]


def _candidate_tables(archive):
    tables = {}
    for name in _TABLES:
        rows = _table(archive, name)
        if rows is None:
            fail("adoption_evidence_missing", "run.facts." + name)
        tables[name] = _decode_rows(rows)
    return tables


def trial_source(conn, audit):
    _tables_exist(conn, ("WorkbenchTrialScenarios", "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialScenarioRows"))
    _source_exists(conn, "WorkbenchTrialScenarios", "scenario_ref", audit["scenario_ref"])
    _source_exists(conn, "WorkbenchTrialDrafts", "draft_ref", audit["draft_ref"])
    saved, head, rows = load_saved_scenario(conn, audit["scenario_ref"])
    admission, proof = head["admission"], audit["proof"]
    require(head["draft_ref"] == audit["draft_ref"], "trial.draft_ref")
    for key, value in (("scenario_ref", audit["scenario_ref"]), ("draft_ref", audit["draft_ref"]),
                       ("scenario_hash", fingerprint(saved)), ("admission_hash", head["admission_hash"]),
                       ("execution_hash", fingerprint(admission["execution"])),
                       ("baseline_hash", fingerprint(admission["baseline"])), ("rows_hash", fingerprint(rows))):
        require(same(proof[key], value), "trial.proof." + key)
    archive = admission["facts"]
    require(fingerprint(archive) == admission["facts_hash"], "trial.facts_hash")
    # The adopt-time facts_hash includes identities created when saving the draft;
    # it is not the earlier admission hash. Baseline/execution have explicit hashes.
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
    return admission["baseline"], tables, arranged


def _scenario_row_bindings(conn, saved):
    tasks = {row["row_ref"]: row for row in saved["tasks"]}
    rows = list(conn.execute("SELECT row_ref,task_ref,source_row_ref FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?",
                             (saved["scenario_ref"],)))
    require(len(tasks) == len(rows), "trial.scenario_rows")
    for row_ref, task_ref, source_row_ref in rows:
        task = tasks.get(row_ref)
        require(task is not None and (task["task_ref"], task["source_row_ref"]) == (task_ref, source_row_ref),
                "trial.scenario_task_identity")


def decoded_baseline(baseline):
    require(type(baseline) is dict and set(baseline) == {"plan_ref", "version", "rows"}, "baseline_shape")
    return dict(baseline, rows=_decode_rows(baseline["rows"]))

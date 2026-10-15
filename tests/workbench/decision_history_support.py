"""P7 histories in a controlled SQLite file, reusing the existing one-operation case."""

import json
from contextlib import contextmanager
from copy import deepcopy

from flask import Blueprint, Flask, g

from core.infrastructure.migrations.v41 import _candidate_provider, _prepare_candidate, _read_packet
from core.models.workbench_command import WorkbenchCommandOutcome, canonical_json
from core.models.workbench_run_job import new_run_ref
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
from core.services.workbench.facts.decision_read_model import build_decision_read_models, prepare_admission_read_models
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.plan_catalog_support import history as legacy_history
from tests.workbench.run_candidate_adoption_support import INTENT as CANDIDATE_INTENT
from tests.workbench.run_candidate_adoption_support import preview as candidate_preview
from tests.workbench.run_candidate_adoption_support import service as candidate_service
from tests.workbench.run_candidate_support import compute, connect
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.trial_adoption_support import INTENT as TRIAL_INTENT
from tests.workbench.trial_adoption_support import preview as trial_preview
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as trial_adopter
from tests.workbench.trial_support import trial_case

BASE = "/api/workbench/v1/scheduling/decision-history"


@contextmanager
def four_source_case(directory):
    """Compute the existing small fixture once; every later history point reuses its archive."""
    generator = trial_case.__wrapped__(directory)
    case = next(generator)
    try:
        # This history contract retains a real legacy configuration row while
        # the current scheduler leaves its retired search policy unused.
        case.conn.execute("INSERT OR IGNORE INTO ScheduleConfig(config_key,config_value) "
                          "VALUES ('graph_candidate_weight_count','3')")
        case.conn.commit()
        run_ref, candidates = compute(case)
        selected = json.loads(case.conn.execute(
            "SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()[0])
        candidate_ref = selected["selection"]["selected_candidate_ref"]
        adopted = candidate_service(case.conn).adopt(candidate_ref, candidate_preview(case, candidate_ref),
            "history-candidate-adopt-0001", CANDIDATE_INTENT)
        official = adopted["data"]["official_plan"]
        original_periods = case.conn.execute("SELECT periods_json FROM WorkbenchCalendarDefaults WHERE singleton=1").fetchone()[0]
        case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json=? WHERE singleton=1",
                          ('[{"start":"08:00","end":"12:00","day_offset":0}]',))
        case.conn.commit()
        saved = saved_scenario(case, {"base": {"candidate_ref": candidate_ref}}, changed=False, suffix="history-0001")
        trial = trial_adopter(case.conn).adopt(saved["scenario_ref"], trial_preview(case, saved),
            "history-trial-adopt-0001", TRIAL_INTENT)
        case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json=? WHERE singleton=1", (original_periods,))
        case.conn.commit()
        case.history_refs = {"run_ref": run_ref, "candidate_ref": candidate_ref,
            "candidate_refs": candidates, "candidate_receipt_ref": adopted["receipt_ref"],
            "candidate_plan_ref": official["plan_ref"], "candidate_version": official["version"],
            "scenario_ref": saved["scenario_ref"], "draft_ref": saved["draft_ref"],
            "trial_receipt_ref": trial["receipt_ref"],
            "trial_plan_ref": trial["data"]["official_plan"]["plan_ref"],
            "trial_version": trial["data"]["official_plan"]["version"]}
        append_candidate_adoption(case)
        legacy_version = case.history_refs["second_candidate_version"] + 1
        legacy_summary = dict(selected["summary"], version=legacy_version, is_simulation=False)
        legacy_history(case.conn, legacy_version, summary=canonical_json(legacy_summary), op_id=case.op_id,
                       time="2026-09-12T08:00:00")
        case.conn.commit()
        case.history_refs.update(legacy_version=legacy_version, legacy_plan_ref=case.plan_ref(legacy_version),
            legacy_history_id=case.conn.execute("SELECT id FROM ScheduleHistory WHERE version=?", (legacy_version,)).fetchone()[0])
        yield case
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def append_candidate_adoption(case):
    """Historical second event for one run, without replaying adoption against a changed baseline."""
    refs, conn = case.history_refs, case.conn
    original = conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE receipt_ref=?",
                            (refs["candidate_receipt_ref"],)).fetchone()
    version = refs["trial_version"] + 1
    summary = json.loads(conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?",
                                     (refs["candidate_version"],)).fetchone()[0])
    request_key, receipt_ref = "history-candidate-adopt-0002", new_run_ref()[:32]
    summary.update(version=version, request_key=request_key, adopted_at="2026-09-11T10:00:00")
    conn.execute("INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status,result_summary,schedule_time) "
                 "VALUES (?,'manual',1,1,'success',?,'2026-09-11T10:00:00')", (version, canonical_json(summary)))
    conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time,lock_status) "
                 "SELECT ?,op_id,machine_id,operator_id,start_time,end_time,lock_status FROM Schedule WHERE version=?",
                 (version, refs["candidate_version"]))
    plan_ref = case.plan_ref(version)
    outcome = json.loads(original["outcome_json"])
    outcome["data"]["official_plan"].update(version=version, plan_ref=plan_ref)
    WorkbenchCommandRepository(conn).insert(request_key=request_key, receipt_ref=receipt_ref,
        action=original["action"], context_ref=original["context_ref"], input_hash=original["input_hash"],
        outcome=WorkbenchCommandOutcome(**outcome))
    conn.commit()
    refs.update(second_candidate_receipt_ref=receipt_ref, second_candidate_plan_ref=plan_ref,
                second_candidate_version=version)


def copy_case(source, directory):
    path = directory / "history.sqlite"
    conn = connect(path)
    source.conn.backup(conn)
    case = JobCase(conn)
    case.path, case.op_id = path, source.op_id
    case.history_refs = deepcopy(source.history_refs)
    case.app = Flask("decision-history-tests")
    return case


def clone_run(case, accepted, *, change_input=None, change_artifact=None, change_facts=None, change_receipt=None):
    """Append a complete historical archive; copied production facts keep their original identity."""
    conn, original_ref = case.conn, case.history_refs["run_ref"]
    source = dict(conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (original_ref,)).fetchone())
    ref, key = new_run_ref(), new_run_ref()
    source.update(run_ref=ref, request_key=key, input_ref="history-reuse-" + ref, accepted_at=accepted,
                  started_at=accepted, finished_at=accepted, executor_ref=new_run_ref())
    if change_input is not None:
        value = json.loads(source["normalized_input_json"])
        change_input(value)
        source["normalized_input_json"] = canonical_json(value)
    if change_facts is not None:
        value = json.loads(source["facts_json"])
        change_facts(value)
        source["facts_json"] = canonical_json(value)
    columns = tuple(source)
    conn.execute("INSERT INTO WorkbenchRunJobs(" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")",
                 tuple(source.values()))
    candidates = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence", (original_ref,))]
    mapping = {row["candidate_ref"]: new_run_ref() for row in candidates}

    def remap(value):
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        return mapping.get(value, ref if value == original_ref else value) if isinstance(value, str) else value

    for row in candidates:
        artifact = remap(json.loads(row["artifact_json"]))
        if change_artifact is not None:
            change_artifact(artifact)
        new_candidate = mapping[row["candidate_ref"]]
        conn.execute("INSERT INTO WorkbenchRunCandidates VALUES (?,?,?,?,?,?,?)",
            (new_candidate, ref, row["candidate_key"], row["sequence"], row["status"], row["task_count"], canonical_json(artifact)))
        for task in conn.execute("SELECT * FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (row["candidate_ref"],)):
            conn.execute("INSERT INTO WorkbenchRunCandidateTasks VALUES (?,?,?,?,?)",
                (new_run_ref(), new_candidate, task["operation_ref"], task["ordinal"], task["payload_json"]))
    receipt = conn.execute("SELECT * FROM WorkbenchRunReceipts WHERE run_ref=?", (original_ref,)).fetchone()
    result = remap(json.loads(receipt["result_json"]))
    if change_receipt is not None:
        change_receipt(result)
    conn.execute("INSERT INTO WorkbenchRunReceipts VALUES (?,?,?,?,?)", (new_run_ref(), ref, receipt["state"], canonical_json(result), accepted))
    original = conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE request_key=(SELECT request_key FROM WorkbenchRunJobs WHERE run_ref=?)",
                            (original_ref,)).fetchone()
    WorkbenchCommandRepository(conn).insert(request_key=key, receipt_ref=new_run_ref()[:32], action=original["action"],
        context_ref=source["input_ref"], input_hash=original["input_hash"],
        outcome=WorkbenchCommandOutcome("committed", {"run_ref": ref}))
    _save_cloned_read_models(conn, ref)
    conn.commit()
    return ref, mapping[case.history_refs["candidate_ref"]]


def _save_cloned_read_models(conn, run_ref):
    """A fixture archive uses the same verified preparation and pure builder as migration."""
    store, repo = CandidateStore(conn), WorkbenchRunRepository(conn)
    run = repo.head(run_ref)
    packet = _read_packet(store, run)
    for candidate in packet["rows"]:
        _prepare_candidate(store, packet, candidate)
    resolver = decision_baseline_source_resolver(conn, candidate_provider=_candidate_provider(store, repo, packet))
    official = read_decision_baseline(packet["capture"], packet["facts"], packet["disposition"], run["accepted_at"],
                                      source_resolver=resolver)
    states = official["source_states"]
    dependencies = repo.dependency_heads(
        sorted({row["source_candidate_ref"] for row in states if row.get("source_candidate_ref") is not None}),
        sorted({row["source_scenario_ref"] for row in states if row.get("source_scenario_ref") is not None}))
    admission = prepare_admission_read_models(run, packet["capture"], official, facts=packet["facts"],
                                               receipt=packet["receipt"], dependencies=dependencies)
    repo.insert_admission_read_model(run_ref, admission["scope"], admission["decision"])
    models = build_decision_read_models(run, packet["capture"], packet["receipt"], packet["rows"],
        packet["prepared_candidates"], official, facts=packet["facts"], dependencies=dependencies,
        process=(packet["receipt"] or {}).get("unified_process"), admission=admission["decision"])
    repo.insert_decision_read_models(run_ref, models["run_model"], models["candidate_models"])


def api(case):
    from web.routes.workbench.decision_history import register_decision_history_routes

    bp = Blueprint("p7_decision_history", __name__)
    register_decision_history_routes(bp)
    case.app.register_blueprint(bp)
    statements = []

    @case.app.before_request
    def bind():
        g.db = connect(case.path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(statements.append)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client(), statements


def read(client, **query):
    if isinstance(query.get("metric_keys"), list):
        query["metric_keys"] = ",".join(query["metric_keys"])
    response = client.get(BASE, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()

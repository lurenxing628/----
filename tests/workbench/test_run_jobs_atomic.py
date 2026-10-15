"""Failure injection at actual SQLite transaction boundaries; original rows survive."""

import json
import pickle
import sqlite3
from collections import Counter
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain, canonical_json
from core.services.workbench.facts.admission_scope import project_admitted_scope
from core.services.workbench.facts.decision_read_models import public_job_status
from core.services.workbench.run import result_preparation
from core.services.workbench.run import worker as worker_module
from core.services.workbench.run.jobs_facts import capture_run_facts
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories import workbench_run_repo as run_repo_module
from data.repositories import workbench_run_result_repo as result_repo_module
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_jobs_support import service


def test_receipt_write_failure_rolls_back_admission(job_case, monkeypatch):
    from collections import Counter

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.run import jobs, preflight
    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

    case = job_case
    ref, token = case.intent()
    before = all_rows(case.conn)
    original_insert = WorkbenchCommandRepository.insert
    receipt_failures = []

    def fail(*args, **kwargs):
        receipt_failures.append("receipt_insert")
        raise sqlite3.OperationalError("accept receipt disk write failed")

    monkeypatch.setattr(WorkbenchCommandRepository, "insert", fail)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).accept(ref, token, "run-request-00000001")
    assert all_rows(case.conn) == before
    assert not case.conn.in_transaction
    assert receipt_failures == ["receipt_insert"]

    monkeypatch.setattr(WorkbenchCommandRepository, "insert", original_insert)
    input_checks = []
    input_admitted = WorkbenchRunRepository.input_admitted

    def checked_input(repo, input_ref):
        input_checks.append(input_ref)
        return input_admitted(repo, input_ref)

    monkeypatch.setattr(WorkbenchRunRepository, "input_admitted", checked_input)
    table_reads, preparations, statements = Counter(), Counter(), []
    capture_table = WorkbenchPreflightFactsRepository.capture_table
    def capture_once(repo, name):
        table_reads[name] += 1
        return capture_table(repo, name)
    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", capture_once)
    for module, name in ((jobs, "GenerationFacts"), (preflight, "configuration_snapshot")):
        original = getattr(module, name)
        def prepared_once(*args, _name=name, _original=original, **kwargs):
            preparations[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, prepared_once)
    case.conn.set_trace_callback(statements.append)
    accepted = service(case.conn).accept(ref, token, "run-request-00000001")
    case.conn.set_trace_callback(None)
    assert accepted["replayed"] is False and input_checks == [ref]
    assert table_reads and set(table_reads.values()) == {1}
    assert preparations == {"GenerationFacts": 1, "configuration_snapshot": 1}
    assert not any(sql.upper().startswith("SELECT") and "FROM WORKBENCHRUNJOBS" in sql.upper()
                   and any(field in sql.upper() for field in ("FACTS_JSON", "EXECUTION_JSON", "BASELINE_JSON"))
                   for sql in statements)
    assert accepted["data"]["scope_summary"]["run_options"]["time_budget_seconds"] == 60
    actual = accepted["data"]
    original_job = public_job_status(WorkbenchRunRepository(case.conn).status(accepted["run_ref"]))
    assert actual == original_job
    assert service(case.conn).get(accepted["run_ref"]) == actual
    assert service(case.conn).lookup("run-request-00000001") == actual
    after = all_rows(case.conn)
    input_checks.clear()
    replayed = service(case.conn).accept(ref, "expired-token-is-not-revalidated", "run-request-00000001")
    assert replayed["replayed"] is True and replayed["run_ref"] == accepted["run_ref"]
    assert replayed["receipt_ref"] == accepted["receipt_ref"] and input_checks == []
    assert all_rows(case.conn) == after
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).accept(ref, token, "run-request-00000002")
    assert rejected.value.code == "input_already_used" and input_checks == [ref]
    assert all_rows(case.conn) == after
    assert not case.conn.in_transaction
    with pytest.raises(WorkbenchCommandRejected) as budget_type:
        case.preflight(dict(case.settings(), time_budget_seconds=True))
    assert budget_type.value.code == "invalid_input" and budget_type.value.status == 422
    case.config(graph_analysis_mode="off")
    budget_ref, budget_token = case.intent(dict(case.settings(), time_budget_seconds=10))
    assert budget_ref != ref
    prepare_admission = jobs.WorkbenchRunService._prepare_admission
    def actual_budget(svc, prepared, *args):
        assert prepared.config_snapshot.time_budget_seconds == 60
        assert prepared.prepared_input.cfg.time_budget_seconds == prepared.run_options["time_budget_seconds"] == 10
        assert prepared.prepared_input.cfg.graph_analysis_mode == prepared.run_options["graph_analysis_mode"] == "off"
        return prepare_admission(svc, prepared, *args)
    monkeypatch.setattr(jobs.WorkbenchRunService, "_prepare_admission", actual_budget)
    budget_run = service(case.conn).accept(budget_ref, budget_token, "run-request-00000003")
    assert budget_run["data"]["scope_summary"]["run_options"]["time_budget_seconds"] == 10
    assert case.conn.execute("SELECT config_value FROM ScheduleConfig WHERE config_key='time_budget_seconds'").fetchone()[0] == "60"


@pytest.mark.parametrize("failure_stage", ["second_candidate"])
def test_result_second_write_and_receipt_failure_are_all_atomic(job_case, monkeypatch, failure_stage):
    case = job_case
    accepted = case.accept()
    captured_scope = accepted["data"]["scope_summary"]
    legacy_row = WorkbenchRunRepository(case.conn).get(accepted["run_ref"])
    legacy_facts = json.loads(legacy_row["facts_json"])
    legacy_facts["tables"].pop("ScheduleConfig")
    legacy_row["facts_json"] = canonical_json(legacy_facts)
    legacy_scope = project_admitted_scope(json.loads(legacy_row["normalized_input_json"]), legacy_facts)
    assert legacy_scope["objective"] is None and legacy_scope["objective_label"] is None
    assert {"field": "objective", "code": "not_recorded", "message": "排产时没有记下这一项。"} in legacy_scope["data_gaps"]
    before = capture_run_facts(case.conn)
    save = WorkbenchRunResultRepository.save
    finish = WorkbenchRunRepository.finish
    executed = []

    def broken_save(repo, run_ref, candidates):
        if failure_stage != "second_candidate":
            return save(repo, run_ref, candidates)
        save(repo, run_ref, candidates[:1])
        executed.append(repo.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0])
        raise sqlite3.OperationalError("second candidate write failed")

    def broken_finish(repo, run_ref, state, result, now):
        if failure_stage == "result_receipt":
            raise sqlite3.OperationalError("result receipt failed")
        if failure_stage == "terminal_update":
            finish(repo, run_ref, state, result, now)
            raise sqlite3.OperationalError("result transaction commit failed")
        return finish(repo, run_ref, state, result, now)

    monkeypatch.setattr(WorkbenchRunResultRepository, "save", broken_save)
    monkeypatch.setattr(WorkbenchRunRepository, "finish", broken_finish)
    with pytest.raises(WorkbenchCommandUncertain):
        WorkbenchRunWorker(case.conn, clock=lambda: datetime(2026, 9, 10, 12, 1, 0, 100000)).execute(accepted["run_ref"])
    assert not case.conn.in_transaction
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 0
    running = service(case.conn).get(accepted["run_ref"])
    assert running["state"] == "running" and running["scope_summary"] == captured_scope
    assert capture_run_facts(case.conn) == before
    if failure_stage == "second_candidate":
        assert executed == [1]
    monkeypatch.undo()
    recovery = service(case.conn)
    recovery.clock = lambda: datetime(2026, 9, 10, 12, 1, 0, 123456)
    outcome = recovery.recover_unfinished_runs()
    assert outcome["recovered"] == [accepted["run_ref"]]
    interrupted = service(case.conn).get(accepted["run_ref"])
    assert interrupted["state"] == "interrupted" and interrupted["scope_summary"] == captured_scope
    assert interrupted["finished_at"] == "2026-09-10T12:01:00.123456"


    # Completion and a repeated terminal execution share the same small status DTO.
    next_run = case.accept(key="run-request-status-0002")
    status_reads, ownership_reads = [], []
    original_status, original_head = WorkbenchRunRepository.status, WorkbenchRunRepository.claim_head

    def small_read(method, observed):
        def read(repo, ref):
            def authorize(action, table, column, database, trigger):
                if action == sqlite3.SQLITE_READ:
                    observed.append((table, column))
                    if table == "WorkbenchRunCandidateTasks" or (
                            table == "WorkbenchRunJobs" and column in ("normalized_input_json", "facts_json", "execution_json", "baseline_json")) or (
                            table == "WorkbenchRunReceipts" and column == "result_json"):
                        return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            repo.conn.set_authorizer(authorize)
            try:
                return method(repo, ref)
            finally:
                repo.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        return read

    monkeypatch.setattr(WorkbenchRunRepository, "status", small_read(original_status, status_reads))
    monkeypatch.setattr(WorkbenchRunRepository, "claim_head", small_read(original_head, ownership_reads))
    phase, encodings, packets, artifacts, models = ["prepare"], [], [], [], []
    original_json = canonical_json
    original_prepare = worker_module.prepare_run_result
    original_artifacts = result_preparation._prepare_result_artifacts
    original_models = result_preparation.build_decision_read_models
    original_persist = WorkbenchRunWorker._persist

    def encode_once(value):
        encoded = original_json(value)
        encodings.append((phase[0], encoded))
        return encoded

    def capture_artifacts(*args, **kwargs):
        raw = original_artifacts(*args, **kwargs)
        artifacts.append(raw)
        return raw

    def capture_models(*args, **kwargs):
        raw = original_models(*args, **kwargs)
        models.append(raw)
        return raw

    def prepare_once(*args, **kwargs):
        prepared = original_prepare(*args, **kwargs)
        packets.append(prepared)
        return prepared

    def persist_encoded(worker, *args, **kwargs):
        phase[0] = "persist"
        try:
            return original_persist(worker, *args, **kwargs)
        finally:
            phase[0] = "returned"

    monkeypatch.setattr(run_repo_module, "canonical_json", encode_once)
    monkeypatch.setattr(result_repo_module, "canonical_json", encode_once)
    monkeypatch.setattr(result_preparation, "_prepare_result_artifacts", capture_artifacts)
    monkeypatch.setattr(result_preparation, "build_decision_read_models", capture_models)
    monkeypatch.setattr(worker_module, "prepare_run_result", prepare_once)
    monkeypatch.setattr(WorkbenchRunWorker, "_persist", persist_encoded)
    completed = WorkbenchRunWorker(case.conn).execute(next_run["run_ref"])
    assert len(packets) == len(artifacts) == len(models) == 1
    packet = packets[0]
    assert pickle.loads(pickle.dumps(packet)) == packet
    assert set(packet.result) == {"state", "result_json", "error_json"}
    assert json.loads(packet.result["result_json"]) == artifacts[0][1]
    storage_json = [packet.result["result_json"], packet.result["error_json"]]
    for encoded, raw in zip(packet.candidates, artifacts[0][0]):
        assert set(encoded) == {"candidate_ref", "key", "sequence", "status", "task_count", "artifact_json", "tasks"}
        assert json.loads(encoded["artifact_json"]) == raw["artifact"]
        assert json.loads(encoded["artifact_json"])["target_objectives"] == artifacts[0][1]["selection"]["target_objectives"]
        storage_json.append(encoded["artifact_json"])
        for task, raw_task in zip(encoded["tasks"], raw["tasks"]):
            assert set(task) == {"row_ref", "operation_ref", "payload_json"}
            assert json.loads(task["payload_json"]) == raw_task["payload"]
            storage_json.append(task["payload_json"])
    for encoded, raw in [(packet.read_models["run_model"], models[0]["run_model"])] + list(zip(
            packet.read_models["candidate_models"], models[0]["candidate_models"])):
        for key, value in encoded.items():
            if key.endswith("_json"):
                assert value is None and raw[key[:-5]] is None or json.loads(value) == raw[key[:-5]]
                if value is not None:
                    storage_json.append(value)
        assert not any(key in encoded for key in ("header", "context", "memberships", "calendar", "official", "process",
                                                   "summary", "preparation", "completion", "delivery", "delivery_detail", "arrangements"))
    assert Counter(encoded for during, encoded in encodings if during == "prepare") == Counter(storage_json)
    assert not any(during == "persist" for during, encoded in encodings)
    receipt_json = case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (next_run["run_ref"],)).fetchone()[0]
    assert receipt_json == packet.result["result_json"]
    assert json.loads(receipt_json).get("unified_process") is not None
    assert "unified_process" not in json.loads(receipt_json)["summary"]["algo"]["candidate_comparison"]
    print("U4_STORAGE_COUNTS", json.dumps({"prepared_json_columns": len(storage_json),
        "prepare_encoding_calls": sum(during == "prepare" for during, encoded in encodings),
        "persist_encoding_calls": sum(during == "persist" for during, encoded in encodings)}))
    assert completed["state"] == "complete" and len(completed["candidates"]) == 1
    assert completed == service(case.conn).get(next_run["run_ref"])
    called = []
    repeated = WorkbenchRunWorker(case.conn, compute_runner=lambda *args, **kwargs: called.append(True)).execute(next_run["run_ref"])
    assert repeated == completed and called == []
    assert status_reads and ownership_reads
    assert all(table != "WorkbenchRunCandidateTasks" for table, column in status_reads + ownership_reads)
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunDecisionReadModels WHERE run_ref=?", (next_run["run_ref"],)).fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateReadModels WHERE run_ref=?", (next_run["run_ref"],)).fetchone()[0] == 1

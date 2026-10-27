"""Failure injection at actual SQLite transaction boundaries; original rows survive."""

import json
import pickle
import sqlite3
from collections import Counter
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain
from core.services.workbench.facts.admission_scope import project_admitted_scope
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.decision_read_models import public_job_status
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.run_history_projection import scope_summary
from core.services.workbench.run import result_preparation
from core.services.workbench.run import worker as worker_module
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.shared.strict_json import canonical_json
from data.repositories import workbench_run_repo as run_repo_module
from data.repositories import workbench_run_result_repo as result_repo_module
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_jobs_support import service


def test_worker_reuses_the_admission_dispositions_without_reclassifying(job_case, monkeypatch):
    from core.models.workbench_run_compute import CandidateRunInputError
    from core.services.workbench.facts.decision_read_models import decode_model
    from core.services.workbench.run import input as run_input
    from tests.workbench.run_candidate_support import corrupt_update

    case = job_case
    accepted = case.accept(key="worker-reuses-admitted-dispositions")
    corrupted = case.accept(key="worker-rejects-null-admitted-dispositions")
    admission = decode_model(WorkbenchRunRepository(case.conn).admission_read_model(accepted["run_ref"], ("decision",)),
                             ("decision",))["decision"]
    assert admission["dispositions"]

    def reclassify(*_args, **_kwargs):
        raise AssertionError("worker 只读受理时存档的处置，不再重新分类")

    monkeypatch.setattr(run_input, "classify_rows", reclassify)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    receipt = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?",
                                           (accepted["run_ref"],)).fetchone()[0])
    assert receipt["dispositions"] == admission["dispositions"]

    corrupt_update(case.conn, "WorkbenchRunAdmissionReadModels",
                   "UPDATE WorkbenchRunAdmissionReadModels SET decision_json=? WHERE run_ref=?",
                   (canonical_json(dict(admission, dispositions=None)), corrupted["run_ref"]))
    with pytest.raises(CandidateRunInputError) as error:
        WorkbenchRunWorker(case.conn).execute(corrupted["run_ref"])
    assert error.value.reason == "admission_disposition_mismatch"
    assert public_job_status(WorkbenchRunRepository(case.conn).status(corrupted["run_ref"]))["state"] == "failed"


def test_admitted_classification_rejects_dispositions_for_other_operations():
    from types import SimpleNamespace

    from core.models.workbench_run_compute import CandidateRunInputError
    from core.services.workbench.facts.run_input_rows import admitted_classification

    operations = [SimpleNamespace(id=1)]
    admitted = [{"op_id": 1, "status": "skipped", "issues": []}, {"op_id": 2, "status": "skipped", "issues": []}]
    for invalid in (None, [None], [{"op_id": "1", "status": "skipped"}], admitted):
        with pytest.raises(CandidateRunInputError) as error:
            admitted_classification(operations, invalid, set())
        assert error.value.reason == "admission_disposition_mismatch"
    with pytest.raises(CandidateRunInputError) as error:
        admitted_classification(operations, admitted[:1], {1})
    assert error.value.reason == "admission_disposition_mismatch"


def test_spawned_compute_consumes_the_parent_admission_and_returns_actual_status(job_case):
    from web.bootstrap.run_compute_process import run_compute_in_process

    case = job_case
    accepted = case.accept(key="spawned-compute-single-admission")
    result = WorkbenchRunWorker(case.conn, compute_runner=run_compute_in_process).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["result_persisted"] is True
    assert result == public_job_status(WorkbenchRunRepository(case.conn).status(accepted["run_ref"]))
    assert result["started_at"] is not None and result["finished_at"] is not None and result["receipt_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts WHERE run_ref=?", (accepted["run_ref"],)).fetchone()[0] == 1


def test_owned_file_compute_matches_thread_snapshot_types_and_payload(tmp_path, monkeypatch):
    from datetime import date
    from types import SimpleNamespace

    from core.infrastructure.connection_guards import is_query_only
    from core.infrastructure.database import get_connection
    from core.infrastructure.snapshot_connection import backup_to_file, open_readonly_immutable

    source = get_connection(str(tmp_path / "source.sqlite"))
    source.execute("CREATE TABLE Facts(day DATE, at TIMESTAMP, label TEXT)")
    source.execute("INSERT INTO Facts VALUES (?,?,?)", (date(2026, 10, 17), datetime(2026, 10, 17, 8, 0, 0, 123456), "原内容"))
    source.commit()
    row = {"run_ref": "a" * 48, "execution_json": "[]", "normalized_input_json": '{"scope":"same"}',
           "baseline_json": "{}", "facts_json": "{}", "facts_hash": None}
    worker = WorkbenchRunWorker(source)
    monkeypatch.setattr(worker, "_check_facts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker_module, "GenerationFacts", lambda _capture: SimpleNamespace(operations={"b" * 48: 1}))
    monkeypatch.setattr(worker_module, "prepare_run_result", lambda value, *_args, **_kwargs: value)

    def compute(conn, normalized_input, projections, **_kwargs):
        assert conn.in_transaction and is_query_only(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        fact = conn.execute("SELECT * FROM Facts").fetchone()
        assert isinstance(fact, sqlite3.Row) and type(fact["day"]) is date and type(fact["at"]) is datetime
        return {"day": fact["day"].isoformat(), "at": fact["at"].isoformat(), "label": fact["label"],
                "input": normalized_input, "execution": projections}

    monkeypatch.setattr(worker_module, "compute_candidate_run", compute)
    # worker 只从受理决策读模型取存档的处置交给计算；这里的假计算不读它。
    admission = {"dispositions": []}
    try:
        thread_payload = worker._compute(row, admission)
        path = str(tmp_path / "owned.sqlite")
        backup_to_file(source, path)

        def no_second_copy(_source):
            raise AssertionError("An owned process snapshot must not be backed up again")

        monkeypatch.setattr(worker_module, "computation_database", no_second_copy)
        with open_readonly_immutable(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                                     row_factory=sqlite3.Row) as owned:
            owned.execute("PRAGMA foreign_keys=ON")
            process_payload = worker.compute_owned_snapshot(owned, row, admission)
            assert process_payload == thread_payload
            with pytest.raises(sqlite3.OperationalError):
                owned.execute("INSERT INTO Facts VALUES (NULL,NULL,'write')")
    finally:
        source.close()


def test_receipt_write_failure_rolls_back_admission(job_case, monkeypatch):
    from collections import Counter

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.material.stage_availability import MaterialAvailability
    from core.services.scheduler.calendar.service import CalendarService
    from core.services.scheduler.config import config_snapshot
    from core.services.scheduler.execution import execution_ledger_adapter
    from core.services.workbench.run import jobs
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
    calendars, material_indexes = [], []
    initialize_calendar, initialize_materials = CalendarService.__init__, MaterialAvailability.__init__

    def calendar_once(calendar, conn, logger=None, *, capture=None):
        calendars.append(capture)
        initialize_calendar(calendar, conn, logger, capture=capture)

    def materials_once(availability, tables):
        material_indexes.append(availability)
        initialize_materials(availability, tables)

    monkeypatch.setattr(CalendarService, "__init__", calendar_once)
    monkeypatch.setattr(MaterialAvailability, "__init__", materials_once)
    capture_table = WorkbenchPreflightFactsRepository.capture_table
    def capture_once(repo, name):
        table_reads[name] += 1
        return capture_table(repo, name)
    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", capture_once)
    for module, name in ((jobs, "GenerationFacts"), (config_snapshot, "build_schedule_config_snapshot"),
                         (execution_ledger_adapter, "current_execution_plan")):
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
    assert preparations == {"GenerationFacts": 1, "build_schedule_config_snapshot": 1, "current_execution_plan": 1}
    assert len(calendars) == len(material_indexes) == 1 and calendars[0] is not None
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
    legacy_input = json.loads(legacy_row["normalized_input_json"])
    legacy_scope = project_admitted_scope(
        legacy_input, GenerationFacts({"facts_text": legacy_row["facts_json"],
                                       "execution": json.loads(legacy_row["execution_json"])}),
        summary=scope_summary(canonical_json(legacy_input)))
    assert legacy_scope["objective"] is None and legacy_scope["objective_label"] is None
    assert {"field": "objective", "code": "not_recorded", "message": "排产时没有记下这一项。"} in legacy_scope["data_gaps"]
    before = ProductionFactsCapture(case.conn).content()
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
    assert ProductionFactsCapture(case.conn).content() == before
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


def test_worker_shares_capture_inside_compute_and_recaptures_only_for_persistence(job_case, monkeypatch):
    from core.services.workbench.facts.production_capture import ProductionFactsCapture
    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

    case = job_case
    accepted = case.accept()
    captures, tables = [], Counter()
    initialize, read = ProductionFactsCapture.__init__, WorkbenchPreflightFactsRepository.capture_table

    def capture_once(capture, conn):
        captures.append(conn)
        initialize(capture, conn)

    def table_once(repo, name):
        tables[id(repo.conn), name] += 1
        return read(repo, name)

    monkeypatch.setattr(ProductionFactsCapture, "__init__", capture_once)
    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", table_once)
    completed = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert completed["state"] == "complete"
    assert len(captures) == 2 and captures[0] is not case.conn and captures[1] is case.conn
    assert tables and set(tables.values()) == {1}


_RUN_KEY = "run-request-00000001"
_RUN_TARGET = "/api/workbench/v1/scheduling/requests/" + _RUN_KEY
_RUN_READ_FAILED = "排产记录没有读出来。请刷新重试；仍不行请联系维护人员，并告知下方编号。"


@pytest.mark.parametrize("method,path,failure,log_prefix,message,committed,request_key", [
    ("GET", "/runs/" + "a" * 32, RuntimeError("run service broke"), "排产运行接口失败",
     _RUN_READ_FAILED, False, None),
    ("POST", "/runs", RuntimeError("run service broke"), "排产运行接口失败",
     _RUN_READ_FAILED, "unknown", _RUN_KEY),
    ("POST", "/runs", WorkbenchCommandUncertain(_RUN_KEY), "排产受理结果待核实",
     "这次提交结果不确定，可能已经生效。请刷新后核对，不要重复提交。", "unknown", _RUN_KEY),
], ids=["read-unexpected", "accept-unexpected", "accept-uncertain"])
def test_run_api_500_logs_the_request_ref_shown_to_the_user(monkeypatch, caplog, method, path, failure, log_prefix,
                                                             message, committed, request_key):
    """排产运行接口包装成 500 的错误：日志记下的编号就是用户看到的「下方编号」，原始异常留在日志里。"""
    import logging
    from types import SimpleNamespace

    from flask import Blueprint, Flask

    from web.routes.workbench import scheduling_jobs

    def broken(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(scheduling_jobs, "_service", lambda: SimpleNamespace(get=broken, accept=broken))
    app = Flask(__name__)
    bp = Blueprint("run_api_failures", __name__)
    scheduling_jobs.register_scheduling_job_routes(bp)
    app.register_blueprint(bp)
    body = {"input_ref": "input", "write_token": "token", "request_key": _RUN_KEY} if method == "POST" else None
    with caplog.at_level(logging.ERROR):
        response = app.test_client().open("/api/workbench/v1/scheduling" + path, method=method, json=body)
    assert response.status_code == 500, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    result = response.get_json()
    error = result["error"]
    assert result["committed"] == committed
    assert (error["code"], error["message"]) == ("storage_failure", message)
    assert (error.get("request_key"), error.get("result_target")) == (request_key, request_key and _RUN_TARGET)
    record, = [item for item in caplog.records if item.getMessage().startswith(log_prefix)]
    assert record.getMessage() == log_prefix + " request_ref=" + error["request_ref"]
    assert record.exc_info[1] is failure

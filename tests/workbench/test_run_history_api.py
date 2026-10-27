"""Real engine artifacts, complete Flask factory and a separate-process restart."""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from flask import Blueprint

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_history import RunHistoryScope
from core.models.workbench_run_job import new_run_ref
from core.services.workbench.facts.decision_read_model import build_failure_read_models
from core.services.workbench.facts.decision_read_models import decode_model
from core.services.workbench.run.history import WorkbenchRunHistoryQueryService
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests._support.excel_templates import point_env_at_shared
from tests.workbench.run_history_support import BASE, dump, read
from tests.workbench.run_history_support import history_case as _history_case  # noqa: F401
from tests.workbench.run_jobs_support import service
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.run_history import register_run_history_routes


def test_full_flask_app_actual_engine_run_and_only_temporary_sqlite(history_case, tmp_path, monkeypatch):
    case = history_case
    ref, token = case.intent()
    runner = service(case.conn)
    runner.clock = lambda: datetime(2026, 9, 10, 12, 0, 0, 50000)
    accepted = runner.accept(ref, token, "run-request-00000001")
    assert accepted["data"]["accepted_at"] == "2026-09-10T12:00:00.050000"
    captured_scope = accepted["data"]["scope_summary"]
    assert (captured_scope["batch_count"], captured_scope["operation_count"]) == (1, 1)
    assert captured_scope["batches"] == [{"batch_ref": case.ref("batch", "B1"), "batch_id": "B1",
                                         "part_no": "P1", "part_label": "Part"}]
    assert (captured_scope["objective"], captured_scope["objective_label"]) == ("min_overdue", "最少超期")
    times = iter((datetime(2026, 9, 10, 12, 1, 0, 125000),))
    worker_result = WorkbenchRunWorker(case.conn,
        clock=lambda: next(times, datetime(2026, 9, 10, 12, 1, 0, 875000))).execute(accepted["run_ref"])
    assert worker_result["started_at"] == "2026-09-10T12:01:00.125000"
    assert worker_result["finished_at"] == "2026-09-10T12:01:00.875000"
    assert datetime.fromisoformat(worker_result["finished_at"]) - datetime.fromisoformat(worker_result["started_at"]) == timedelta(seconds=0.75)
    assert case.conn.execute("SELECT recorded_at FROM WorkbenchRunReceipts WHERE run_ref=?", (accepted["run_ref"],)).fetchone()[0] == worker_result["finished_at"]
    case.conn.execute("UPDATE Parts SET part_name='Current part' WHERE part_no='P1'")
    case.operation(seq=2)
    case.config(objective="min_changeover")
    assert service(case.conn).get(accepted["run_ref"])["scope_summary"] == captured_scope
    expected_candidate_count = len(worker_result["candidates"])
    expected_task_count = sum(row["task_count"] for row in worker_result["candidates"])
    assert 1 <= expected_candidate_count <= 3
    receipt = json.loads(case.conn.execute(
        "SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (accepted["run_ref"],)).fetchone()[0])
    selection = receipt["selection"]
    assert selection["selected_candidate_ref"] == next(row["candidate_ref"] for row in worker_result["candidates"] if row["selected"])
    assert set(selection["objective_winners"]) == set(selection["target_objectives"])
    assert set(selection["objective_winners"].values()) <= {row["candidate_ref"] for row in worker_result["candidates"]}
    for key, path in (("APS_DB_PATH", case.path), ("APS_LOG_DIR", tmp_path / "logs"), ("APS_BACKUP_DIR", tmp_path / "backups")):
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("APS_ENV", "development")
    point_env_at_shared(monkeypatch)
    original, paths = sqlite3.connect, []

    def guard(path, *args, **kwargs):
        value = url2pathname(urlsplit(str(path)).path) if str(path).startswith("file:") else str(path)
        assert value == ":memory:" or Path(value).resolve() == case.path.resolve(), "Nonfixture SQLite access"
        paths.append(value)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guard)
    from web.bootstrap.entrypoint import create_app_with_mode
    app = create_app_with_mode("default")
    if not any(rule.rule == BASE and "GET" in rule.methods for rule in app.url_map.iter_rules()):
        bp = Blueprint("bq_full_app_history", __name__)
        register_run_history_routes(bp)
        app.register_blueprint(bp)
    if not any(rule.rule == BASE + "/<run_ref>/candidates" for rule in app.url_map.iter_rules()):
        candidates_bp = Blueprint("bq_full_app_candidates", __name__)
        register_run_candidate_routes(candidates_bp)
        app.register_blueprint(candidates_bp)
    client = app.test_client()
    from core.services.workbench.run.jobs import WorkbenchRunService

    def forbidden(*args, **kwargs):
        raise AssertionError("History GET must not install, recover or dispatch")

    monkeypatch.setattr(WorkbenchRunService, "recover_unfinished_runs", forbidden)
    monkeypatch.setattr(WorkbenchRunWorker, "execute", forbidden)
    before = dump(case.conn)
    data = read(client)["data"]
    row = data["runs"][0]
    assert row["run_ref"] == accepted["run_ref"] and row["candidate_count"] == expected_candidate_count
    assert row["task_count"] == expected_task_count
    assert row["scope_summary"]["start_date"] == "2026-09-09"
    assert row["constraint_verification"] == "not_checked_by_history"
    reopened_client = app.test_client()
    restored = read(reopened_client)["data"]["runs"][0]
    catalog = reopened_client.get(BASE + "/" + restored["run_ref"] + "/candidates")
    assert catalog.status_code == 200
    candidate_ref = catalog.get_json()["data"]["candidates"][0]["candidate_ref"]
    workspace = reopened_client.get("/api/workbench/v1/scheduling/candidates/" + candidate_ref + "/workspace")
    assert workspace.status_code == 200
    assert workspace.get_json()["data"]["candidate"]["run_ref"] == accepted["run_ref"]
    assert workspace.get_json()["data"]["task_count"] == 1
    rules = [rule for rule in app.url_map.iter_rules() if rule.rule == BASE]
    assert any("GET" in rule.methods for rule in rules)
    # The full app may still be awaiting the parent's explicit AV registration.
    assert not app.config.get("WORKBENCH_RUN_JOBS_ENABLED")
    assert dump(case.conn) == before and paths and str(case.path) in paths


def test_new_process_reopens_history_without_browser_token_cache(history_case):
    case = history_case
    complete = case.accept(new_run_ref())
    complete_result = WorkbenchRunWorker(case.conn).execute(complete["run_ref"])
    assert complete_result["state"] == "complete"
    refs = [complete["run_ref"]]
    # A stored skipped operation leaves the real selected candidate short of the admitted scope.
    skipped = case.operation(seq=2)
    case.conn.execute("UPDATE BatchOperations SET status='skipped' WHERE id=?", (skipped,))
    case.conn.commit()
    partial = case.accept(new_run_ref())
    partial_result = WorkbenchRunWorker(case.conn).execute(partial["run_ref"])
    assert partial_result["state"] == "partial"
    assert partial_result["candidates"] and all(row["status"] == "completed" for row in partial_result["candidates"])
    assert partial_result["candidates"][0]["task_count"] == 1
    for candidate in partial_result["candidates"]:
        actual_count = case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?",
                                        (candidate["candidate_ref"],)).fetchone()[0]
        assert actual_count == candidate["task_count"]
    refs.append(partial["run_ref"])
    repo = WorkbenchRunRepository(case.conn)
    for state in ("failed", "interrupted"):
        accepted = case.accept(new_run_ref())
        run_ref = accepted["run_ref"]
        when = datetime.fromisoformat(accepted["data"]["accepted_at"])
        result = {"state": state, "result_persisted": False, "candidates": [],
                  "error": {"code": "history_fixture_" + state,
                            "message": "跨进程历史读取测试明确保存的 " + state + " 终态。"}}
        with TransactionManager(case.conn).transaction(begin_immediate=True):
            assert repo.claim(run_ref, new_run_ref(), (when + timedelta(seconds=1)).isoformat(timespec="microseconds"))
            admission = decode_model(repo.admission_read_model(run_ref, fields=("decision",)), ("decision",))["decision"]
            models = build_failure_read_models(repo.get(run_ref), admission, result)
            repo.insert_decision_read_models(run_ref, models["run_model"], models["candidate_models"])
            repo.finish(run_ref, result, (when + timedelta(seconds=2)).isoformat(timespec="microseconds"))
        assert not case.conn.in_transaction
        refs.append(run_ref)
    expected, fingerprint = WorkbenchRunHistoryQueryService(case.conn).catalog(RunHistoryScope())
    before = dump(case.conn)
    code = '''import json, sqlite3, sys
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.infrastructure.schema_declaration import load_schema_sql
from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.run.history import WorkbenchRunHistoryQueryService
conn = sqlite3.connect(sys.argv[1])
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=ON")
assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
assert current_schema_contract_issues(conn, schema_version=CURRENT_SCHEMA_VERSION, schema_sql=load_schema_sql()) == []
conn.execute("PRAGMA query_only=ON")
data, fingerprint = WorkbenchRunHistoryQueryService(conn).catalog(RunHistoryScope())
print(json.dumps({"data": data, "fingerprint": fingerprint}))
conn.close()
'''
    completed = subprocess.run([sys.executable, "-c", code, str(case.path)], cwd=str(Path(__file__).resolve().parents[2]),
                               env=dict(os.environ), check=True, capture_output=True, text=True, timeout=30)
    actual = json.loads(completed.stdout)
    assert actual["data"] == expected and actual["fingerprint"] == fingerprint
    assert {row["run_ref"] for row in actual["data"]["runs"]} == set(refs)
    assert {row["state"] for row in actual["data"]["runs"]} == {"complete", "partial", "failed", "interrupted"}
    assert dump(case.conn) == before


def test_history_conditions_strict_operator_machine_enum_parsing(history_case):
    from copy import deepcopy

    from core.infrastructure.read_evidence import read_evidence_scope
    from core.infrastructure.snapshot_connection import ddl_columns
    from core.services.workbench.facts.candidate_facts import GenerationFacts
    from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
    from core.services.workbench.history.catalog import read_history_catalog
    from core.services.workbench.history.conditions import (
        compare_prepared_history_conditions,
        prepare_history_condition_side,
        prepare_history_condition_source,
    )
    from core.services.workbench.history.reading import HistoryReader
    from core.shared.strict_json import canonical_json

    case = history_case
    accepted = case.accept(new_run_ref())
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete"
    with TransactionManager(case.conn).transaction(), candidate_read_snapshot(case.conn), read_evidence_scope(case.conn):
        descriptors, _ = read_history_catalog(case.conn)
        descriptor = next(row for row in descriptors if row["entry_ref"] == "run:" + accepted["run_ref"])
        packet = HistoryReader(case.conn, catalog=descriptors).read(descriptor)

    def with_operator_machine(base_packet, is_primary, skill_level, suffix):
        cloned = deepcopy(base_packet)
        facts = json.loads(cloned["capture"]["facts_text"])
        ddl = next(sql for kind, name, _, sql in facts["schema"] if kind == "table" and name == "OperatorMachine")
        columns = ddl_columns(ddl, "OperatorMachine", restricted=True)
        for row in facts["tables"]["OperatorMachine"]:
            row[columns.index("is_primary")] = is_primary
            row[columns.index("skill_level")] = skill_level
        cloned["capture"]["facts_text"] = canonical_json(facts)
        cloned["facts"] = GenerationFacts(cloned["capture"])
        cloned.update(ref=suffix * 48, entry_ref="run:" + suffix * 48)
        return cloned

    window = {"start": "2026-09-09T08:00:00", "end": "2026-09-09T16:00:00"}
    yes_packet = with_operator_machine(packet, "yes", "expert", "1")
    alias_packet = with_operator_machine(packet, "主操", "高级", "2")
    broken_packet = with_operator_machine(packet, "broken", "broken", "3")

    equal_pair = compare_prepared_history_conditions(
        prepare_history_condition_side(prepare_history_condition_source(yes_packet), window),
        prepare_history_condition_side(prepare_history_condition_source(alias_packet), window),
    )
    auth_rows = {row["field"]: row for row in equal_pair["conditions"]["rows"]
                 if row["category"] == "resource_qualifications" and row["field"] in ("is_primary", "skill_rank")}
    assert auth_rows["is_primary"]["state"] == "equal"
    assert auth_rows["is_primary"]["before"]["value"] == auth_rows["is_primary"]["after"]["value"] == "yes"
    assert auth_rows["skill_rank"]["state"] == "equal"
    assert auth_rows["skill_rank"]["before"]["value"] == auth_rows["skill_rank"]["after"]["value"] == 0

    broken_pair = compare_prepared_history_conditions(
        prepare_history_condition_side(prepare_history_condition_source(yes_packet), window),
        prepare_history_condition_side(prepare_history_condition_source(broken_packet), window),
    )
    broken_rows = {row["field"]: row for row in broken_pair["conditions"]["rows"]
                   if row["category"] == "resource_qualifications" and row["field"] in ("is_primary", "skill_rank")}
    for field in ("is_primary", "skill_rank"):
        assert broken_rows[field]["state"] == "unknown"
        assert broken_rows[field]["after"]["state"] == "unknown"
        assert broken_rows[field]["after"]["value"] is None


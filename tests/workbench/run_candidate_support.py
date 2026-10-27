"""BL-only fresh current-schema temporary databases and real engine fixtures."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.infrastructure.schema_declaration import load_schema_sql
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import JobCase
from web.routes.workbench.run_candidates import register_run_candidate_routes

BASE = "/api/workbench/v1/scheduling"
PRIVATE = {"version", "op_id", "candidate_key", "raw", "facts_json", "artifact_json", "payload_json",
           "machine_id", "operator_id", "supplier_id", "plan_ref", "task_ref", "source_key", "entity_key", "history"}


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@pytest.fixture(name="candidate_case")
def candidate_case(tmp_path):
    path = tmp_path / "bl-candidates.sqlite"
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"))
    conn = connect(path)
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert current_schema_contract_issues(conn, schema_version=CURRENT_SCHEMA_VERSION, schema_sql=load_schema_sql()) == []
    # Historical locked plans in this fixture were made for an explicit 08:00-16:00 shift.
    conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                 ('[{"start":"08:00","end":"16:00","day_offset":0}]',))
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Original lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Original operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Original part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    case.app = Flask("bl-candidate-tests")
    with case.app.app_context():
        yield case
    conn.close()


def compute(case, settings=None):
    accepted = case.accept(settings=settings)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    return result["run_ref"], [row["candidate_ref"] for row in result["candidates"]]


_OBJECTIVE_LABELS = {"min_overdue": "交期优先", "min_tardiness": "拖期更轻", "min_changeover": "切换更少"}


def install_representatives(monkeypatch, count):
    """Publish the real search winner as ``count`` per-objective representatives.

    The unified generator publishes one representative per distinct winning
    archive entry; tiny fixtures converge on one entry. This keeps the real
    search, validation, persistence and read models, and only splits the
    objective winners so a run carries several current-shape representatives.
    Tests then give the representatives different saved arrangements.
    """
    from core.services.workbench.run import compute as compute_module

    real = compute_module.run_candidate_comparison

    def representatives(**kwargs):
        outcome = real(**kwargs)
        (plan,) = outcome.candidates
        targets = list(outcome.target_objectives)
        groups = [targets[:len(targets) - count + 1]] + [[target] for target in targets[len(targets) - count + 1:]]
        plans = [replace(plan, sequence=index, candidate_key="business_" + str(index + 1), representative_objectives=group,
                         label=" · ".join(_OBJECTIVE_LABELS[target] for target in group))
                 for index, group in enumerate(groups)]
        winners = {target: plans[index].candidate_key for index, group in enumerate(groups) for target in group}
        selection = replace(outcome.selection, selected_candidate_key=plans[0].candidate_key, selected_plan=plans[0],
                            objective_winners=winners)
        return replace(outcome, candidates=plans, selection=selection)

    monkeypatch.setattr(compute_module, "run_candidate_comparison", representatives)


def compute_two_objectives(case):
    """Real unified search with two business representatives in the current saved shape.

    One machine runs two operation types in an eight-hour shift. Keeping the two
    09-09 batches on time costs two type changes; grouping the types saves one
    change but finishes B2 late. ``min_overdue``/``min_tardiness`` and
    ``min_changeover`` therefore select different archive entries.
    """
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Milling')")
    case.conn.executemany("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1',?)", [("T1",), ("T2",)])
    case.conn.execute("UPDATE Batches SET quantity=1,due_date='2026-09-09' WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET unit_hours=3 WHERE id=?", (case.op_id,))
    for code, kind, due in (("B2", "T2", "2026-09-09"), ("B3", "T1", "2026-09-10"), ("B4", "T2", "2026-09-10")):
        case.batch(code, quantity=1, due_date=due)
        case.operation(code, unit_hours=3, op_type_id=kind, op_type_name=kind)
    case.config(algo_mode="improve", time_budget_seconds=1)
    run_ref, refs = compute(case, case.settings("B1", "B2", "B3", "B4"))
    assert len(refs) == 2
    return run_ref, refs


def api(case):
    bp = Blueprint("bl_candidates", __name__)
    register_run_candidate_routes(bp)
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


def read(client, path, **query):
    response = client.get(BASE + path, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json()
    public(data)
    return data


def public(value, path=()):
    if type(value) is dict:
        private = PRIVATE - {"task_ref"} if path[-2:] == ("gantt_graph", "nodes") else PRIVATE
        if path[-2:] == ("generation", "baseline"):
            private = private - {"version"}
        assert not private.intersection(value)
        for key, child in value.items():
            public(child, path + (key,))
    elif type(value) is list:
        for child in value:
            public(child, path)


def state(conn):
    return tuple(conn.iterdump())


@contextmanager
def retained(conn):
    before, changes = state(conn), conn.total_changes
    try:
        yield
    finally:
        assert state(conn) == before
        assert conn.total_changes == changes


def corrupt_update(conn, table, sql, args=()):
    """Fixture-only corruption with the permanent schema restored before any read."""
    triggers = list(conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)))
    for row in triggers:
        conn.execute('DROP TRIGGER "' + row[0] + '"')
    conn.execute(sql, args)
    for row in triggers:
        conn.execute(row[1])
    conn.commit()


def edit_artifact(case, ref, edit):
    raw = case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0]
    artifact = json.loads(raw)
    edit(artifact)
    corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET artifact_json=? WHERE candidate_ref=?",
                   (json.dumps(artifact, ensure_ascii=False), ref))


def candidate_artifact_view(artifact, tasks):
    """Test/oracle view of arrangements; never rewrite the immutable archive."""
    rows = [{key: value for key, value in task.items() if key != "locked"} for task in tasks]
    artifact["validated_payload"] = {**artifact["validated_payload"], "schedule_rows": rows,
        "assigned_by_op_id": {str(row["op_id"]): {key: row[key] for key in ("machine_id", "operator_id")}
                              for row in rows if row["source"] == "internal"}}
    artifact["results"] = [{**metadata, **row} for metadata, row in zip(artifact["results"], rows)]
    return artifact


def stored_candidate_artifact(conn, ref):
    raw = conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0]
    tasks = [json.loads(row[0]) for row in conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (ref,))]
    return candidate_artifact_view(json.loads(raw), tasks)


def edit_capture(case, field, edit):
    assert field in ("facts_json", "execution_json", "normalized_input_json", "baseline_json")
    raw = case.conn.execute("SELECT " + field + " FROM WorkbenchRunJobs").fetchone()[0]
    value = json.loads(raw)
    edit(value)
    encoded = json.dumps(value, ensure_ascii=False)
    sql = "UPDATE WorkbenchRunJobs SET " + field + "=?"
    corrupt_update(case.conn, "WorkbenchRunJobs", sql, (encoded,))

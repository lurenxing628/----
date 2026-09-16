"""ET paired real connections and durable, isolated schema31 evidence."""

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.workbench_run_job import durable_value
from core.services.workbench.run_input_rows import batch_model, operation_model
from tests.workbench.piece_chain_support import piece_layout
from tests.workbench.plan_catalog_support import candidate, scenario
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.trial_support import connect


@pytest.fixture(name="tmp_path")
def stable_tmp_path(request):
    root = Path(tempfile.mkdtemp(prefix="aps-et-piece-",
                                dir=os.environ.get("APS_ET_EVIDENCE_ROOT")))
    write_evidence(root, "test", {"nodeid": request.node.nodeid})
    print("ET stable evidence:", root)
    return root


def write_evidence(root, name, value):
    (root / (name + ".json")).write_text(
        json.dumps(durable_value(value), indent=2, ensure_ascii=True), encoding="utf-8")


def open_connection(path, kind):
    return get_connection(str(path)) if kind == "production" else connect(path)


@pytest.fixture(params=("ordinary", "production"))
def production_case(trial_case, request):
    original = trial_case
    case = JobCase(open_connection(original.path, request.param))
    case.path, case.op_id, case.app = original.path, original.op_id, original.app
    case.connection_kind = request.param
    try:
        yield case
    finally:
        case.conn.close()


def reopen(case):
    conn = open_connection(case.path, case.connection_kind)
    case.conn.close()
    replacement = JobCase(conn)
    replacement.path, replacement.op_id, replacement.app = case.path, case.op_id, case.app
    replacement.connection_kind = case.connection_kind
    return replacement


def seed_history(case):
    ids = piece_layout(case)
    case.batch("B2", quantity=1)
    rival = case.operation(batch="B2", seq=10, unit_hours=.5)
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-09' WHERE batch_id IN ('B1','B2')")
    case.conn.commit()
    for version in (1, 2, 3, 4):
        case.plan(version, [ids[None, 10]], start="2026-09-09T08:00:00", end="2026-09-09T08:45:00")
    candidate(case.conn, 3, "critical_best", op_id=ids[None, 10])
    scenario(case.conn, "et-old-scene", 3, op_id=ids[None, 10])
    case.conn.commit()
    receipt = case.command("create", case.task(4, ids[None, 10]), case.values(3,
        actual_end="2026-09-09T08:45:00", effective_processing_hours=.75))
    assert receipt["ok"], receipt
    return ids, rival, receipt


def raw_differences(conn, prepared):
    differences = []
    sources = (("Batches", prepared.batches.values(), "batch_id", batch_model),
               ("BatchOperations", prepared.operations, "id", operation_model))
    for table, models, identity, build in sources:
        for model in models:
            left = asdict(model)
            row = conn.execute("SELECT * FROM " + table + " WHERE " + identity + "=?",
                               (left[identity],)).fetchone()
            right = asdict(build(dict(row)))
            for field, value in left.items():
                current = right[field]
                if type(value) is not type(current) or value != current:
                    differences.append({"table": table, "identity": left[identity], "field": field,
                        "prepared_type": type(value).__name__, "prepared_value": repr(value),
                        "current_type": type(current).__name__, "current_value": repr(current)})
    return differences


def assert_raw_date_differences(case, prepared):
    differences = raw_differences(case.conn, prepared)
    write_evidence(case.path.parent, "raw-differences", differences)
    expected = {(batch, field) for batch in ("B1", "B2") for field in ("due_date", "ready_date")}
    if case.connection_kind == "production":
        assert {(row["identity"], row["field"]) for row in differences} == expected
        assert all((row["prepared_type"], row["current_type"]) == ("str", "date") for row in differences)
    else:
        assert differences == []


def assert_official_rows(case, ids, rival):
    for version in (5, 6):
        row = case.conn.execute("SELECT start_time,end_time,lock_status FROM Schedule WHERE version=? AND op_id=?",
                                (version, ids[None, 10])).fetchone()
        assert tuple(row) == ("2026-09-09 08:00:00", "2026-09-09 08:45:00", "locked")
    assert case.conn.execute("SELECT start_time FROM Schedule WHERE version=6 AND op_id=?",
                             (ids[None, 40],)).fetchone()[0] == "2026-09-09 13:00:00"
    assert {row[0] for row in case.conn.execute("SELECT op_id FROM Schedule WHERE version=6")} == set(ids.values()) | {rival}
    assert case.conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 32
    assert not case.conn.execute("PRAGMA foreign_key_check").fetchall()


def assert_all_old_rows_retained(before, after):
    assert set(before) == set(after)
    append_only = {"Schedule", "ScheduleHistory", "ScheduleVersionSeq", "OperationLogs",
                   "WorkbenchCommandReceipts", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
                   "WorkbenchDashboardItems"} | set(RUN_TABLES) | set(TRIAL_TABLES)
    clocks = {"sqlite_sequence", "WorkbenchPlanIdentityClock"}
    for table, rows in before.items():
        if table in clocks:
            continue
        if table in append_only:
            current = {row[0]: row for row in after[table]}
            assert all(current.get(row[0]) == row for row in rows), table
        else:
            assert after[table] == rows, table

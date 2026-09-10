"""R1-H characterization using private file-backed SQLite and all-table oracles."""

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from flask import Blueprint, g

from core.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_master_overview import MasterOverviewScope
from core.services.process.part_service import PartService
from core.services.process.workflow_state import record_confirmation, workflow_snapshot
from core.services.workbench.master_overview import MasterOverviewService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_route_preview import ProcessRoutePreviewService
from core.services.workbench.resource_readiness import _checked_workflow, process_readiness
from tests.workbench.process_query_support import ref_for, seed_process
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked_quota_case
from tests.workbench.process_quota_protection_support import quota_case as _quota_case
from tests.workbench.process_route_support import all_table_snapshot, read_only_probe
from tests.workbench.process_stage_api_support import StageAPI, rejected
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case
from web.routes.process_parts import update_internal_hours
from web.routes.workbench.process_reads import register_process_read_routes
from web.routes.workbench.process_writes import register_process_write_routes


@pytest.fixture
def private_process_db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "r1-h-process.sqlite"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    schema = Path(__file__).resolve().parents[2] / "schema.sql"
    conn.executescript(schema.read_text(encoding="utf-8"))
    seed_process(conn)
    conn.execute("ALTER TABLE PartOperations ADD COLUMN r1_h_original BLOB")
    conn.execute("UPDATE PartOperations SET r1_h_original=?,created_at='2001-02-03 04:05:06'",
                 (sqlite3.Binary(b"original\x00\xff"),))
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


@pytest.mark.parametrize("values", [
    {"view": []}, {"domain": False}, {"status": "ready"}, {"sort": "unknown"},
    {"direction": 1}, {"query": None}, {"query": "x" * 1001}, {"query": "\x00"},
    {"size": True}, {"size": 21}, {"column_filters": []},
    {"view": "issues", "column_filters": {"relation_count": "0"}},
    {"column_filters": {"evidence": 0}}, {"column_filters": {"evidence": "\x00"}},
    {"column_filters": {"evidence": "x" * 1001}},
])
def test_scope_keeps_strict_types_and_view_specific_columns(values):
    with pytest.raises(WorkbenchCommandRejected) as caught:
        MasterOverviewScope(**values)
    assert caught.value.code == "invalid_input" and caught.value.status == 400


@pytest.mark.parametrize("view,column", [("issues", "evidence"), ("entities", "relation_count")])
def test_scope_retains_exact_search_text_at_boundary(view, column):
    original = " " + "x" * 998 + " "
    scope = MasterOverviewScope(view=view, query=original, column_filters={column: original})
    assert scope.values()["query"] == original
    assert scope.values()["column_filters"] == {column: original}


def test_real_stage_evidence_is_readonly_and_never_inferred(private_process_db):
    conn = private_process_db
    for expected, action in (("source", None), ("source", "route"),
                             ("hours", "source"), ("ready", "hours")):
        if action is not None:
            with TransactionManager(conn).transaction(begin_immediate=True):
                record_confirmation(conn, "PROC-001", action, "R1-H")
        before = all_table_snapshot(conn)
        conn.execute("PRAGMA query_only=ON")
        try:
            record = workflow_snapshot(conn)["PROC-001"]
            assert _checked_workflow(record) is record["workflow"]
            assert record["workflow"]["stage"] == expected
            assert record["workflow"]["ready"] is (expected == "ready")
            readiness = process_readiness(conn, 5)
        finally:
            conn.execute("PRAGMA query_only=OFF")
        assert readiness["counts"]["ready"] == int(expected == "ready")
        assert all_table_snapshot(conn) == before


@pytest.mark.parametrize("stage,patch", [
    ("route", {"confirmed_at": None}), ("route", {"confirmed_at": " "}),
    ("source", {"confirmed_by": " "}), ("source", {"confirmed_by": 1}),
    ("hours", {"state": "unconfirmed"}),
])
def test_damaged_confirmation_evidence_cannot_mean_ready(private_process_db, stage, patch):
    conn = private_process_db
    with TransactionManager(conn).transaction(begin_immediate=True):
        for name in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", name, "R1-H")
    record = deepcopy(workflow_snapshot(conn)["PROC-001"])
    record["workflow"][stage].update(patch)
    with pytest.raises(RuntimeError):
        _checked_workflow(record)


@pytest.mark.parametrize("mode", ["text", "rows"])
def test_route_difference_keeps_raw_unknown_and_read_transaction(private_process_db, mode):
    conn = private_process_db
    body = {"mode": "text", "route_raw": "10车削;20待建工种;40检验"} if mode == "text" else {
        "mode": "rows", "rows": [{"seq": 10, "op_type_name": "车削"},
                                 {"seq": 20, "op_type_name": "待建工种"},
                                 {"seq": 40, "op_type_name": "检验"}]}
    original_input, before = deepcopy(body), all_table_snapshot(conn)
    reader, previewer = WorkbenchProcessQueryService(conn), ProcessRoutePreviewService(conn)
    with reader.read_snapshot(), previewer.reference_snapshot(), read_only_probe(conn):
        preview = previewer.preview(body)
        unchanged = deepcopy(preview)
        result = reader.route_difference(ref_for(conn), preview)
        assert conn.in_transaction and preview == unchanged and body == original_input
        assert result["changes"] == {"added": [40], "removed": [30],
                                     "retained": [10], "same_sequence_changed": [20]}
        assert result["counts"] == {"operations": 3, "recognized": 2, "unknown": 1}
        assert result["can_confirm_route"] and result["write_context"] is None
        assert result["operations"][1]["source_suggestion"] is None
        assert result["operations"][1]["issues"][0]["code"] == "unknown_op_type"
    assert all_table_snapshot(conn) == before and not conn.in_transaction


def test_invalid_legacy_sequence_is_not_renumbered_or_dropped(private_process_db):
    conn = private_process_db
    conn.execute("UPDATE PartOperations SET seq='bad-sequence' WHERE part_no='PROC-001' AND seq=10")
    conn.commit()
    before = all_table_snapshot(conn)
    reader = WorkbenchProcessQueryService(conn)
    with reader.read_snapshot(), read_only_probe(conn):
        preview = ProcessRoutePreviewService(conn).preview({"mode": "text", "route_raw": "10车削20热处理"})
        result = reader.route_difference(ref_for(conn), preview)
    assert not result["can_confirm_route"]
    assert "legacy_sequence_invalid" in {item["code"] for item in result["diagnostics"]}
    assert result["baseline"] == {"operation_count": 3, "external_group_count": 1,
                                  "has_published_template": True}
    assert result["changes"]["added"] == [10] and result["changes"]["removed"] == [30]
    assert all_table_snapshot(conn) == before


@pytest.mark.parametrize("damage,expected", [
    ("merged-retained", {"operation.retained_days"}),
    ("invalid-range", {"group.invalid"}),
    ("foreign-group", {"operation.group", "operation.days"}),
])
def test_external_group_evidence_and_original_days_survive(private_process_db, damage, expected):
    conn = private_process_db
    if damage == "merged-retained":
        conn.execute("UPDATE PartOperations SET ext_days=-2 WHERE source='external'")
    elif damage == "invalid-range":
        conn.execute("UPDATE ExternalGroups SET start_seq=21 WHERE group_id='PROC-G'")
    else:
        conn.execute("UPDATE ExternalGroups SET part_no='PROC-002' WHERE group_id='PROC-G'")
        conn.execute("UPDATE PartOperations SET ext_days=NULL WHERE source='external'")
    conn.commit()
    before = all_table_snapshot(conn)
    reader = MasterOverviewService(conn)
    with reader.read_snapshot():
        entity = reader.resolve("route", ref_for(conn))
    issues = {row["rule"]: row for row in entity["issues"]}
    assert expected <= set(issues)
    operation_id = conn.execute("SELECT id FROM PartOperations WHERE source='external'").fetchone()[0]
    operation_ref = ref_for(conn, "template_operation", str(operation_id))
    for rule in expected:
        assert issues[rule]["target"]["context"]["template_operation_ref"] == operation_ref
    if damage == "invalid-range":
        assert issues["group.invalid"]["target"]["context"]["template_external_group_ref"] == ref_for(
            conn, "template_external_group", "PROC-G")
    if damage != "foreign-group":
        period = next(row for row in entity["fields"] if row["source"] == "ExternalGroups.total_days")
        assert period["value"] == 6.75
    json.dumps(entity, allow_nan=False)
    assert all_table_snapshot(conn) == before


def test_hours_failure_rolls_back_trigger_write_and_preserves_input(private_process_db):
    conn = private_process_db
    conn.execute("""CREATE TEMP TRIGGER r1_h_fail_hours AFTER UPDATE OF unit_hours ON PartOperations
        BEGIN UPDATE Parts SET remark='must roll back' WHERE part_no=NEW.part_no;
        SELECT RAISE(ABORT,'R1-H storage failure'); END""")
    conn.commit()
    before, statements = all_table_snapshot(conn), []
    original = [" PROC-001 ", "10", " 0.5 ", " 2.5 "]
    conn.set_trace_callback(statements.append)
    with pytest.raises(AppError):
        PartService(conn).update_internal_hours(*original)
    conn.set_trace_callback(None)
    assert "BEGIN IMMEDIATE" in statements and "ROLLBACK" in statements
    assert original == [" PROC-001 ", "10", " 0.5 ", " 2.5 "]
    assert all_table_snapshot(conn) == before and not conn.in_transaction


@pytest.fixture
def locked_process_api(locked_quota_case):
    case = locked_quota_case
    case.app.config["DATABASE_PATH"] = case.db_path
    bp = Blueprint("workbench", __name__)
    register_process_read_routes(bp)
    register_process_write_routes(bp)
    case.app.register_blueprint(bp)
    case.app.add_url_rule("/legacy/parts/<part_no>/ops/<int:seq>/hours",
                          view_func=update_internal_hours, methods=["POST"])
    case.app.add_url_rule("/legacy/parts/<part_no>", "process.part_detail", lambda part_no: part_no)

    @case.app.before_request
    def database():
        g.db = case.conn

    return case, StageAPI(case.app.test_client())


def test_legacy_hours_request_preserves_lock_rejection_and_original_rows(locked_process_api):
    case, api = locked_process_api
    original = {"setup_hours": " 8 ", "unit_hours": " 99 "}
    before = all_table_snapshot(case.conn)
    # This legacy view propagates the domain error; it is not an api_endpoint.
    with pytest.raises(WorkbenchCommandRejected) as caught:
        api.client.post("/legacy/parts/P1/ops/1/hours", data=original)
    assert caught.value.code == "calibration_quota_locked" and caught.value.status == 409
    assert all_table_snapshot(case.conn) == before and not case.conn.in_transaction
    assert original == {"setup_hours": " 8 ", "unit_hours": " 99 "}
    response = api.client.post("/legacy/parts/P1/ops/1/hours", data={"setup_hours": " 8 ", "unit_hours": " 3 "})
    assert response.status_code == 302
    row = case.conn.execute("SELECT * FROM PartOperations WHERE part_no='P1' AND seq=1").fetchone()
    assert row["setup_hours"] == 8 and row["unit_hours"] == 3 and row["cw_hidden"] == b"hidden\x00\xff"
    after = all_table_snapshot(case.conn)
    assert before[0] == after[0]
    for table in before[1]:
        if table not in ("PartOperations", "WorkbenchEntityRefs"):
            assert before[1][table] == after[1][table], table


def test_workbench_hours_api_rejects_locked_change_without_any_write(locked_process_api):
    case, api = locked_process_api
    payload = api.hours(code="P1")
    payload["operations"][0].update(setup_hours=8, unit_hours=99)
    body = api.body("hours_confirm", payload, code="P1")
    before = all_table_snapshot(case.conn)
    rejected(api.post("hours_confirm", body, code="P1"), "calibration_quota_locked", 409)
    assert all_table_snapshot(case.conn) == before and not case.conn.in_transaction

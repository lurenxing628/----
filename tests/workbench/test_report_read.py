"""Real domain reads, exact identity/cohort semantics, no GET repairs."""

import pytest
from flask import g

from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_api_support import BASE, make_api
from tests.workbench.report_api_support import report_api as _report_api


def test_real_current_plan_unknowns_and_ten_minute_boundary(report_api):
    data = report_api.read()["data"]
    assert data["plan"]["is_current_official"]
    assert data["summary"]["operations"] == 23
    assert data["summary"]["confirmed_due"] == 2
    assert data["summary"]["due_on_time"] == 1
    assert data["summary"]["finish_late"] == 1
    assert data["summary"]["unreported"] == 20
    assert data["summary"]["unclosed_due"] == 21
    assert data["summary"]["effective_processing_hours"] is None
    assert data["capabilities"]["state"] == "partial"
    assert data["rows"][0]["completion_basis"] == "legacy_finish_event"
    assert data["rows"][2]["confirmed_finish"] is None


def test_finish_date_is_not_overlap_and_actual_resource_selects_whole_operation(report_api):
    empty = report_api.read(plan_finish_date_from="2026-09-01", plan_finish_date_to="2026-09-01")
    assert empty["data"]["rows"] == []
    assert empty["data"]["summary"]["completion_rate"] is None
    first = report_api.read()
    second_machine = next(row["ref"] for row in first["data"]["choices"]["machine"] if row["label"] == "二号设备")
    data = report_api.read(topic="records", resource_type="machine", resource_ref=second_machine)["data"]
    assert data["summary"]["operations"] == 1 and len(data["rows"]) == 2
    assert all(row["report_ref"] is None and row["report_no"] is None for row in data["rows"])
    assert data["rows"][1]["quantity_done"] == 1


def test_paging_sort_and_detail_share_scope_and_asof(report_api):
    first = report_api.read(size=10)
    token = first["meta"]["snapshot_ref"]
    second = report_api.read(size=10, page=2, snapshot_ref=token)
    assert second["meta"]["as_of"] == first["meta"]["as_of"]
    assert second["data"]["summary"] == first["data"]["summary"]
    assert len(second["data"]["rows"]) == 10 and second["data"]["page"]["total"] == 23
    op = first["data"]["rows"][0]["operation_ref"]
    detail = report_api.read("/operations/" + op, snapshot_ref=token)
    assert detail["data"]["detail"]["operation"]["operation_ref"] == op
    assert len(detail["data"]["detail"]["records"]) == 2
    assert_error(report_api.get(query="no-match", snapshot_ref=token), "snapshot_stale")
    with report_api.db() as conn:
        conn.execute("UPDATE OperationExecutionEvents SET remark='new fact' WHERE id=(SELECT MIN(id) FROM OperationExecutionEvents)")
    assert_error(report_api.get(snapshot_ref=token), "snapshot_stale")


@pytest.mark.parametrize("role,version", [("critical_best", 3), ("adopted", 1)])
def test_candidate_and_history_never_substitute_actual(report_api, role, version):
    assert_error(report_api.get(plan_ref=report_api.ref(version, role)), "plan_not_current_official")


@pytest.mark.parametrize("query", [{"source": "demo"}, {"plan_role": "adopted"}, {"scenario_id": "x"},
    {"range_start": "2026-09-01"}, {"plan_finish_date_from": "2026-09-01"},
    {"plan_finish_date_from": "2026-02-30", "plan_finish_date_to": "2026-03-02"},
    {"page": "1.5"}, {"size": "500"}, {"sort": "op_id"}, {"focus": "made_up"}])
def test_invalid_scope_is_not_ignored(report_api, query):
    assert_error(report_api.get(**query), "invalid_input", 400)


def test_zero_writes_restart_and_missing_identity(report_api, monkeypatch):
    before = report_api.state()
    first = report_api.read()
    for topic in ("records", "machines", "people", "quality"):
        report_api.read(topic=topic, snapshot_ref=first["meta"]["snapshot_ref"])
    assert report_api.state() == before
    assert not any(sql.lstrip().split()[0].upper() in ("UPDATE", "INSERT", "DELETE", "REPLACE", "CREATE") for sql in report_api.statements)
    restarted = make_api(report_api.path)
    def persisted_fields(rows):
        return [{key: value for key, value in row.items() if key != "elapsed_since_planned_minutes"} for row in rows]

    assert persisted_fields(restarted.read()["data"]["rows"]) == persisted_fields(first["data"]["rows"])
    assert_error(restarted.get(snapshot_ref=first["meta"]["snapshot_ref"]), "snapshot_stale")
    with report_api.db() as conn:
        intact = list(conn.iterdump())
        assert intact == before
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        conn.execute("BEGIN")
        try:
            # Keep the FK damage uncommitted and let the real HTTP reader see it.
            conn.execute("PRAGMA defer_foreign_keys=ON")
            conn.execute("DELETE FROM WorkbenchTaskRefs WHERE plan_ref=?", (first["data"]["plan"]["plan_ref"],))
            damaged, changes = list(conn.iterdump()), conn.total_changes
            assert damaged != intact
            assert not conn.execute("SELECT 1 FROM WorkbenchTaskRefs WHERE plan_ref=?",
                                    (first["data"]["plan"]["plan_ref"],)).fetchall()
            assert conn.execute("PRAGMA foreign_key_check").fetchall()
            conn.execute("PRAGMA query_only=ON")

            def bind_damaged_fixture():
                g.db = conn

            with monkeypatch.context() as patch:
                patch.setitem(report_api.app.before_request_funcs, None, [bind_damaged_fixture])
                patch.setitem(report_api.app.teardown_request_funcs, None, [])
                assert_error(report_api.get(), "identity_missing")
            assert list(conn.iterdump()) == damaged and conn.total_changes == changes
            assert report_api.state() == intact
        finally:
            conn.rollback()
            conn.execute("PRAGMA query_only=OFF")
        assert list(conn.iterdump()) == intact
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA defer_foreign_keys").fetchone()[0] == 0
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert report_api.state() == before


def test_required_snapshot_and_duplicate_parameter(report_api):
    assert_error(report_api.get(page=2), "snapshot_required", 400)
    assert_error(report_api.get("/export"), "snapshot_required", 400)
    assert_error(report_api.client.get(BASE + "?focus=all&focus=complete"), "invalid_input", 400)
    assert report_api.client.post(BASE).status_code == 405

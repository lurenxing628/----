"""Native launcher enables the shipped point surfaces, never a fixture-only flag."""

from pathlib import Path

from core.infrastructure.database import get_connection
from tests.workbench.run_entrypoint_support import EntryHarness
from tests.workbench.run_entrypoint_support import entrypoint_case as _case  # noqa: F401
from tests.workbench.test_run_adoption_host import BASE, ready_adoption
from tests.workbench.trial_adoption_support import INTENT
from web.bootstrap.launcher_paths import db_scope_lock_path

TRIAL = "/api/workbench/v1/trial"


def post(client, path, value):
    response = client.post(path, json=value)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["ok"], result
    return result


def read_point(client, plan):
    response = client.get("/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    task, = data["tasks"]
    assert task["event_kind"] == "point" and task["start"] == task["end"]
    assert task["duration_seconds"] == 0 and task["occupies_resources"] is False
    assert data["plan_span"]["end_inclusive"] is True
    for route, field in (("/api/workbench/v1/actual-gantt", "items"),
                         ("/api/workbench/v1/execution/tasks", "tasks")):
        response = client.get(route, query_string={"plan_ref": plan["plan_ref"]})
        assert response.status_code == 200, response.get_json()
        item, = response.get_json()["data"][field]
        actual_task = item["task"] if field == "items" else item
        assert actual_task["task_ref"] == task["task_ref"]
        assert actual_task["operation_ref"] == task["operation_ref"]
        assert actual_task["event_kind"] == "point"
        assert item["execution"]["confirmed_finish"] is None
    return task


def test_managed_point_candidate_then_trial_adoption_and_shutdown(job_case, tmp_path, monkeypatch):
    case, observed = job_case, {}
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0 WHERE id=?", (case.op_id,))
    case.conn.commit()
    raw = [tuple(row) for row in case.conn.execute("SELECT * FROM BatchOperations ORDER BY id")]

    def serve(app, *_):
        assert app.config["WORKBENCH_POINT_RENDERING_ENABLED"] is True
        client = app.test_client()
        candidate_ref, body = ready_adoption(app, case, "point-host-adopt-0001")
        first = post(client, BASE + candidate_ref + "/adopt", body)
        assert post(client, BASE + candidate_ref + "/adopt", body)["receipt_ref"] == first["receipt_ref"]
        first_plan = first["data"]["official_plan"]
        original = read_point(client, first_plan)
        source = {"base": {"plan_ref": first_plan["plan_ref"]}}
        preview = post(client, TRIAL + "/drafts/preview", source)["data"]
        draft = post(client, TRIAL + "/drafts", {"input": source, "request_key": "point-host-draft-0001",
                     "write_token": preview["write_context"]["write_token"]})["data"]
        task, = draft["tasks"]
        draft = post(client, TRIAL + "/drafts/" + draft["draft_ref"] + "/change", {
            "input": {"task_ref": task["task_ref"], "machine_ref": task["machine_ref"],
                      "operator_ref": task["operator_ref"], "start": "2026-09-09T13:00:00"},
            "request_key": "point-host-move-0001", "write_token": draft["write_context"]["write_token"]})["data"]
        saved = post(client, TRIAL + "/drafts/" + draft["draft_ref"] + "/save", {
            "input": {"name": "Managed point scenario"}, "request_key": "point-host-save-0001",
            "write_token": draft["write_context"]["write_token"]})["data"]
        target = TRIAL + "/scenarios/" + saved["scenario_ref"]
        preview = post(client, target + "/adopt-preview", {})["data"]
        assert preview["validation"]["can_adopt"], preview
        body = {"input": INTENT, "request_key": "point-host-adopt-0002", "write_token": preview["write_context"]["write_token"]}
        second = post(client, target + "/adopt", body)
        replay = post(client, target + "/adopt", body)
        assert replay["replayed"] and replay["receipt_ref"] == second["receipt_ref"]
        changed = read_point(client, second["data"]["official_plan"])
        assert changed["operation_ref"] == original["operation_ref"] and changed["task_ref"] != original["task_ref"]
        assert changed["start"] == changed["end"] == "2026-09-09T13:00:00"
        assert read_point(client, first_plan) == original
        observed["app"] = app

    harness = EntryHarness(case, tmp_path, monkeypatch, serve)
    try:
        assert harness.run() == 0
        assert observed["app"].config["WORKBENCH_POINT_RENDERING_ENABLED"] is False
        with get_connection(str(case.path)) as conn:
            assert [tuple(row) for row in conn.execute("SELECT * FROM BatchOperations ORDER BY id")] == raw
            assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 2
            assert conn.execute("SELECT COUNT(*) FROM Schedule WHERE start_time=end_time").fetchone()[0] == 2
            assert conn.execute("SELECT COUNT(*) FROM WorkbenchProductionReports").fetchone()[0] == 0
        harness.exit()
        assert not Path(db_scope_lock_path(str(case.path))).exists()
    finally:
        harness.cleanup()

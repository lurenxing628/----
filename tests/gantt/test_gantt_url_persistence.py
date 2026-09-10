"""LEG-035..041: retired controls cannot execute; canonical reads keep exact identity and time."""

from __future__ import annotations

from contextlib import closing

from core.infrastructure.database import get_connection
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests._support.gantt_retirement import _business_state, _canonical_workspace
from tests.workbench.plan_read_support import seed_plans


def _seed(db_path):
    from core.services.scheduler.config.config_service import ConfigService
    from core.services.system.system_config_service import SystemConfigService
    with closing(get_connection(db_path)) as conn:
        seed_plans(conn)
        ConfigService(conn).ensure_defaults()
        SystemConfigService(conn).ensure_defaults(backup_keep_days_default=7)
        conn.commit()
        return WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(3, "adopted"))


def _assert_retired(client, query):
    response = client.get("/scheduler/gantt", query_string=query)
    assert response.status_code == 410, response.get_data(as_text=True)
    assert "Location" not in response.headers and response.headers["Cache-Control"] == "no-store"
    html = response.get_data(as_text=True)
    assert "旧入口已退役" in html and "未忽略条件后跳转" in html
    for old in ('id="ganttZoomLevel"', 'id="ganttZoomFormValue"', 'id="ganttZoomWarning"',
                'data-gantt-mode="view"', 'data-zoom-level="', 'id="ganttColorMode"',
                'id="ganttFilterBatch"', "/static/js/", "/static/css/"):
        assert old not in html


def test_gantt_url_persistence_contract(app_client, db_env) -> None:
    reference = _seed(db_env)
    before = _business_state(app_client)
    query = {"version": "3", "plan_role": "adopted", "start_date": "2026-09-09", "end_date": "2026-09-10"}
    # The old state/form/link assertions map one-for-one to refusal of their controls.
    controls = (
        ("gantt_zoom", "fifteen-minute"), ("gantt_color", "status"),
        ("gantt_batch", "B001"), ("gantt_batch", "B002"), ("gantt_batch", "B003"),
        ("gantt_resource", "MC01"), ("gantt_resource", "MC02"), ("gantt_resource", "OP02"),
        ("gantt_overdue", "1"), ("gantt_external", "1"), ("gantt_deps", "process"),
        ("gantt_hcc", "0"), ("gantt_vm", "Week"), ("gantt_zoom", "bad"),
        ("gantt_zoom", "five-minute"), ("view", "machine"), ("view", "operator"),
    )
    for key, value in controls:
        _assert_retired(app_client, dict(query, **{key: value}))
    _assert_retired(app_client, dict(query, gantt_zoom="fifteen-minute", gantt_color="status",
                                    gantt_batch="B001", gantt_resource="MC01", gantt_overdue="1",
                                    gantt_external="1", gantt_deps="process", gantt_hcc="0"))
    context, payload = _canonical_workspace(app_client, query)
    assert context == {"plan_ref": reference, "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-11T00:00:00"}
    tasks = payload["data"]["tasks"]
    assert len(tasks) == 1 and tasks[0]["plan_ref"] == reference
    assert tasks[0]["start"] == "2026-09-09T22:30:00" and tasks[0]["end"] == "2026-09-10T06:30:00"
    assert {row["kind"] for row in payload["data"]["resources"]} >= {"machine", "operator"}
    for key, value in (("gantt_batch", "B002"), ("gantt_resource", "MC02"), ("view", "operator")):
        unsupported = app_client.get("/api/workbench/v1/plans/" + reference + "/workspace", query_string={key: value})
        assert unsupported.status_code == 400 and unsupported.get_json()["error"]["code"] == "invalid_input"
    # Original week/version contract remains real, even when that week has no tasks.
    week, empty = _canonical_workspace(app_client, {"version": "1", "week_start": "2026-03-02"})
    assert empty["data"]["plan"]["version"] == 1 and empty["data"]["tasks"] == []
    assert week["range_start"] == "2026-03-02T00:00:00" and week["range_end"] == "2026-03-09T00:00:00"
    assert app_client.get("/scheduler/gantt?version=999").status_code == 404
    assert _business_state(app_client) == before

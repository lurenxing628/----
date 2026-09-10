"""LEG-035..041: retired controls cannot execute; canonical reads keep exact identity and time."""

from __future__ import annotations

import json
from contextlib import closing
from html.parser import HTMLParser

from core.infrastructure.database import get_connection
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_read_support import seed_plans


class _Boot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.parts = False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "workbench-boot":
            self.active = True

    def handle_data(self, value):
        if self.active:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def _business_state(client):
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                  if row[0] not in ("OperationLogs", "sqlite_sequence", "SystemJobState")]
        return {name: sorted(repr(tuple(row)) for row in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"'))
                for name in tables}


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


def _canonical_workspace(client, query):
    response = client.get("/scheduler/gantt", query_string=query)
    assert response.status_code == 302, response.get_data(as_text=True)
    target = response.headers["Location"]
    canonical = client.get(target)
    assert canonical.status_code == 200, canonical.get_data(as_text=True)
    parser = _Boot()
    parser.feed(canonical.get_data(as_text=True))
    navigation = json.loads("".join(parser.parts))["navigation"]
    assert navigation["view"] == "gantt"
    context = navigation["context"]
    reference = context["plan_ref"]
    scope = {key: value for key, value in context.items() if key != "plan_ref"}
    workspace = client.get("/api/workbench/v1/plans/" + reference + "/workspace", query_string=scope)
    assert workspace.status_code == 200, workspace.get_data(as_text=True)
    payload = workspace.get_json()
    assert payload["ok"] and payload["data"]["plan"]["plan_ref"] == reference
    assert payload["meta"]["source"] == "production" and payload["meta"]["time_basis"] == "factory_local"
    # Refresh must resolve the same original ref, not the most recent plan.
    refreshed = client.get(target)
    again = _Boot()
    again.feed(refreshed.get_data(as_text=True))
    assert json.loads("".join(again.parts))["navigation"] == navigation
    return context, payload


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

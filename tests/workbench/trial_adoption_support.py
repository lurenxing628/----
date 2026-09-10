"""CQ-owned temporary SQLite helpers; real trial, scheduler, ledger and commands."""

import sqlite3
from collections import Counter

from flask import Blueprint, g

from core.services.workbench.trial_adoption import WorkbenchTrialAdoptionService
from tests.workbench.trial_support import change, connect, create
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.trial_adoption import register_trial_adoption_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

INTENT = {"confirm": True, "reason": "Saved scenario approved", "declared_operator": "Declared planner"}
KEY = "trial-adoption-request-0001"
BASE = "/api/workbench/v1/trial/scenarios/"


def service(conn, enabled=True):
    return WorkbenchTrialAdoptionService(conn, integration_enabled=enabled,
        context_factory=issue_write_context, context_validator=validate_write_context)


def saved_scenario(case, value=None, *, changed=True, suffix="0001"):
    draft = create(case, value, key="cq-trial-create-" + suffix)
    if changed:
        draft = change(case, draft, key="cq-trial-change-" + suffix)["data"]
    return trial_service(case.conn).save(draft["draft_ref"], {"name": "Saved trial " + suffix},
        draft["write_context"]["write_token"], "cq-trial-save-" + suffix)["data"]


def preview(case, saved):
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is True, result
    return result["write_context"]["write_token"]


def api(case, enabled=True, factory=sqlite3.Connection):
    case.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = enabled
    bp = Blueprint("cq_trial_adoption", __name__)
    register_trial_adoption_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = connect(case.path, factory)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client()


def assert_retained(before, after):
    append_only = {"Schedule", "ScheduleHistory", "ScheduleVersionSeq", "OperationLogs",
                   "WorkbenchCommandReceipts", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs"}
    clocks = {"sqlite_sequence", "WorkbenchPlanIdentityClock"}
    assert set(before) == set(after)
    for name, rows in before.items():
        if name == "WorkbenchDashboardItems":
            assert_dashboard_task_appends(before, after)
        elif name in append_only:
            current = {row[0]: row for row in after[name]}
            assert all(current.get(row[0]) == row for row in rows), name
        elif name not in clocks:
            assert after[name] == rows, name


def _appended_source_rows(before, after, table):
    previous = {row[0]: row for row in before[table]}
    current = {row[0]: row for row in after[table]}
    assert len(previous) == len(before[table]) and len(current) == len(after[table]), table
    assert all(current.get(key) == row for key, row in previous.items()), table
    assert len({row[1] for row in after[table]}) == len(after[table]), table
    return [row for key, row in current.items() if key not in previous]


def assert_dashboard_task_appends(before, after):
    # v29 creates exactly two source mappings per new task, not handling history.
    tasks = _appended_source_rows(before, after, "WorkbenchTaskRefs")
    items = _appended_source_rows(before, after, "WorkbenchDashboardItems")
    expected = Counter((("str", category), ("NoneType", None), row[1])
                       for row in tasks for category in ("actual", "downtime"))
    actual = Counter(tuple(row[2:]) for row in items)
    assert actual == expected, "WorkbenchDashboardItems must map exactly the newly appended task refs"
    for row in items:
        kind, value = row[1]
        assert kind == "str" and isinstance(value, str) and len(value) == 48, "dashboard item ref"
        assert set(value) <= set("0123456789abcdef"), "dashboard item ref"


def full_plan(case):
    second = case.operation(seq=2)
    case.plan(1, [case.op_id, second], end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T11:00:00',end_time='2026-09-09T11:45:00' WHERE op_id=?", (second,))
    case.conn.commit()
    return {"base": {"plan_ref": case.plan_ref(1)}}, second

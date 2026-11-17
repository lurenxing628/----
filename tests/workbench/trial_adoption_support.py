"""CQ-owned temporary SQLite helpers; real trial, scheduler, ledger and commands."""

import sqlite3
from collections import Counter
from datetime import datetime

from flask import Blueprint, g

from core.services.workbench.trial.adoption import WorkbenchTrialAdoptionService
from tests.workbench.run_jobs_support import data_context
from tests.workbench.trial_support import change, connect, create
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.trial_adoption import register_trial_adoption_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

INTENT = {"confirm": True, "reason": "Saved scenario approved", "declared_operator": "Declared planner"}
KEY = "trial-adoption-request-0001"
BASE = "/api/workbench/v1/trial/scenarios/"
# Stored resource names readers do not show (``candidate_values.is_stored_text``): empty, a BLOB as a stored JSON
# document holds it, or with NUL. The schema holds a resource name only as ``TEXT NOT NULL``.
BAD_RESOURCE_NAMES = {"empty": "", "blob": {"$sqlite_blob": "TGF0aGU="}, "nul": "Lathe\x00 1"}


def service(conn, enabled=True):
    return WorkbenchTrialAdoptionService(conn, integration_enabled=enabled,
        context_factory=issue_write_context, context_validator=validate_write_context,
        data_context=data_context(conn), clock=datetime.now)


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


def _appended_source_rows(before, after, table):
    previous = {row[0]: row for row in before[table]}
    current = {row[0]: row for row in after[table]}
    assert len(previous) == len(before[table]) and len(current) == len(after[table]), table
    assert all(current.get(key) == row for key, row in previous.items()), table
    assert len({row[1] for row in after[table]}) == len(after[table]), table
    return [row for key, row in current.items() if key not in previous]


def assert_dashboard_task_appends(before, after):
    # v29+ creates exactly two source mappings per new Schedule task, not handling history.
    tasks = _appended_source_rows(before, after, "Schedule")
    items = _appended_source_rows(before, after, "WorkbenchDashboardItems")
    expected = Counter(
        (("str", category), ("NoneType", None), row[3], ("NoneType", None))
        for row in tasks
        for category in ("actual", "downtime")
    )
    actual = Counter(tuple(row[2:]) for row in items)
    assert actual == expected, "WorkbenchDashboardItems must map exactly the newly appended task refs"
    for row in items:
        kind, value = row[1]
        assert kind == "str" and isinstance(value, str) and len(value) == 48, "dashboard item ref"
        assert set(value) <= set("0123456789abcdef"), "dashboard item ref"


def external_operation(case):
    """An external heat treatment by supplier ``S1`` after the case's turning, on its own two-day cycle."""
    from tests.workbench.identity_metadata_support import insert_row

    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Heat treatment','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES ('S1','Supplier')")
    case.conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','EXT')")
    insert_row(case.conn, "ExternalGroups", dict(group_id="EG", part_no="P1", start_seq=2, end_seq=2,
               merge_mode="separate", total_days=None, supplier_id="S1"))
    insert_row(case.conn, "PartOperations", dict(part_no="P1", seq=2, op_type_id="EXT", op_type_name="Heat treatment",
               source="external", supplier_id="S1", ext_group_id="EG", ext_days=2, setup_hours=None, unit_hours=None,
               status="active"))
    return case.operation(seq=2, op_type_id="EXT", op_type_name="Heat treatment", source="external",
                          supplier_id="S1", machine_id=None, operator_id=None, setup_hours=None, unit_hours=None,
                          ext_days=2)


def full_plan(case):
    from tests.workbench.execution_ledger_support import publish_official_plan

    second = case.operation(seq=2)
    publish_official_plan(
        case.conn,
        1,
        [
            {"op_id": case.op_id, "machine_id": "M1", "operator_id": "O1",
             "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T11:00:00"},
            {"op_id": second, "machine_id": "M1", "operator_id": "O1",
             "start_time": "2026-09-09T11:00:00", "end_time": "2026-09-09T11:45:00"},
        ],
    )
    case.conn.commit()
    return {"base": {"plan_ref": case.plan_ref(1)}}, second

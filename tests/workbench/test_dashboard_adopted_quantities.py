"""Dashboard task quantities come from real adopted work, not today's batch."""

import pytest
from flask import Blueprint

from core.services.batch.service import BatchService
from tests.workbench.piece_chain_support import adopt_candidate, adopt_trial, piece_candidate, saved_trial
from tests.workbench.point_downstream_support import ACTUAL, FIELD, app_for, read
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.dashboard import register_dashboard_routes

QUANTITY_FIELDS = ("quantity", "batch_quantity", "quantity_basis", "quantity_reason")
DASHBOARD = "/api/workbench/v1/dashboard"


def _client(case):
    app = app_for(case)
    blueprint = Blueprint("adopted_quantity_dashboard", __name__)
    register_dashboard_routes(blueprint)
    app.register_blueprint(blueprint)
    return app.test_client()


def _read_quantities(client, case, plan_ref):
    before = snapshot(case.conn)
    plan = read(client, "/api/workbench/v1/plans/" + plan_ref + "/workspace")["data"]
    actual = read(client, ACTUAL, plan_ref=plan_ref)["data"]
    field = read(client, FIELD + "/tasks", plan_ref=plan_ref, size=100)["data"]
    merged = read(client, DASHBOARD, size=100)["data"]
    standalone = read(client, DASHBOARD + "/analysis", plan_ref=plan_ref)["data"]
    assert merged["analysis_error"] is None
    assert actual["items_complete"] is True and actual["task_count"] == 8
    assert plan["tasks_complete"] is True and plan["task_count"] == 8
    task_sets = {
        "plan": plan["tasks"], "actual": [item["task"] for item in actual["items"]],
        "field": field["tasks"], "merged": merged["analysis"]["tasks"],
        "standalone": standalone["tasks"],
    }
    result = {}
    for name, tasks in task_sets.items():
        assert len(tasks) == len({task["task_ref"] for task in tasks}) == 8, name
        assert len({task["operation_ref"] for task in tasks}) == 8, name
        assert all(task["plan_ref"] == plan_ref for task in tasks), name
        result[name] = {task["task_ref"]: (task["operation_ref"], task["piece_id"],
                        *(task[key] for key in QUANTITY_FIELDS)) for task in tasks}
    assert snapshot(case.conn) == before
    return result


@pytest.mark.parametrize("adoption", ["candidate", "trial"])
def test_dashboard_retains_adopted_piece_and_common_quantities_after_live_batch_edit(trial_case, adoption):
    case = trial_case
    _, _, candidates = piece_candidate(case, common=True)
    if adoption == "candidate":
        receipt = adopt_candidate(case, candidates[0])
        quantity_basis = "run_admission"
    else:
        _, _, saved = saved_trial(case, {"candidate_ref": candidates[0]})
        receipt = adopt_trial(case, saved)
        quantity_basis = "trial_creation"
    plan_ref = receipt["data"]["official_plan"]["plan_ref"]
    client = _client(case)
    original = _read_quantities(client, case, plan_ref)
    adopted = original["plan"]
    assert sum(row[1] is None for row in adopted.values()) == 2
    assert sum(row[1] is not None for row in adopted.values()) == 6
    for row in adopted.values():
        assert row[2:] == (3 if row[1] is None else 1, 3, quantity_basis, None)
    for name, rows in original.items():
        assert rows == adopted, name

    # This fixture edits current master data through the real domain service.
    # It does not change any captured run, adopted audit, task, or plan row;
    # an older adopted task must retain its original work even after such drift.
    changed = BatchService(case.conn).update("B1", quantity=5)
    assert changed.quantity == 5
    assert case.conn.execute("SELECT quantity FROM Batches WHERE batch_id='B1'").fetchone()[0] == 5
    refreshed = _read_quantities(client, case, plan_ref)
    for name, rows in refreshed.items():
        assert rows == adopted, name

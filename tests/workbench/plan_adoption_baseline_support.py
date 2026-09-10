"""DA-only helpers: real engine/adoptions in temporary file SQLite, never production."""

import json

from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_baseline import build_plan_baseline
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_service
from tests.workbench.run_candidate_support import corrupt_update
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as trial_service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


def adopt_candidate(case, suffix="first"):
    accepted = case.accept(key="da-run-request-" + suffix)
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == "complete", run
    ref = run["candidates"][0]["candidate_ref"]
    svc = candidate_service(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"], preview
    result = svc.adopt(ref, preview["write_context"]["write_token"], "da-adopt-candidate-" + suffix, INTENT)
    assert result["result"] == "committed", result
    return result["data"]["official_plan"]


def adopt_trial(case, official, suffix="second"):
    saved = saved_scenario(case, {"base": {"plan_ref": official["plan_ref"]}}, suffix="da-" + suffix)
    svc = trial_service(case.conn)
    preview = svc.preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    result = svc.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], "da-adopt-trial-" + suffix, INTENT)
    assert result["result"] == "committed", result
    return result["data"]["official_plan"], saved


def read(case, official, start=None, end=None):
    conn = case.conn
    query = WorkbenchPlanQueryService(conn)
    with query.read_snapshot():
        scope = PlanReadScope(official["plan_ref"], start, end)
        repo, entry, _ = query._selected(scope.plan_ref)
        return build_plan_baseline(conn, entry=entry, scope=scope, selected_rows=query._task_rows(repo, entry, scope))


def two_versions(case, source="trial"):
    first = adopt_candidate(case)
    if source == "trial":
        second, _ = adopt_trial(case, first)
    else:
        second = adopt_candidate(case, "second")
    assert (first["version"], second["version"]) == (1, 2)
    return first, second


def mutate_json(conn, table, column, edit, where="1=1", args=()):
    text = conn.execute("SELECT " + column + " FROM " + table + " WHERE " + where, args).fetchone()[0]
    value = json.loads(text)
    edit(value)
    corrupt_update(conn, table, "UPDATE " + table + " SET " + column + "=? WHERE " + where,
                   (json.dumps(value, ensure_ascii=False),) + tuple(args))

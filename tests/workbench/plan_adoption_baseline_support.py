"""DA-only helpers: real engine/adoptions in temporary file SQLite, never production."""

from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan.baseline import build_plan_baseline
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_service
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
        context = PlanReadContext(conn, references=query.references, entities=query.entities)
        with context.read_scope():
            _, entry, _ = context.selected(scope.plan_ref)
            return build_plan_baseline(conn, entry=entry, scope=scope, context=context)


def two_versions(case, source="trial"):
    first = adopt_candidate(case)
    if source == "trial":
        second, _ = adopt_trial(case, first)
    else:
        second = adopt_candidate(case, "second")
    assert (first["version"], second["version"]) == (1, 2)
    return first, second

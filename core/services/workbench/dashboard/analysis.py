"""Standalone dashboard analysis; the first-screen list reuses its own facts."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import reference

from .analysis_projection import project_dashboard_analysis
from .facts import DashboardFacts
from .projection import safe_material
from .service import WorkbenchDashboardService


def read_dashboard_analysis(conn, plan_ref=None, *, query, as_of, binding=None, bind_snapshot=None):
    if plan_ref is not None:
        reference(plan_ref)
    with WorkbenchDashboardService(conn).read_snapshot():
        revisions = DashboardFacts.precheck_binding(conn, query.scope(plan_ref), binding)
        facts = DashboardFacts(conn, as_of, source_revisions=revisions).load(include_candidates=False)
        if plan_ref is not None and (facts.plan_state != "loaded" or facts.plan is None or facts.plan["plan_ref"] != plan_ref):
            raise WorkbenchCommandRejected("snapshot_stale", "原正式计划已变化或无法读取，未切换到其他计划。", 409)
        # 待排池和任务条要按批次查来源编号，留在读快照里；其余投影在读事务结束后只用已读出的事实。
        material = safe_material(facts)
    facts.project()
    state = facts.snapshot_contents()
    if bind_snapshot is not None:
        bind_snapshot(state, facts.now.isoformat(timespec="seconds"))
    data = project_dashboard_analysis(facts, material, query=query)
    # A page changes only the view. The binding covers complete source facts,
    # including revisions and voids, so later pages cannot mix source snapshots.
    return data, state

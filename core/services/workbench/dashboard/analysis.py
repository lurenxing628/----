"""Standalone dashboard analysis; the first-screen list reuses its own facts."""

from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_dashboard import reference

from .analysis_projection import project_dashboard_analysis
from .facts import DashboardFacts, typed
from .projection import safe_material
from .service import WorkbenchDashboardService


def read_dashboard_analysis(conn, plan_ref=None):
    if plan_ref is not None:
        reference(plan_ref)
    with WorkbenchDashboardService(conn).read_snapshot():
        facts = DashboardFacts(conn, datetime.now().replace(microsecond=0)).load()
        if plan_ref is not None and (facts.plan_state != "loaded" or facts.plan is None or facts.plan["plan_ref"] != plan_ref):
            raise WorkbenchCommandRejected("snapshot_stale", "原正式计划已变化或无法读取，未切换到其他计划。", 409)
        # 待排池和任务条要按批次查来源编号，留在读快照里；其余投影在读事务结束后只用已读出的事实。
        material = safe_material(facts)
    data = project_dashboard_analysis(facts.project(), material)
    state = input_fingerprint(typed({"source": facts.fingerprint(), "data": {k: v for k, v in data.items() if k != "as_of"}}))
    return data, state

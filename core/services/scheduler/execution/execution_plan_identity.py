"""Scheduler-owned current official plan identity for execution readers."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.services.common.bounded_plan_query import _PagePlanQueryService
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


def current_execution_plan(conn):
    repo = WorkbenchPlanCatalogRepository(conn)
    version = repo.latest_version()
    if version is None:
        return None
    refs = WorkbenchPlanIdentityRepository(conn)
    try:
        plan_ref = refs.get_plan_ref(WorkbenchPlanLocator(version, "adopted"))
    except WorkbenchPlanReferenceError as exc:
        raise WorkbenchCommandRejected("execution_ledger_unavailable", "当前正式计划永久身份不可用，不能改指其他计划。") from exc
    resolution = _PagePlanQueryService(repo, version).resolve_plan_view(version, "adopted", None)
    identity = resolution.plan_identity
    writable = bool(identity and identity.can_write_feedback)
    return {"plan_ref": plan_ref, "version": version, "kind": "official", "display_name": "当前正式计划",
            "is_current_official": bool(identity and identity.is_current_executable_official_version),
            "completeness": "complete" if writable else "invalid", "source_run_ref": None, "baseline_ref": None,
            "capabilities": {"view": bool(identity), "edit_draft": False, "adopt": False, "report_actual": writable},
            "blocked_reasons": [] if writable else [{"code": "plan_not_writable", "message": "当前正式计划未通过可录入校验。"}]}

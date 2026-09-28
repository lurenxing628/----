"""Read the immutable admission and candidate evidence without installing anything."""

from core.infrastructure.schema_probe import object_sql
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .candidate_projection import candidate_summary, dispositions, scheduled_ids, validate_manifest
from .candidate_store import CandidateStore
from .preflight_dependencies import material_deferred_ids
from .run_policy import require_admission


def require_adoption_schema(conn):
    if workbench_plan_identity_contract_issues(conn):
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "正式计划编号结构不完整，无法采用。请联系维护人员。", 503)
    # The legacy allocator's CREATE IF NOT EXISTS must never become a repair path.
    sql = object_sql(conn, "ScheduleVersionSeq")
    if sql is None or "AUTOINCREMENT" not in sql.upper():
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "排版本号用的结构还没装好，不能采用。请联系维护人员。", 503)


def load_adoption_candidate(conn, candidate_ref):
    store = CandidateStore(conn)
    run_ref = store.candidate_run(candidate_ref)
    run = store.run(run_ref)
    repo = WorkbenchRunRepository(conn)
    require_admission(repo, repo.get(run_ref))
    receipt = store.receipt(run)
    candidates = store.candidates(run_ref)
    validate_manifest(run, candidates, receipt)
    candidate = next(row for row in candidates if row["candidate_ref"] == candidate_ref)
    scope = dispositions(receipt)
    capture = store.capture(run_ref)
    ids = require_candidate_scope(run, candidates, candidate, scope, capture)
    tasks = store.tasks(candidate_ref)
    if len(tasks) != len(ids):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "这个候选方案的工序明细条数对不上，不能采用。请重新排产后再试。")
    return candidate, scope, tasks, capture


def require_candidate_scope(run, candidates, candidate, scope, capture):
    """Same archived scope proof for direct adoption and candidate-based trials."""
    summary = candidate_summary(candidate, scope)
    deferred = material_deferred_ids(scope.values(), capture["input"]) if scope is not None else set()
    stage_scope = bool(deferred) and run["state"] in ("complete", "partial") and all(row["status"] == "completed" for row in candidates)
    if (candidate["status"] != "completed" or
            ((run["state"] != "complete" or summary["completeness"] != "complete") and not stage_scope)):
        raise CandidateAdoptionBlocked("candidate_incomplete", "这次排产或这个候选方案没有排完，不能采用。请重新排产后再试。")
    ids = scheduled_ids(candidate)
    if not ids or scope is None or ids != {row["op_id"] for row in scope.values()} - deferred:
        raise CandidateAdoptionBlocked("candidate_scope_incomplete", "这个候选方案没有排全排产时选定的工序，不能采用。请重新排产后再试。")
    _require_complete_summary(candidate["artifact"], ids)
    return ids


def _require_complete_summary(artifact, ids):
    engine_summary = artifact.get("summary")
    if (type(engine_summary) is not dict or engine_summary.get("success") is not True
            or engine_summary.get("errors") != [] or engine_summary.get("failed_ops") != 0
            or type(engine_summary.get("failed_ops")) is not int
            or type(engine_summary.get("total_ops")) is not int or engine_summary["total_ops"] != len(ids)
            or type(engine_summary.get("scheduled_ops")) is not int
            or engine_summary.get("scheduled_ops") != len(ids)):
        raise CandidateAdoptionBlocked("candidate_unproven", "这个候选方案里有没排上的工序，或者缺少完整结果，不能采用。请重新排产后再试。")

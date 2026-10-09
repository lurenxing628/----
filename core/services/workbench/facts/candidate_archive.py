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
    ids = require_candidate_scope(run, candidate, scope, capture)
    tasks = store.tasks(candidate_ref)
    if len(tasks) != len(ids):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "这个候选方案的工序明细条数对不上，不能采用。请重新排产后再试。")
    return candidate, scope, tasks, capture


def require_candidate_scope(run, candidate, scope, capture):
    """Prove this candidate's scope; a comparison sibling may have exhausted its budget."""
    summary = candidate_summary(candidate, scope)
    deferred = material_deferred_ids(scope.values(), capture["input"]) if scope is not None else set()
    if (run["state"] not in ("complete", "partial") or candidate["status"] != "completed"
            or (summary["completeness"] != "complete" and not deferred)):
        raise CandidateAdoptionBlocked("candidate_incomplete", _incomplete_message(candidate, scope, deferred))
    ids = scheduled_ids(candidate)
    if not ids or scope is None or ids != {row["op_id"] for row in scope.values()} - deferred:
        raise CandidateAdoptionBlocked("candidate_scope_incomplete", "这个候选方案没有排全排产时选定的工序，不能采用。请重新排产后再试。")
    _require_complete_summary(candidate["artifact"], ids)
    return ids


def _incomplete_message(candidate, scope, deferred):
    """按没排完的原因说出路：本次跳过的批次重排还是跳过，要先取消勾选或处理好跳过原因。"""
    if candidate["status"] != "completed":
        return "这个候选方案没有算出结果，不能采用。请看其它候选方案；都不行请到「排产记录」查看原因。"
    skipped = sorted({row["batch_id"] for row in (scope or {}).values()
                      if row["status"] == "skipped" and row["op_id"] not in deferred})
    if skipped:
        names = "、".join(skipped[:5]) + (" 等" if len(skipped) > 5 else "")
        return ("这次排产有批次本次跳过（" + names + "），结果只能查看、不能采用：采用时选中批次的工序要全部排上。"
                "要采用，请回到排产检查取消勾选这些批次，或先按工序明细处理好跳过原因，再重新排产。"
                + _other_gaps(candidate, scope))
    return "这个候选方案有工序没排上，或者缺少完整结果，不能采用。请到「排产记录」查看原因，处理后重新排产。"


def _other_gaps(candidate, scope):
    """跳过批次之外同时还有的没排完原因（与 candidate_summary 判“不完整”同一口径），只取消勾选不够时一并说清。"""
    if _unscheduled_beyond_skipped(candidate, scope):
        return "另外，这个方案里还有别的工序没排上，处理好跳过的批次后还要到「排产记录」查看原因。"
    return ""


def _unscheduled_beyond_skipped(candidate, scope):
    """排产结果的 incomplete_batch_ids 本来就含跳过的批次，只有跳过批次以外的才算另一个原因。"""
    skipped = {row["batch_id"] for row in scope.values() if row["status"] == "skipped"}
    expected = {row["op_id"] for row in scope.values() if row["status"] != "skipped"}
    if expected - (scheduled_ids(candidate) or set()):
        return True
    completion = (candidate["artifact"].get("metrics") or {}).get("completion")
    incomplete = completion.get("incomplete_batch_ids") if type(completion) is dict else None
    return type(incomplete) is list and any(type(item) is not str or item not in skipped for item in incomplete)


def _require_complete_summary(artifact, ids):
    engine_summary = artifact.get("summary")
    if (type(engine_summary) is not dict or engine_summary.get("success") is not True
            or engine_summary.get("errors") != [] or engine_summary.get("failed_ops") != 0
            or type(engine_summary.get("failed_ops")) is not int
            or type(engine_summary.get("total_ops")) is not int or engine_summary["total_ops"] != len(ids)
            or type(engine_summary.get("scheduled_ops")) is not int
            or engine_summary.get("scheduled_ops") != len(ids)):
        raise CandidateAdoptionBlocked("candidate_unproven", "这个候选方案里有没排上的工序，或者缺少完整结果，不能采用。请重新排产后再试。")

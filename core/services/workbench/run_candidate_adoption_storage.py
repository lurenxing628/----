"""Read the immutable admission and candidate evidence without installing anything."""

import hashlib

from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_job import durable_value
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .run_candidate_projection import candidate_summary, dispositions, scheduled_ids, validate_manifest
from .run_candidate_storage import CandidateStore
from .run_jobs_facts import run_baseline, run_execution_projections, run_facts_unchanged


def require_adoption_schema(conn):
    if workbench_plan_identity_contract_issues(conn):
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "正式计划编号结构不完整，无法采用。请联系维护人员。", 503)
    # The legacy allocator's CREATE IF NOT EXISTS must never become a repair path.
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ScheduleVersionSeq'").fetchone()
    if row is None or "AUTOINCREMENT" not in row[0].upper():
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "排版本号用的结构还没装好，不能采用。请联系维护人员。", 503)


def load_adoption_candidate(conn, candidate_ref):
    store = CandidateStore(conn)
    run_ref = store.candidate_run(candidate_ref)
    run = store.run(run_ref)
    repo = WorkbenchRunRepository(conn)
    repo.require_admission(repo.get(run_ref))
    receipt = store.receipt(run)
    candidates = store.candidates(run_ref)
    validate_manifest(run, candidates, receipt)
    candidate = next(row for row in candidates if row["candidate_ref"] == candidate_ref)
    scope = dispositions(receipt)
    summary = candidate_summary(candidate, scope)
    if run["state"] != "complete" or candidate["status"] != "completed" or summary["completeness"] != "complete":
        raise CandidateAdoptionBlocked("candidate_incomplete", "这次排产或这个候选方案没有排完，不能采用。请重新排产后再试。")
    ids = scheduled_ids(candidate)
    if not ids or scope is None or ids != {row["op_id"] for row in scope.values()}:
        raise CandidateAdoptionBlocked("candidate_scope_incomplete", "这个候选方案没有排全排产时选定的工序，不能采用。请重新排产后再试。")
    artifact = candidate["artifact"]
    _require_complete_summary(artifact, ids)
    tasks = store.tasks(candidate_ref)
    if len(tasks) != len(ids):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "这个候选方案的工序明细条数对不上，不能采用。请重新排产后再试。")
    return candidate, scope, tasks, store.capture(run_ref)


def _require_complete_summary(artifact, ids):
    engine_summary = artifact.get("summary")
    if (type(engine_summary) is not dict or engine_summary.get("success") is not True
            or engine_summary.get("errors") != [] or engine_summary.get("failed_ops") != 0
            or type(engine_summary.get("failed_ops")) is not int
            or type(engine_summary.get("total_ops")) is not int or engine_summary["total_ops"] != len(ids)
            or type(engine_summary.get("scheduled_ops")) is not int
            or engine_summary.get("scheduled_ops") != len(ids)):
        raise CandidateAdoptionBlocked("candidate_unproven", "这个候选方案里有没排上的工序，或者缺少完整结果，不能采用。请重新排产后再试。")


def check_admission_current(conn, capture):
    text = capture["facts_text"]
    if type(text) is not str or hashlib.sha256(text.encode("utf-8")).hexdigest() != capture["facts_hash"]:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "排产时记下的数据校验不通过，不能采用，正式计划没有改动。请重新排产后再试。")
    baseline = run_baseline(conn)
    if baseline != capture["baseline"]:
        raise WorkbenchCommandRejected("snapshot_stale", "排产时的正式计划已经变了，这次没有采用，正式计划没有改动。请重新做排产检查。")
    if baseline["version"] is None and conn.execute("SELECT 1 FROM Schedule LIMIT 1").fetchone():
        raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "系统里还有找不到所属版本的正式安排，不能采用。请联系维护人员核对。")
    if conn.execute("SELECT 1 FROM Schedule s WHERE NOT EXISTS "
                    "(SELECT 1 FROM ScheduleHistory h WHERE h.version=s.version) LIMIT 1").fetchone():
        raise CandidateAdoptionBlocked("official_history_inconsistent", "有正式安排找不到所属的版本记录，不能采用。请联系维护人员核对。")
    if not run_facts_unchanged(conn, text, capture["facts_hash"]):
        raise WorkbenchCommandRejected("snapshot_stale", "排产之后，排产范围、报工记录、设备人员或班表有变化，这次没有采用，正式计划没有改动。请重新排产后再试。")
    projections = run_execution_projections(conn, capture["input"])
    _require_official_baseline(baseline, projections)
    if durable_value(projections) != capture["execution"]:
        raise WorkbenchCommandRejected("snapshot_stale", "排产时记下的报工记录已经变了，这次没有采用，正式计划没有改动。请重新排产后再试。")
    return baseline, projections


def _require_official_baseline(baseline, projections):
    if baseline["version"] is None:
        if any(row.plan_identity is not None for row in projections):
            raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "系统里还没有正式计划，但报工记录上挂着计划编号，对不上，不能采用。请联系维护人员核对。")
        return
    for row in projections:
        identity = row.plan_identity
        if (not isinstance(identity, dict) or identity.get("plan_ref") != baseline["plan_ref"]
                or identity.get("version") != baseline["version"] or identity.get("kind") != "official"
                or identity.get("is_current_official") is not True or identity.get("completeness") != "complete"):
            raise CandidateAdoptionBlocked("baseline_not_current_official", "排产时对照的那份计划已经不是当前正式计划，不能采用。请重新做排产检查。")

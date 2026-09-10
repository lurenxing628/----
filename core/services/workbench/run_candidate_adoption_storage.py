"""Read the immutable admission and candidate evidence without installing anything."""

import hashlib

from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_job import durable_value
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .run_candidate_projection import candidate_summary, dispositions, scheduled_ids, validate_manifest
from .run_candidate_storage import CandidateStore
from .run_jobs_facts import capture_run_facts, run_baseline, run_execution_projections


def require_adoption_schema(conn):
    if workbench_plan_identity_contract_issues(conn):
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "正式计划永久身份结构不完整，不能采用，也不会自动修复。", 503)
    # The legacy allocator's CREATE IF NOT EXISTS must never become a repair path.
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ScheduleVersionSeq'").fetchone()
    if row is None or "AUTOINCREMENT" not in row[0].upper():
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "正式版本分配表尚未安装，未启用采用。", 503)


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
        raise CandidateAdoptionBlocked("candidate_incomplete", "运行或候选未完整排完，不能正式采用。")
    ids = scheduled_ids(candidate)
    if not ids or scope is None or ids != {row["op_id"] for row in scope.values()}:
        raise CandidateAdoptionBlocked("candidate_scope_incomplete", "候选安排没有完整覆盖受理工序，不能正式采用。")
    artifact = candidate["artifact"]
    _require_complete_summary(artifact, ids)
    tasks = store.tasks(candidate_ref)
    if len(tasks) != len(ids):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选明细数量不一致，不能采用。")
    return candidate, scope, tasks, store.capture(run_ref)


def _require_complete_summary(artifact, ids):
    engine_summary = artifact.get("summary")
    if (type(engine_summary) is not dict or engine_summary.get("success") is not True
            or engine_summary.get("errors") != [] or engine_summary.get("failed_ops") != 0
            or type(engine_summary.get("failed_ops")) is not int
            or type(engine_summary.get("total_ops")) is not int or engine_summary["total_ops"] != len(ids)
            or type(engine_summary.get("scheduled_ops")) is not int
            or engine_summary.get("scheduled_ops") != len(ids)):
        raise CandidateAdoptionBlocked("candidate_unproven", "候选结果存在失败或缺少完整证明，不能正式采用。")


def check_admission_current(conn, capture):
    text = capture["facts_text"]
    if type(text) is not str or hashlib.sha256(text.encode("utf-8")).hexdigest() != capture["facts_hash"]:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "受理事实快照校验失败，不能采用。")
    baseline = run_baseline(conn)
    if baseline != capture["baseline"]:
        raise WorkbenchCommandRejected("snapshot_stale", "受理时的正式计划已变化，未采用候选，请重新检查排产。")
    if baseline["version"] is None and conn.execute("SELECT 1 FROM Schedule LIMIT 1").fetchone():
        raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "空基线仍有无历史归属的正式排程，不能采用。")
    if conn.execute("SELECT 1 FROM Schedule s WHERE NOT EXISTS "
                    "(SELECT 1 FROM ScheduleHistory h WHERE h.version=s.version) LIMIT 1").fetchone():
        raise CandidateAdoptionBlocked("official_history_inconsistent", "正式安排缺少所属历史版本，不能采用。")
    fingerprint, _ = capture_run_facts(conn)
    if fingerprint != capture["facts_hash"]:
        raise WorkbenchCommandRejected("snapshot_stale", "受理后的输入、执行、资源、日历或其他生产事实已变化，未采用候选。")
    projections = run_execution_projections(conn, capture["input"])
    _require_official_baseline(baseline, projections)
    if durable_value(projections) != capture["execution"]:
        raise WorkbenchCommandRejected("snapshot_stale", "受理时的执行投影已变化，未采用候选。")
    return baseline, projections


def _require_official_baseline(baseline, projections):
    if baseline["version"] is None:
        if any(row.plan_identity is not None for row in projections):
            raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "空正式基线与执行领域计划身份不一致。")
        return
    for row in projections:
        identity = row.plan_identity
        if (not isinstance(identity, dict) or identity.get("plan_ref") != baseline["plan_ref"]
                or identity.get("version") != baseline["version"] or identity.get("kind") != "official"
                or identity.get("is_current_official") is not True or identity.get("completeness") != "complete"):
            raise CandidateAdoptionBlocked("baseline_not_current_official", "受理基线不是可信的当前可执行正式计划，不能采用。")

"""Rebuild exact input and validate stored rows, not the engine completion flag."""

from datetime import datetime
from types import SimpleNamespace

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_run_adoption import CandidateAdoptionBlocked, CandidateAdoptionEvidence
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_execution_persistence_guard import validate_execution_guard_before_persist
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
from core.services.scheduler.schedule_service import ScheduleService
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .piece_adoption import validate_piece_adoption
from .run_candidate_adoption_constraints import validate_adoption_constraints
from .run_candidate_adoption_storage import check_admission_current, load_adoption_candidate, require_adoption_schema
from .run_candidate_storage import CandidateStore
from .run_compute_validation import validate_candidate
from .run_input import prepare_candidate_run_input


def _rows(tasks, candidate, prepared):
    expected = candidate["artifact"]["validated_payload"]["schedule_rows"]
    by_id = {row["op_id"]: row for row in expected}
    refs = {row["op_id"]: row["operation_ref"] for row in prepared.dispositions}
    result, seen = [], set()
    for task in tasks:
        value = dict(task["payload"])
        op_id = value.get("op_id")
        locked = value.pop("locked", None)
        if (type(op_id) is not int or op_id in seen or task["operation_ref"] != refs.get(op_id)
                or type(locked) is not bool or locked != (op_id in prepared.frozen_op_ids)
                or value != by_id.get(op_id)):
            raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选行、原始工序身份或锁定记录不一致。")
        seen.add(op_id)
        for field in ("start_time", "end_time"):
            raw = value[field]
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None or parsed.isoformat() != raw:
                raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选时间不是明确的工厂本地时间。")
            # Schedule's legacy formatter retains seconds only. Do not round a proof.
            if parsed.microsecond:
                raise CandidateAdoptionBlocked("candidate_time_precision_unsupported", "候选含秒以下时间，正式安排无法无损保存，未采用。")
            value[field] = parsed
        if set(value) != {"op_id", "machine_id", "operator_id", "start_time", "end_time", "source"}:
            raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选行字段不完整或存在未知字段。")
        result.append(SimpleNamespace(**value))
    return result


def validate_adoption(conn, candidate_ref):
    try:
        with CandidateStore(conn).snapshot():
            require_adoption_schema(conn)
            candidate, scope, tasks, capture = load_adoption_candidate(conn, candidate_ref)
            baseline, projections = check_admission_current(conn, capture)
            prepared = prepare_candidate_run_input(conn, capture["input"], projections)
            if {row["operation_ref"]: row for row in prepared.dispositions} != scope:
                raise CandidateAdoptionBlocked("candidate_disposition_mismatch", "受理工序范围或前后序与当前事实不一致。")
            rows = _rows(tasks, candidate, prepared)
            payload = validate_candidate(prepared, rows, [])
            _check_artifact_payload(candidate, payload)
            if payload.scheduled_op_ids != {op.id for op in prepared.operations}:
                raise CandidateAdoptionBlocked("candidate_scope_incomplete", "未完整覆盖选中工序，不能采用。")
            svc = ScheduleService(conn)
            _require_official_scope(svc, prepared.prev_version, payload.scheduled_op_ids)
            validate_adoption_payload(conn, prepared, payload)
            snapshot = {"candidate_ref": candidate_ref, "run_ref": candidate["run_ref"],
                        "facts_hash": capture["facts_hash"], "baseline_ref": baseline["plan_ref"],
                        "baseline_version": baseline["version"], "baseline_hash": input_fingerprint(baseline),
                        "candidate_hash": input_fingerprint({"candidate": candidate, "tasks": tasks, "scope": scope}),
                        "validated_hash": input_fingerprint(durable_value(payload))}
            return CandidateAdoptionEvidence(candidate_ref, candidate["run_ref"], baseline, snapshot, prepared, payload)
    except CandidateAdoptionBlocked:
        raise
    except WorkbenchCommandRejected as exc:
        if exc.code in ("candidate_artifact_invalid", "run_result_inconsistent"):
            raise CandidateAdoptionBlocked(exc.code, "候选台账损坏或内容不一致，未启用采用。") from exc
        raise
    except (CandidateRunInputError, AppError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise CandidateAdoptionBlocked("candidate_constraint_unproven", "候选未通过完整事实和约束复核，未启用采用。") from exc


def _require_official_scope(svc, version, scheduled_ids):
    from collections import defaultdict

    latest = _latest_plan_rows(svc, version)
    if not set(latest) <= scheduled_ids:
        raise CandidateAdoptionBlocked("official_scope_not_covered", "候选未覆盖已有正式安排的完整工序范围，请选全相关批次后重新排产。")
    by_version = defaultdict(list)
    for row in latest.values():
        by_version[row["version"]].append(row)
    identities = WorkbenchPlanIdentityRepository(svc.conn)
    for old_version, rows in by_version.items():
        plan_ref = identities.get_plan_ref(WorkbenchPlanLocator(old_version, "adopted"))
        identities.get_task_refs(plan_ref, rows)


def validate_adoption_payload(conn, prepared, payload):
    if any(op.piece_id is not None for op in prepared.operations):
        validate_piece_adoption(conn, prepared=prepared, payload=payload)
        return
    validate_adoption_constraints(conn, prepared, payload)
    validate_execution_guard_before_persist(ScheduleService(conn), validated_schedule_payload=payload,
        execution_guard_state_revisions=prepared.execution_guard_state_revisions,
        execution_facts=prepared.execution_facts, execution_fixed_op_ids=prepared.execution_fixed_op_ids,
        execution_completed_op_ids=prepared.execution_completed_op_ids,
        execution_snapshot_revision=prepared.execution_snapshot_revision,
        execution_snapshot_op_ids=prepared.execution_snapshot_op_ids,
        payload_validation_operations=prepared.operations)


def _check_artifact_payload(candidate, payload):
    artifact = candidate["artifact"]
    expected = durable_value(payload)
    if artifact["validated_payload"] != expected:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选验证记录与明细不一致。")
    results = artifact.get("results")
    if type(results) is not list or len(results) != len(payload.schedule_rows):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选原始引擎结果不完整。")
    fields = ("op_id", "machine_id", "operator_id", "start_time", "end_time", "source")
    original = [{key: row[key] for key in fields} for row in results]
    if original != expected["schedule_rows"]:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选原始引擎结果与保存安排不一致。")

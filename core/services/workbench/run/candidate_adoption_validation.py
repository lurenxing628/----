"""Rebuild exact input and validate stored rows, not the engine completion flag."""

from datetime import datetime
from types import SimpleNamespace

from core.errors import AppError
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked, CandidateAdoptionEvidence
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_execution_persistence_guard import validate_execution_guard_before_persist
from core.services.workbench.facts.candidate_archive import load_adoption_candidate, require_adoption_schema
from core.services.workbench.facts.candidate_projection import uses_task_rows
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.production_capture import ProductionFactsCapture

from .candidate_adoption_constraints import validate_adoption_constraints
from .candidate_adoption_storage import check_admission_current
from .compute_validation import validate_candidate
from .input import prepare_candidate_run_input
from .piece_adoption import validate_piece_adoption
from .preflight_facts import PreflightFacts


def _rows(tasks, candidate, prepared, expected_ids):
    from_tasks = uses_task_rows(candidate["artifact"])
    if expected_ids is None:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选验证范围缺失，不能采用。请重新排产后再试。")
    legacy_rows = None if from_tasks else {row["op_id"]: row for row in candidate["artifact"]["validated_payload"]["schedule_rows"]}
    refs = {row["op_id"]: row["operation_ref"] for row in prepared.dispositions}
    seen = set()
    return [_row_from_task(task, refs, prepared.frozen_op_ids, expected_ids, legacy_rows, seen) for task in tasks]


def _row_from_task(task, refs, frozen_op_ids, expected_ids, legacy_rows, seen):
    """Validate one permanent task against its admission and old-format arrangement witness."""
    value = dict(task["payload"])
    op_id = value.get("op_id")
    locked = value.pop("locked", None)
    if (type(op_id) is not int or op_id in seen or task["operation_ref"] != refs.get(op_id)
            or type(locked) is not bool or locked != (op_id in frozen_op_ids)
            or op_id not in expected_ids or (legacy_rows is not None and not same(value, legacy_rows.get(op_id)))):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选行、原始工序身份或锁定记录不一致。")
    seen.add(op_id)
    for field in ("start_time", "end_time"):
        raw = value[field]
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None or parsed.isoformat() != raw:
            raise CandidateAdoptionBlocked("candidate_artifact_invalid", "这个候选方案里的时间格式不对，不能采用。请重新排产后再试。")
        # Official TEXT storage and every schedule reader preserve this exact instant.
        value[field] = parsed
    if set(value) != {"op_id", "machine_id", "operator_id", "start_time", "end_time", "source"}:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "这个候选方案的工序明细有缺项或多出认不出的项，不能采用。请重新排产后再试。")
    return SimpleNamespace(**value)


def validate_adoption(conn, candidate_ref):
    try:
        with CandidateStore(conn).snapshot():
            require_adoption_schema(conn)
            _run, candidate, scope, tasks, capture, ids = load_adoption_candidate(conn, candidate_ref)
            current_capture = ProductionFactsCapture(conn)
            facts = PreflightFacts(conn, capture=current_capture)
            with facts.snapshot(fingerprint=False):
                baseline, projections = check_admission_current(conn, capture, current_capture=current_capture)
                prepared = prepare_candidate_run_input(conn, capture["input"], projections, capture_fingerprint=False,
                                                       facts=facts, baseline=baseline,
                                                       validated_projections={row.operation_ref: row for row in projections})
                if not same({row["operation_ref"]: row for row in prepared.dispositions}, scope):
                    raise CandidateAdoptionBlocked("candidate_disposition_mismatch", "排产时的工序范围或前后顺序和现在的记录对不上，不能采用。请重新做排产检查。")
                rows = _rows(tasks, candidate, prepared, ids)
                payload = validate_candidate(prepared, rows, [])
                _check_artifact_payload(candidate, payload)
                if payload.scheduled_op_ids != prepared.schedule_output_allowed_op_ids:
                    raise CandidateAdoptionBlocked("candidate_scope_incomplete", "这个候选方案没有排全选中的工序，不能采用。请重新排产后再试。")
                _require_official_scope(prepared.latest_plan_rows, payload.scheduled_op_ids)
                validate_adoption_payload(conn, prepared, payload)
                proof = {"proof_version": "content_refs_v1", "candidate_ref": candidate_ref,
                         "run_ref": candidate["run_ref"], "baseline_ref": baseline["plan_ref"],
                         "baseline_version": baseline["version"]}
                # The candidate and task ledger are permanent. Current production facts,
                # actual rows and constraints are re-read by this same guarded transaction.
                snapshot = proof
                return CandidateAdoptionEvidence(candidate_ref, candidate["run_ref"], baseline, snapshot,
                                                 prepared, payload, proof)
    except CandidateAdoptionBlocked:
        raise
    except WorkbenchCommandRejected as exc:
        if exc.code in ("candidate_artifact_invalid", "run_result_inconsistent"):
            raise CandidateAdoptionBlocked(exc.code, "这次排产的记录读不出来或内容对不上，不能采用，正式计划没有改动。请重新排产后再试。") from exc
        raise
    except (CandidateRunInputError, AppError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise CandidateAdoptionBlocked("candidate_constraint_unproven", "这个候选方案没有通过完整复核，不能采用，正式计划没有改动。请重新排产后再试。") from exc


def _require_official_scope(latest, scheduled_ids):
    # Resource execution preparation has already bound every official row to its permanent task.
    if not official_scope_coverage(latest, scheduled_ids)["covers_official_scope"]:
        raise CandidateAdoptionBlocked("official_scope_not_covered", "候选未覆盖已有正式安排的完整工序范围，请选全相关批次后重新排产。")


def validate_adoption_payload(conn, prepared, payload):
    if any(op.piece_id is not None for op in prepared.operations):
        validate_piece_adoption(conn, prepared=prepared, payload=payload)
        return
    validate_adoption_constraints(conn, prepared, payload)
    validate_execution_guard_before_persist(prepared, validated_schedule_payload=payload)


def _check_artifact_payload(candidate, payload):
    artifact = candidate["artifact"]
    expected = durable_value(payload)
    if uses_task_rows(artifact):
        expected = {key: value for key, value in expected.items() if key not in ("schedule_rows", "assigned_by_op_id")}
        if not same(artifact["validated_payload"], expected):
            raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选验证记录与明细不一致。")
        return
    if not same(artifact["validated_payload"], expected):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选验证记录与明细不一致。")
    results = artifact.get("results")
    if type(results) is not list or len(results) != len(payload.schedule_rows):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选原始引擎结果不完整。")
    fields = ("op_id", "machine_id", "operator_id", "start_time", "end_time", "source")
    original = [{key: row[key] for key in fields} for row in results]
    if not same(original, expected["schedule_rows"]):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选原始引擎结果与保存安排不一致。")

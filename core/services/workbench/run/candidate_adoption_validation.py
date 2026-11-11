"""Rebuild exact input and validate stored rows, not the engine completion flag."""

from dataclasses import fields

from core.errors import AppError
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked, CandidateAdoptionEvidence
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import validate_task_payload
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.production_capture import ProductionFactsCapture

from .candidate_adoption_constraints import validate_adoption_constraints
from .candidate_adoption_storage import check_admission_current
from .input import prepare_business_input
from .piece_adoption import validate_piece_adoption
from .preflight_facts import PreflightFacts


def _rows(tasks, prepared, expected_ids):
    refs = {row["op_id"]: row["operation_ref"] for row in prepared.dispositions}
    seen = set()
    return [_row_from_task(task, refs, prepared.seeds.frozen_op_ids, expected_ids, seen) for task in tasks]


def _row_from_task(task, refs, frozen_op_ids, expected_ids, seen):
    """Validate one permanent task against its admission identity and lock."""
    value = task["payload"]
    op_id, start, end = validate_task_payload(value, seen=seen)
    if (task["operation_ref"] != refs.get(op_id)
            or value["locked"] != (op_id in frozen_op_ids)
            or op_id not in expected_ids):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选行、原始工序身份或锁定记录不一致。")
    return ValidatedScheduleRow(
        op_id=op_id,
        machine_id=value["machine_id"],
        operator_id=value["operator_id"],
        start_time=start,
        end_time=end,
        source=value["source"],
    )


def validate_adoption(conn, candidate_ref):
    try:
        with CandidateStore(conn).snapshot():
            _run, candidate, scope, tasks, capture, ids, generation_facts = load_adoption_candidate(conn, candidate_ref)
            current_capture = ProductionFactsCapture(conn)
            with PreflightFacts.open(conn, capture=current_capture) as facts:
                baseline, projections = check_admission_current(
                    capture,
                    current_capture=current_capture,
                    captured_facts=generation_facts.archive,
                    ledger=facts.ledger,
                )
                prepared = prepare_business_input(
                    conn,
                    capture["input"],
                    projections,
                    facts=facts,
                    baseline=baseline,
                    include_efforts=False,
                )
                if not same({row["operation_ref"]: row for row in prepared.dispositions}, scope):
                    raise CandidateAdoptionBlocked("candidate_disposition_mismatch", "排产时的工序范围或前后顺序和现在的记录对不上，不能采用。请重新做排产检查。")
                rows = _rows(tasks, prepared, ids)
                outcome = validate_adoption_payload(conn, prepared, rows, candidate=candidate)
                proof = {"proof_version": "content_refs_v1", "candidate_ref": candidate_ref,
                         "run_ref": candidate["run_ref"], "baseline_ref": baseline["plan_ref"],
                         "baseline_version": baseline["version"]}
                # The candidate and task ledger are permanent. Current production facts,
                # actual rows and constraints are re-read by this same guarded transaction.
                snapshot = proof
                return CandidateAdoptionEvidence(candidate_ref, candidate["run_ref"], baseline, snapshot,
                                                 prepared, outcome, proof)
    except CandidateAdoptionBlocked:
        raise
    except WorkbenchCommandRejected as exc:
        if exc.code in ("candidate_artifact_invalid", "run_result_inconsistent"):
            raise CandidateAdoptionBlocked(exc.code, "这次排产的记录读不出来或内容对不上，不能采用，正式计划没有改动。请重新排产后再试。") from exc
        raise
    except (CandidateRunInputError, AppError) as exc:
        raise CandidateAdoptionBlocked("candidate_constraint_unproven", "这个候选方案没有通过完整复核，不能采用，正式计划没有改动。请重新排产后再试。") from exc


def require_official_scope(latest, scheduled_ids):
    # Resource execution preparation has already bound every official row to its permanent task.
    if not official_scope_coverage(latest, scheduled_ids)["covers_official_scope"]:
        raise CandidateAdoptionBlocked("official_scope_not_covered", "候选未覆盖已有正式安排的完整工序范围，请选全相关批次后重新排产。")


def validate_adoption_payload(conn, prepared, payload, *, candidate):
    if prepared.piece_scope is not None:
        outcome = validate_piece_adoption(conn, prepared=prepared, payload=payload)
    else:
        outcome = validate_adoption_constraints(prepared, payload)
    validated = outcome.validated_payload
    _check_artifact_payload(candidate, validated)
    if validated.scheduled_op_ids != prepared.allowed_op_ids:
        raise CandidateAdoptionBlocked("candidate_scope_incomplete", "这个候选方案没有排全选中的工序，不能采用。请重新排产后再试。")
    require_official_scope(prepared.latest_plan_rows, validated.scheduled_op_ids)
    return outcome


def _check_artifact_payload(candidate, payload):
    # 安排明细已在任务账本里逐行核对，这里只转换并核对其余验证记录。
    summary = {item.name: getattr(payload, item.name) for item in fields(payload)
               if item.name not in ("schedule_rows", "assigned_by_op_id")}
    if not same(candidate["artifact"]["validated_payload"], durable_value(summary)):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选验证记录与明细不一致。")

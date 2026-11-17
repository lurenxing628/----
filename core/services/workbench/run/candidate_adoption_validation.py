"""Rebuild exact input and validate stored rows, not the engine completion flag."""

from core.errors import AppError
from core.models.content import StoredJsonCorrupt, same
from core.models.workbench_run_adoption import CandidateAdoptionBlocked, CandidateAdoptionEvidence
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.run.schedule_payload_contract import arrangement_row
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_artifact import validated_payload_record
from core.services.workbench.facts.candidate_facts import require_arranged_type
from core.services.workbench.facts.candidate_projection import candidate_origin
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.plan.official_persistence import adopted_label, build_task_snapshot, generation_resource
from core.shared.strict_json import canonical_json

from .candidate_adoption_constraints import validate_adoption_constraints
from .candidate_adoption_storage import check_admission_current
from .input import prepare_business_input
from .piece_adoption import validate_piece_adoption
from .preflight_facts import PreflightFacts

_UNREADABLE = "这次排产的记录读不出来或内容对不上，不能采用，正式计划没有改动。请重新排产后再试。"


def _row_from_task(task, refs, frozen_op_ids, expected_ids):
    """Validate one permanent task against its admission identity and lock.

    ``refs`` gives each operation one ref and a candidate keeps each ref once
    (UNIQUE(candidate_ref, operation_ref)), so no operation can be arranged twice.
    """
    op_id = task["op_id"]
    if (task["operation_ref"] != refs.get(op_id)
            or task["locked"] != (op_id in frozen_op_ids)
            or op_id not in expected_ids):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选行、原始工序身份或锁定记录不一致。")
    return arrangement_row(task)


def _provenance_and_snapshots(candidate_ref, run, candidate, receipt, capture, generation_facts, refs, outcome):
    """``refs`` binds each admitted operation to its ref (the dispositions); the archived operation that ref names
    must be the arranged one (``GenerationFacts.operation``)."""
    origin = candidate_origin(candidate, run, capture)
    base_meta = origin["baseline"]
    provenance = {
        "source_kind": "candidate_adoption",
        "source_ref": candidate_ref,
        "source_label": origin["source_label"],
        "run_ref": run["run_ref"],
        "draft_ref": None,
        "accepted_at": run["accepted_at"],
        "finished_at": run["finished_at"],
        "algorithm_json": canonical_json(origin["algorithm"]),
        "baseline_version": base_meta["version"],
        "baseline_ref": base_meta["baseline_ref"],
        "baseline_kind": base_meta["kind"],
        "baseline_captured_at": base_meta["captured_at"],
        "baseline_captured_task_count": int(base_meta["captured_task_count"]),
        "operation_effort": receipt.operation_effort,
    }
    task_snapshots = {}
    for row in outcome.validated_payload.schedule_rows:
        ref = refs[row.op_id]
        op_archive = generation_facts.operation(ref, row.op_id)
        require_arranged_type(op_archive)
        op_type = generation_facts.operation_type_labels(op_archive["op_type_id"])
        task_snapshots[row.op_id] = build_task_snapshot(
            operation=op_archive,
            batch=generation_facts.related("Batches", op_archive["batch_id"]),
            execution=generation_facts.execution[ref],
            quantity_basis="run_admission",
            op_type_ref=op_type["process_type_ref"],
            op_type_label=adopted_label(op_type["process_type_label"], corrupt),
            machine=generation_resource(generation_facts, "machine", row.machine_id),
            operator=generation_resource(generation_facts, "operator", row.operator_id),
            supplier=generation_resource(generation_facts, "supplier", op_archive["supplier_id"]),
        )
    return provenance, task_snapshots


def validate_adoption(conn, candidate_ref):
    try:
        store = CandidateStore(conn)
        with store.snapshot():
            run, candidate, receipt, scope, tasks, capture, ids, generation_facts = load_adoption_candidate(
                conn, candidate_ref, store=store
            )
            current_capture = ProductionFactsCapture(conn)
            with PreflightFacts.open(conn, capture=current_capture) as facts:
                baseline, projections = check_admission_current(
                    capture,
                    current_capture=current_capture,
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
                refs = {row["op_id"]: row["operation_ref"] for row in prepared.dispositions}
                rows = [_row_from_task(task, refs, prepared.seeds.frozen_op_ids, ids) for task in tasks]
                outcome = validate_adoption_payload(conn, prepared, rows, candidate=candidate)
                snapshot = {
                    "candidate_ref": candidate_ref,
                    "run_ref": candidate["run_ref"],
                    "baseline_ref": baseline["plan_ref"],
                    "baseline_version": baseline["version"],
                }
                provenance, task_snapshots = _provenance_and_snapshots(
                    candidate_ref,
                    run,
                    candidate,
                    receipt,
                    capture,
                    generation_facts,
                    refs,
                    outcome,
                )
                return CandidateAdoptionEvidence(
                    candidate_ref,
                    candidate["run_ref"],
                    baseline,
                    snapshot,
                    prepared,
                    outcome,
                    provenance,
                    task_snapshots,
                )
    except CandidateAdoptionBlocked:
        raise
    except StoredJsonCorrupt as exc:
        # 只有存档 JSON 读不出来这一种存储失败按“不能采用”提示；存档形状损坏与其他存储失败照常 500。
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", _UNREADABLE) from exc
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
    # 安排明细已在任务账本里逐行核对，这里按存档的同一份键表核对其余验证记录。
    if not same(candidate["artifact"]["validated_payload"], validated_payload_record(payload)):
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "候选验证记录与明细不一致。")

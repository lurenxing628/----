"""Archived pressure and adoption use the same complete official operation set."""

import json
from dataclasses import replace

import pytest

from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_piece_adoption import PieceAdoptionScope, PieceOperationWork
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.run.candidate_adoption_validation import _require_official_scope
from core.services.workbench.run.piece_adoption_execution import _quantities
from tests.workbench.run_candidate_adoption_support import INTENT, candidate, preview, service, snapshot
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401


def test_saved_permanent_coverage_agrees_with_real_adoption_guard(candidate_case):
    case = candidate_case
    case.batch("B2")
    second = case.operation("B2")
    case.conn.commit()
    ref = candidate(case, case.settings("B1", "B2"))
    service(case.conn).adopt(ref, preview(case, ref), "coverage-full-official", INTENT)
    refs = {json.loads(row[1])["op_id"]: row[0] for row in case.conn.execute(
        "SELECT operation_ref,payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))}
    coverage = official_scope_coverage(refs.values(), [refs[case.op_id]])
    assert coverage == {"covers_official_scope": False, "official_operation_count": 2,
                        "covered_official_operation_count": 1, "missing_official_operations": [refs[second]]}
    before = snapshot(case.conn)
    with pytest.raises(CandidateAdoptionBlocked) as exc:
        _require_official_scope(ProductionFactsCapture(case.conn).latest_plan_rows(1), {case.op_id})
    assert exc.value.code == "official_scope_not_covered"
    _require_official_scope(ProductionFactsCapture(case.conn).latest_plan_rows(1), {case.op_id, second})
    assert snapshot(case.conn) == before


def _mixed_piece_quantities():
    scope = PieceAdoptionScope((
        PieceOperationWork(1, "ORDINARY", None, 1, 3, ()),
        PieceOperationWork(2, "PIECES", None, 1, 3, ()),
        PieceOperationWork(3, "PIECES", "A", 2, 1, (2,)),
    ))
    refs = {work.op_id: f"{work.op_id:048x}" for work in scope.operations}
    projections = {
        refs[work.op_id]: ExecutionProjection(
            operation_ref=refs[work.op_id], current_task_ref=None, comparison_task_ref=None, plan_identity=None,
            target_quantity=work.target_quantity, target_basis="piece" if work.piece_id is not None else "batch",
            known_completed_quantity=0, quantity_complete=True, unknown_record_count=0, records_complete=True,
            first_actual_start=None, confirmed_finish=None, execution_state="unreported",
            completion_basis=None, data_quality="complete", remaining_quantity=work.target_quantity,
        ) for work in scope.operations
    }
    projections[refs[1]] = replace(
        projections[refs[1]], execution_state="complete", completion_basis="legacy_finish_event",
        quantity_complete=False, unknown_record_count=1, records_complete=False,
        data_quality="legacy_incomplete", remaining_quantity=None,
        first_actual_start="2026-09-09T08:00:00", confirmed_finish="2026-09-09T09:00:00",
    )
    return scope, refs, projections


def test_nonpiece_legacy_completion_can_share_a_run_with_strict_piece_quantities():
    scope, refs, projections = _mixed_piece_quantities()
    _quantities(scope, refs, projections)


@pytest.mark.parametrize("patch,code", [
    ({"target_basis": "piece"}, "piece_quantity_unknown"),
    ({"target_quantity": 4}, "piece_quantity_unknown"),
    ({"data_quality": "invalid"}, "piece_execution_quantity_unproven"),
    ({"known_completed_quantity": 4}, "piece_execution_quantity_unproven"),
    ({"completion_basis": "complete_reports"}, "piece_execution_quantity_unproven"),
])
def test_legacy_completion_exception_keeps_target_and_data_quality_protections(patch, code):
    scope, refs, projections = _mixed_piece_quantities()
    projections[refs[1]] = replace(projections[refs[1]], **patch)
    with pytest.raises(CandidateAdoptionBlocked) as exc:
        _quantities(scope, refs, projections)
    assert exc.value.code == code


@pytest.mark.parametrize("op_id", [2, 3])
def test_piece_batches_and_their_common_operations_still_require_known_completion_quantities(op_id):
    scope, refs, projections = _mixed_piece_quantities()
    work = next(work for work in scope.operations if work.op_id == op_id)
    projections[refs[op_id]] = replace(
        projections[refs[1]], operation_ref=refs[op_id], target_quantity=work.target_quantity,
        target_basis="piece" if work.piece_id is not None else "batch",
    )
    with pytest.raises(CandidateAdoptionBlocked) as exc:
        _quantities(scope, refs, projections)
    assert exc.value.code == "piece_execution_quantity_unproven"

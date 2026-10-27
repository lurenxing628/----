"""Shared candidate proof remains local to its read snapshot."""

from dataclasses import replace

import pytest

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.run import input_execution, piece_adoption
from tests.workbench.piece_adoption_support import lower_input, slot_payload, split
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.run_compute_support import prepare_run_input


def test_piece_candidates_reuse_proof_but_adoption_rechecks_current_quantities(trial_case, monkeypatch):
    case = trial_case
    split(case)
    quantity_checks = []
    original = input_execution._quantities

    def count_quantities(scope, refs, projections):
        quantity_checks.append(scope)
        return original(scope, refs, projections)

    monkeypatch.setattr(input_execution, "_quantities", count_quantities)
    prepared = lower_input(case)
    payload = slot_payload(prepared)
    with candidate_read_snapshot(case.conn):
        context = piece_adoption.prepare_piece_validation_context(case.conn, prepared)
        for _ in range(2):
            piece_adoption.validate_piece_candidate(case.conn, prepared=prepared, payload=payload, context=context)
    assert quantity_checks == [prepared.piece_scope]

    ref = prepared.preflight_facts.operation_refs[case.op_id]
    projections = [
        replace(item, target_quantity=item.target_quantity + 1) if item.operation_ref == ref else item
        for item in case.projections("B1")
    ]
    with pytest.raises(PieceAdoptionBlocked) as caught:
        prepare_run_input(case.conn, case.settings("B1"), projections, for_adoption=True)
    assert caught.value.code == "piece_quantity_unknown"
    assert quantity_checks == [prepared.piece_scope, prepared.piece_scope]


def test_reused_piece_scope_still_proves_disposition_identity(trial_case):
    case = trial_case
    split(case)
    prepared = lower_input(case)
    prepared.dispositions[0]["operation_ref"] = "changed-operation-ref"
    with pytest.raises(PieceAdoptionBlocked) as caught:
        piece_adoption.prepare_piece_validation_context(case.conn, prepared)
    assert caught.value.code == "piece_identity_changed"

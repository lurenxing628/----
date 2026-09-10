"""Real worker candidates preserve common joins and independent single-piece work."""

from dataclasses import replace
from datetime import datetime

import pytest

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.workbench.run_input import prepare_candidate_run_input
from tests.workbench.test_piece_adoption_support import split
from tests.workbench.test_piece_chain_support import artifact, piece_candidate, piece_layout
from tests.workbench.test_piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_run_candidate_support import compute


@pytest.mark.parametrize("parallel", [False, True])
def test_real_worker_exact_quantity_fan_out_join(trial_case, parallel):
    case = trial_case
    ids, _, refs = piece_candidate(case, parallel=parallel)
    for ref in refs:
        rows = {row["op_id"]: row for row in artifact(case, ref)["results"]}
        assert set(rows) == set(ids.values())
        for key, op_id in ids.items():
            row = rows[op_id]
            duration = datetime.fromisoformat(row["end_time"]) - datetime.fromisoformat(row["start_time"])
            assert duration.total_seconds() == (2700 if key[0] is None else 900)
        for piece in ("item-A", "item-B", "item-C"):
            assert rows[ids[piece, 20]]["start_time"] >= rows[ids[None, 10]]["end_time"]
            assert rows[ids[piece, 30]]["start_time"] >= rows[ids[piece, 20]]["end_time"]
            assert rows[ids[None, 40]]["start_time"] >= rows[ids[piece, 30]]["end_time"]
        if parallel:
            assert len({rows[ids[piece, 20]]["start_time"] for piece in ("item-A", "item-B", "item-C")}) == 1
    assert case.conn.execute("SELECT quantity FROM Batches WHERE batch_id='B1'").fetchone()[0] == 3
    assert case.conn.execute("SELECT count(*) FROM Schedule").fetchone()[0] == 0


def test_piece_zero_work_uses_exact_original_execution_target(trial_case):
    case = trial_case
    split(case, unit=0)
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    pieces = [row for row in prepared.dispositions if row["piece_id"] is not None]
    assert len(pieces) == 6
    assert all(row["execution"]["target_basis"] == "piece" and row["execution"]["target_quantity"] == 1
               for row in pieces)
    projections = [replace(item, target_quantity=3, remaining_quantity=3) if item.target_basis == "piece" else item
                   for item in case.projections()]
    with pytest.raises(PieceAdoptionBlocked) as caught:
        prepare_candidate_run_input(case.conn, case.settings(), projections)
    assert caught.value.code == "piece_quantity_unknown"


def test_piece_graph_retains_material_ready_date_and_auto_assignment(trial_case):
    case = trial_case
    ids = piece_layout(case)
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-11'")
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL,operator_id=NULL WHERE piece_id IS NOT NULL")
    case.conn.commit()
    _, refs = compute(case)
    for ref in refs:
        rows = artifact(case, ref)["results"]
        assert {row["op_id"] for row in rows} == set(ids.values())
        assert min(row["start_time"] for row in rows) >= "2026-09-11T08:00:00"
        assert all(row["machine_id"] and row["operator_id"] for row in rows)

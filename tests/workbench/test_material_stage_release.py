"""Real candidate decoding respects stage dates and never splits quantities itself."""

from datetime import datetime

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.run.compute import compute_candidate_run
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def add_requirement(case, second, arrivals):
    case.conn.execute("DELETE FROM WorkbenchCalendarDefaults")
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1", (str(second),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B1"), {"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3,
            "available_quantity": 0, "operation_ref": operation_ref, "arrivals": arrivals}]})


def test_stage_arrivals_wait_at_use_operation_in_all_real_candidates(run_case):
    case = run_case
    second = case.operation(seq=2)
    add_requirement(case, second, [{"arrival_date": "2026-09-10", "quantity": 1}, {"arrival_date": "2026-09-11", "quantity": 2}])
    settings = case.settings(material_strategy="stage")
    result = unchanged(case, lambda: compute_candidate_run(case.conn, settings, case.projections()))
    assert result.state == "complete"
    for candidate in result.candidate_payloads.values():
        rows = {row.op_id: row for row in candidate.schedule_rows}
        assert rows[case.op_id].start_time == datetime(2026, 9, 9, 8, 30)
        assert rows[second].start_time == datetime(2026, 9, 11, 8, 30)
    strict = prepare_candidate_run_input(case.conn, case.settings(material_strategy="strict"), case.projections())
    assert {op.material_ready_date for op in strict.algo_ops} == {"2026-09-11"}
    assert case.conn.execute("SELECT quantity FROM Batches WHERE batch_id='B1'").fetchone()[0] == 3


def test_missing_later_material_only_allows_earlier_stage_and_quantity_change_requires_review(run_case):
    case = run_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    data, _ = PreflightService(case.conn).evaluate(case.settings(material_strategy="stage"))
    assert [row["status"] for row in data["tasks"]] == ["eligible", "skipped"]
    prepared = prepare_candidate_run_input(case.conn, case.settings(material_strategy="stage"), case.projections())
    assert [op.id for op in prepared.algo_ops] == [case.op_id]
    with pytest.raises(CandidateRunInputError):
        prepare_candidate_run_input(case.conn, case.settings(material_strategy="strict"), case.projections())
    case.conn.execute("UPDATE Batches SET quantity=4 WHERE batch_id='B1'")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError):
        prepare_candidate_run_input(case.conn, case.settings(material_strategy="stage"), case.projections())

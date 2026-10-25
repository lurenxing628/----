"""当前工作台的关闭批次与跳过工序只形成处置记录，不进入候选。"""

import pytest

from core.services.workbench.run.compute import compute_candidate_run
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


@pytest.mark.parametrize("batch_status", ["completed", "cancelled"])
def test_closed_batches_and_skipped_operations_do_not_enter_candidates(run_case, batch_status):
    case = run_case
    skipped = case.operation(seq=2, status="skipped")
    case.batch("B2", status=batch_status)
    closed = case.operation("B2")
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings("B1", "B2"), case.projections()))
    assert result.schedule_input.schedule_output_allowed_op_ids == {case.op_id}
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == {case.op_id}
    skipped_rows = {row["op_id"] for row in result.dispositions if row["status"] == "skipped"}
    assert skipped_rows == {skipped, closed}

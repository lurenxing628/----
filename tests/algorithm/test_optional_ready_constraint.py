"""工作台这次齐套检查开关决定未齐套工序是否参加计算。"""

import pytest

from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run.compute import compute_candidate_run
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def test_optional_ready_constraint(run_case):
    case = run_case
    case.conn.execute("UPDATE Batches SET ready_status='no' WHERE batch_id='B1'")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError, match="没有可排"):
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(ready_check=True), case.projections()))
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(ready_check=False), case.projections()))
    assert all(payload.scheduled_op_ids == {case.op_id} for payload in result.candidate_payloads.values())

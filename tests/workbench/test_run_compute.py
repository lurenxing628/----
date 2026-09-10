"""Actual single-chain candidates, not a preflight or mocked optimizer."""

from datetime import datetime

from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.services.scheduler.run.schedule_input_collector import ScheduleRunInput
from core.services.workbench.run_compute import compute_candidate_run
from core.services.workbench.run_input import prepare_candidate_run_input
from tests.workbench.test_run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.test_run_compute_support import unchanged


def test_actual_candidates_are_typed_scoped_and_never_persisted(run_case):
    case = run_case
    projections = case.projections()
    prepared = unchanged(case, lambda: prepare_candidate_run_input(case.conn, case.settings(), projections))
    assert isinstance(prepared, ScheduleRunInput)
    assert isinstance(prepared.batches["B1"], Batch)
    assert all(isinstance(op, BatchOperation) for op in prepared.operations)
    assert prepared.normalized_batch_ids == ["B1"]
    assert prepared.cfg.auto_assign_persist == "no"
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))
    assert result.result_persisted is False
    assert result.state == "complete"
    assert result.orchestration.candidate_comparison.completed_count == 4
    assert set(result.candidate_payloads) == {"baseline", "graph_w1_of_3", "graph_w2_of_3", "graph_w3_of_3"}
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == {case.op_id}
        row = payload.schedule_rows[0]
        assert row.start_time == datetime(2026, 9, 9, 8)
        assert row.end_time == datetime(2026, 9, 9, 8, 45)


def test_input_overrides_do_not_mutate_global_config(run_case):
    case = run_case
    case.config(auto_assign_enabled="no", auto_assign_persist="yes", enforce_ready_default="yes")
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(ready_check=False), case.projections()))
    assert result.schedule_input.cfg.auto_assign_enabled == "yes"
    assert result.schedule_input.readiness_gate_enabled is False
    assert result.schedule_input.cfg.enforce_ready_default == "no"

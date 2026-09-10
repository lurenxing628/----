"""No Schedule/Candidate/version or other table changes, including failures."""

import sqlite3

import pytest

from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run_compute import compute_candidate_run, compute_prepared_candidate_run
from core.services.workbench.run_input import prepare_candidate_run_input
from core.services.workbench.run_input_projection_codec import restore_execution_projections
from tests.workbench.test_preflight_support import deny_writes
from tests.workbench.test_run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.test_run_compute_support import unchanged


@pytest.mark.parametrize("target", ["ScheduleVersionSeq", "ScheduleConfig", "Schedule", "ScheduleCandidate"])
def test_incidental_write_is_denied_before_any_change(run_case, monkeypatch, target):
    from core.services.workbench import run_compute

    case = run_case
    projections = case.projections()

    def attempted_write(**kwargs):
        if target == "ScheduleVersionSeq":
            case.conn.execute("INSERT INTO ScheduleVersionSeq DEFAULT VALUES")
        else:
            case.conn.execute("DELETE FROM " + target)
        raise AssertionError("write unexpectedly succeeded")

    monkeypatch.setattr(run_compute, "optimize_schedule", attempted_write)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))
    assert case.conn.execute("PRAGMA query_only").fetchone()[0] == 0
    assert not case.conn.in_transaction


def test_caller_authorizer_and_open_transaction_are_preserved(run_case):
    case = run_case
    projections = case.projections()
    case.conn.execute("BEGIN")
    case.conn.set_authorizer(deny_writes)
    try:
        result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))
        assert result.result_persisted is False
        assert case.conn.in_transaction
        with pytest.raises(sqlite3.DatabaseError, match="authorized"):
            case.conn.execute("DELETE FROM Schedule")
    finally:
        case.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        case.conn.rollback()


def test_late_summary_failure_does_not_leave_candidate_or_version(run_case, monkeypatch):
    from core.services.workbench import run_compute

    case = run_case

    def broken_summary(*args, **kwargs):
        raise RuntimeError("summary fault after real optimization")

    monkeypatch.setattr(run_compute, "build_result_summary", broken_summary)
    with pytest.raises(RuntimeError, match="summary fault"):
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))


def test_missing_config_is_not_bootstrapped_by_compute(run_case):
    case = run_case
    case.conn.execute("DELETE FROM ScheduleConfig")
    case.conn.commit()
    with pytest.raises(Exception, match="配置|参数|缺"):
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))


def test_projection_snapshot_codec_preserves_null_zero_and_all_fields(run_case):
    plain = [row.to_dict() for row in run_case.projections()]
    restored = restore_execution_projections(plain)
    assert [row.to_dict() for row in restored] == plain
    assert restored[0].known_completed_quantity == 0
    assert restored[0].first_actual_start is None
    damaged = dict(plain[0])
    del damaged["remaining_quantity"]
    with pytest.raises(CandidateRunInputError) as error:
        restore_execution_projections([damaged])
    assert error.value.reason == "execution_snapshot_invalid"


def test_explicit_zero_context_never_silently_becomes_previous_version(run_case):
    case = run_case
    case.plan(7, [case.op_id])
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_prepared_candidate_run(case.conn, prepared, version_override=0))
    assert error.value.reason == "version_context_unrepresentable"

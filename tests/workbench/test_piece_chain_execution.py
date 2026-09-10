"""Original actual intervals, fixed seeds and unrelated pieces through both adoptions."""

import pytest

from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_piece_chain_support import (
    adopt_candidate,
    adopt_trial,
    artifact,
    piece_candidate,
    saved_trial,
)
from tests.workbench.test_piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_run_jobs_support import service as run_service
from tests.workbench.trial_support import snapshot


def test_actual_piece_and_independent_locked_successor_reach_both_adoptions(trial_case):
    case = trial_case
    ids, _, refs = piece_candidate(case, common=False)
    adopt_candidate(case, refs[0])
    first, independent = ids["item-A", 20], ids["item-B", 30]
    report = case.command("create", case.task(1, first), case.values(1))
    assert report["ok"]
    case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=1 AND op_id=?", (independent,))
    case.conn.commit()
    before = snapshot(case.conn)
    accepted = case.accept(key="ef-with-actuals-run-0001")
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    for item in result["candidates"]:
        rows = {row["op_id"]: row for row in artifact(case, item["candidate_ref"])["results"]}
        assert rows[first]["start_time"] == "2026-09-09T08:00:00"
        assert rows[first]["end_time"] == "2026-09-09T10:00:00"
        assert rows[ids["item-A", 30]]["start_time"] >= rows[first]["end_time"]
        assert rows[independent]["start_time"] < rows[first]["end_time"]
        assert rows[independent]["machine_id"] == "M2"
    plan = adopt_candidate(case, result["candidates"][0]["candidate_ref"], "ef-actual-candidate-adopt-0001")["data"]["official_plan"]
    _, _, saved = saved_trial(case, {"plan_ref": plan["plan_ref"]}, op_id=ids["item-A", 30])
    next_plan = adopt_trial(case, saved)["data"]["official_plan"]
    assert next_plan["version"] == 3
    after = snapshot(case.conn)
    for table in ("Batches", "BatchOperations", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions",
                  "OperationExecutionEvents"):
        assert after[table] == before[table], table
    for version in (2, 3):
        actual = case.conn.execute("SELECT start_time,end_time,machine_id,operator_id,lock_status FROM Schedule "
                                   "WHERE version=? AND op_id=?", (version, first)).fetchone()
        assert tuple(actual) == ("2026-09-09 08:00:00", "2026-09-09 10:00:00", "M1", "O1", "locked")


@pytest.mark.parametrize("quantity", [None, 0])
def test_unknown_or_partial_piece_report_blocks_before_run_acceptance(trial_case, quantity):
    case = trial_case
    ids, _, refs = piece_candidate(case, common=False)
    adopt_candidate(case, refs[0])
    case.command("create", case.task(1, ids["item-A", 20]), case.values(quantity))
    before = snapshot(case.conn)
    preview = run_service(case.conn).preview(case.preflight())
    assert preview["write_context"]["capabilities"]["scheduling.run"] is False
    assert preview["write_context"]["write_token"] is None
    assert snapshot(case.conn) == before

"""Worker -> persisted candidate -> official -> reopened DB -> changed saved trial -> official."""

import json

import pytest

from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from tests.workbench.piece_chain_support import (
    adopt_candidate,
    adopt_trial,
    artifact,
    piece_candidate,
    saved_trial,
)
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.trial_adoption_support import service as trial_adoption
from tests.workbench.trial_support import connect, snapshot
from tests.workbench.trial_support import service as trial_service


def workspace(conn, ref):
    svc = WorkbenchPlanQueryService(conn)
    with svc.read_snapshot():
        return svc.workspace(PlanReadScope(ref))[0]


@pytest.mark.parametrize("common", [False, True])
def test_real_complete_chain_preserves_raw_source_old_scene_and_receipts(trial_case, common):
    case = trial_case
    ids, run_ref, refs = piece_candidate(case, common=common)
    original_artifact = artifact(case, refs[0])
    adopted = adopt_candidate(case, refs[0])
    plan = adopted["data"]["official_plan"]
    assert plan["version"] == 1
    before = snapshot(case.conn)
    reopened = connect(case.path)
    original_connection = case.conn
    case.conn = reopened
    try:
        read = workspace(reopened, plan["plan_ref"])
        assert len(read["tasks"]) == len(ids)
        assert artifact(case, refs[0]) == original_artifact
        replay = candidate_adoption(reopened).adopt(refs[0], "expired", "ef-candidate-adopt-0001", INTENT)
        assert replay["receipt_ref"] == adopted["receipt_ref"] and replay["replayed"]
        assert snapshot(reopened) == before
        target = ids[None, 40] if common else ids["item-C", 30]
        draft, changed, saved = saved_trial(case, {"plan_ref": plan["plan_ref"]}, op_id=target)
        assert draft["task_count"] == changed["task_count"] == saved["task_count"] == len(ids)
        if common:
            join = next(row for row in draft["tasks"] if row["sequence"] == 40)
            assert len(join["predecessor_operation_refs"]) == 3
        assert {row["quantity"] for row in draft["tasks"] if row["piece_id"] is not None} == {1}
        assert {row["batch_quantity"] for row in draft["tasks"]} == {3}
        frozen_scene = trial_service(reopened).scenario(saved["scenario_ref"])
        adopted_trial = adopt_trial(case, saved)
        next_plan = adopted_trial["data"]["official_plan"]
        assert next_plan["version"] == 2
        assert next_plan["source_scenario_ref"] == saved["scenario_ref"]
        assert trial_service(reopened).scenario(saved["scenario_ref"]) == frozen_scene
        assert workspace(reopened, plan["plan_ref"])["tasks"] == read["tasks"]
        for version, source in ((1, "workbench_candidate_adoption"), (2, "workbench_trial_adoption")):
            audit = json.loads(reopened.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,)).fetchone()[0])
            assert audit["source"] == source
            assert audit["run_ref"] == run_ref if version == 1 else audit["scenario_ref"] == saved["scenario_ref"]
        current = snapshot(reopened)
        for table in ("Batches", "BatchOperations", "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks",
                      "WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "OperationExecutionEvents"):
            assert current[table] == before[table], table
        replay = trial_adoption(reopened).adopt(saved["scenario_ref"], "expired", "ef-piece-trial-adopt-0001", INTENT)
        assert replay["receipt_ref"] == adopted_trial["receipt_ref"] and replay["replayed"]
        assert snapshot(reopened) == current
    finally:
        case.conn = original_connection
        reopened.close()
    final_connection = connect(case.path)
    try:
        after = workspace(final_connection, next_plan["plan_ref"])
        assert {row["operation_ref"] for row in after["tasks"]} == {row["operation_ref"] for row in read["tasks"]}
        assert any(row["start"] == "2026-09-09T13:00:00" for row in after["tasks"])
        assert final_connection.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 32
    finally:
        final_connection.close()


def test_real_worker_candidate_can_be_trial_source_without_adopting_it(trial_case):
    case = trial_case
    ids, _, refs = piece_candidate(case)
    _, _, saved = saved_trial(case, {"candidate_ref": refs[0]}, op_id=ids[None, 40])
    assert case.conn.execute("SELECT count(*) FROM Schedule").fetchone()[0] == 0
    result = adopt_trial(case, saved)
    assert result["data"]["official_plan"]["version"] == 1

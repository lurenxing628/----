"""Real scheduling/adoption/reopen/read evidence for fractional work, never rounding."""

import json
from datetime import datetime

import pytest

from core.models.workbench_plan_scope import PlanReadScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
from tests.workbench.ea_zero_duration_support import adoption_service
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import compute, connect


@pytest.mark.parametrize("efficiency,shift_hours", [(1, 8), (0.7, 8), (1, 0.0025)])
def test_fractional_chain_all_candidates_adopt_reopen_and_delivery(candidate_case, efficiency, shift_hours):
    case = candidate_case
    case.conn.execute("UPDATE Batches SET part_name='Original part'")
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    case.operation(seq=2, unit_hours=0)
    case.operation(seq=3, unit_hours=0.001)
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_hours,efficiency,allow_normal,allow_urgent) "
                      "VALUES ('2026-09-09','workday','08:00',?,?,'yes','yes')", (shift_hours, efficiency))
    case.conn.commit()
    _, refs = compute(case)
    assert len(refs) == 4
    svc = adoption_service(case.conn)
    for ref in refs:
        preview = svc.preview(ref)
        assert preview["validation"]["can_adopt"], preview
        workspace, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(ref))
        tasks = sorted(workspace["tasks"], key=lambda row: row["sequence"])
        assert len(tasks) == 3
        assert tasks[1]["start"] == tasks[1]["end"] == tasks[0]["end"]
        assert tasks[2]["start"] >= tasks[1]["end"]
        assert any(datetime.fromisoformat(row["end"]).microsecond for row in tasks)
        delivery, = workspace["delivery_risks"]["items"]
        assert delivery["risk"] == "on_time" and delivery["invalid_task_count"] == 0
        assert delivery["planned_finish"] == max(row["end"] for row in tasks)
        analysis, _ = read_candidate_analysis(case.conn, ref)
        assert analysis["metrics"]["overdue_count"]["value"] == 0
        assert analysis["metrics"]["total_tardiness_hours"]["value"] == 0
        assert analysis["baseline"]["available"] is False
    ref = refs[0]
    expected = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (ref,))]
    preview = svc.preview(ref)
    result = svc.adopt(ref, preview["write_context"]["write_token"], "subsecond-adopt-00001", INTENT)
    plan = result["data"]["official_plan"]
    reopened = connect(case.path)
    try:
        stored = {row["op_id"]: dict(row) for row in reopened.execute("SELECT * FROM Schedule WHERE version=?", (plan["version"],))}
        for row in expected:
            for field in ("start_time", "end_time"):
                assert datetime.fromisoformat(stored[row["op_id"]][field]) == datetime.fromisoformat(row[field])
        reader = WorkbenchPlanQueryService(reopened)
        with reader.read_snapshot():
            public, _ = reader.workspace(PlanReadScope(plan["plan_ref"]))
        assert sorted((row["start"], row["end"]) for row in public["tasks"]) == sorted(
            (row["start_time"], row["end_time"]) for row in expected)
        assert reopened.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(reopened.execute("PRAGMA foreign_key_check")) == []
    finally:
        reopened.close()

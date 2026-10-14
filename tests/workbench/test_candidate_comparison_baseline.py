"""Current comparison consumers share the assembled admission official source."""

from copy import deepcopy

import pytest

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from core.services.workbench.run.candidate_comparison import read_candidate_comparison
from core.services.workbench.run.decision_impact import batch_impacts
from core.services.workbench.run.decision_source import DecisionSource
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import INTENT, service
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401


def run(case, key):
    accepted = case.accept(key="shared-formal-run-" + key, settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    return result["run_ref"], result["candidates"][0]["candidate_ref"]


def test_partial_formal_version_current_analysis_dashboard_and_decision_share_whole_batches(candidate_case, monkeypatch):
    case = candidate_case
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    _, original = run(case, "original")
    initial, _ = read_candidate_analysis(case.conn, original)
    assert all(row["change_kinds"] == ["unknown"] for row in initial["batches"])
    adopter = service(case.conn)
    preview = adopter.preview(original)
    adopter.adopt(original, preview["write_context"]["write_token"], "shared-formal-adoption", INTENT)
    # A legacy partial version preserves B2's most recent formal arrangement in v1.
    case.conn.execute("INSERT INTO Schedule(op_id,machine_id,operator_id,start_time,end_time,lock_status,version) "
                      "SELECT op_id,machine_id,operator_id,start_time,end_time,lock_status,2 FROM Schedule WHERE op_id=?", (case.op_id,))
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status,result_summary) "
                      "VALUES(2,'manual',1,1,'success','{}')")
    case.conn.commit()
    run_ref, candidate = run(case, "comparison")
    source = read_candidate_source(CandidateStore(case.conn), candidate)
    captured = deepcopy(source.capture)
    # Force a real multi-chunk historical read without changing the worker quota.
    monkeypatch.setattr("core.services.workbench.facts.candidate_baseline.MAX_OPERATIONS", 1)
    legacy, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(candidate))
    assert legacy["baseline"]["captured_task_count"] == 1
    assert next(row for row in legacy["comparisons"] if row["batch_label"] == "B2")["baseline_segments"] == []
    analysis, _ = read_candidate_analysis(case.conn, candidate)
    dashboard, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(
        candidate, "2026-09-09T00:00:00", "2026-09-26T00:00:00"))
    store = CandidateStore(case.conn)
    with store.snapshot(), read_evidence_scope(case.conn):
        decision = DecisionSource(store, run_ref, comparison_mode="admission_official", selected_candidate_ref=candidate)
        rows, summary = batch_impacts(decision)
    expected = {row["batch_ref"]: row["before"] for row in rows}
    for data in (analysis, dashboard):
        assert {row["batch_ref"]: row["before"] for row in data["batches"]} == expected
        assert data["baseline"]["captured_task_count"] == 2
        assert data["baseline"]["version"] == legacy["baseline"]["version"] == 2
    assert all(row["schedule_complete"] and row["risk"] == "on_time" for row in expected.values())
    assert dashboard["summary"]["before"]["known_due_count"] == 2
    assert dashboard["summary"]["before"]["unknown_due_count"] == 0
    assert dashboard["summary"]["before"]["total_tardiness_hours"] == summary["before"]["total_tardiness_hours"] == 0
    assert dashboard["machine_changes"]["count"] == analysis["metrics"]["machine_change_count"]["value"] == 0
    assert read_candidate_source(CandidateStore(case.conn), candidate).capture == captured
    duplicate = deepcopy(captured)
    duplicate["execution"][1] = deepcopy(duplicate["execution"][0])
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        AdmissionBaseline(duplicate, source.facts, source.disposition, source.run["accepted_at"])
    assert rejected.value.code == "candidate_baseline_invalid"

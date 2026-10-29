"""Current comparison consumers share the assembled admission official source."""

from copy import deepcopy

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from core.services.workbench.run.candidate_comparison import read_candidate_comparison
from core.services.workbench.run.decision_impact import batch_impacts
from core.services.workbench.run.decision_source import DecisionSource
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import INTENT, service
from tests.workbench.run_candidate_support import api
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_run_decision_impact_api import detail, operation_ref


def run(case, key):
    accepted = case.accept(key="shared-formal-run-" + key, settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    return result["run_ref"], result["candidates"][0]["candidate_ref"]


def test_formal_versions_current_analysis_dashboard_and_decision_share_whole_batches(candidate_case):
    case = candidate_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Milling')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T2')")
    case.batch("B2", due_date="2026-09-20")
    second_id = case.operation("B2", op_type_id="T2", op_type_name="Milling")
    case.conn.commit()
    case.config(sort_strategy="due_date_first")
    _, original = run(case, "original")
    initial, _ = read_candidate_analysis(case.conn, original)
    assert all(row["change_kinds"] == ["unknown"] for row in initial["batches"])
    adopter = service(case.conn)
    preview = adopter.preview(original)
    adopter.adopt(original, preview["write_context"]["write_token"], "shared-formal-adoption", INTENT)
    accepted = case.accept(key="shared-formal-run-selected", settings=case.settings("B1"))
    selected_run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert selected_run["state"] == "complete"
    selected_ref = selected_run["candidates"][0]["candidate_ref"]
    client, _ = api(case)
    changes = detail(client, accepted["run_ref"], "changeovers", selected_candidate_ref=selected_ref,
        comparison_mode="admission_official", range_start="2026-09-09T00:00:00", range_end="2026-09-26T00:00:00")["data"]
    for side, value in (("before", 1), ("after", 0)):
        metric = changes["summary"][side]["type_changeover_count"]
        assert metric["value"] == value and metric["total_count"] == 1
    difference = changes["summary"]["deltas"]["type_changeover_count"]
    assert difference["reference_value"] == 1 and difference["selected_value"] == 0
    assert difference["value"] == -1 and difference["state"] == "comparable" and difference["direction"] == "better"
    assert len(changes["items"]) == 1
    predecessor = changes["items"][0]
    first_ref, second_ref = (operation_ref(case, key) for key in (case.op_id, second_id))
    assert predecessor["event_side"] == "reference"
    assert predecessor["previous_operation_ref"] == second_ref and predecessor["next_operation_ref"] == first_ref
    selected_dashboard, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(
        selected_ref, "2026-09-09T00:00:00", "2026-09-26T00:00:00"))
    entry = next(row for row in selected_dashboard["tradeoffs"]["all_differences"] if row["metric_key"] == "type_changeover_count")
    assert entry["reference_value"] == 1 and entry["selected_value"] == 0
    assert entry["value"] == -1 and entry["state"] == "comparable" and entry["direction"] == "better"
    # 第二次采用覆盖 B1、B2（每次采用都覆盖已有正式安排的完整工序范围）。
    _, second = run(case, "second-adoption")
    preview = adopter.preview(second)
    assert preview["validation"]["can_adopt"], preview
    adopter.adopt(second, preview["write_context"]["write_token"], "shared-formal-adoption-2", INTENT)
    run_ref, candidate = run(case, "comparison")
    source = read_candidate_source(CandidateStore(case.conn), candidate)
    captured = deepcopy(source.capture)
    baseline_view, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(candidate))
    assert baseline_view["baseline"]["captured_task_count"] == 2
    assert all(row["baseline_segments"] for row in baseline_view["comparisons"])
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
        assert data["baseline"]["version"] == baseline_view["baseline"]["version"] == 2
    assert all(row["schedule_complete"] and row["risk"] == "on_time" for row in expected.values())
    assert dashboard["summary"]["before"]["known_due_count"] == 2
    assert dashboard["summary"]["before"]["unknown_due_count"] == 0
    assert dashboard["summary"]["before"]["total_tardiness_hours"] == summary["before"]["total_tardiness_hours"] == 0
    assert dashboard["machine_changes"]["count"] == analysis["metrics"]["machine_change_count"]["value"] == 0
    assert read_candidate_source(CandidateStore(case.conn), candidate).capture == captured

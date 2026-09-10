"""EP fixture regressions use real admission, worker, HTTP and temporary SQLite."""

import json

import pytest

from tests.workbench.run_baseline_widgets_support import record, small_cases
from tests.workbench.run_candidate_baseline_support import baseline
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.trial_widgets_support import TrialWidgetServer, service


def test_ep_trial_baseline_unready_work_is_not_an_improvement(candidate_case):
    case = candidate_case
    cases = small_cases(case)
    for name in ("mixed", "execution"):
        assert len(cases[name]["refs"]) == 4
        for ref in cases[name]["refs"]:
            data, _ = baseline(case, ref)
            rows = [row for row in data["comparisons"] if row["status"] == "unscheduled"]
            assert len(rows) == 1, data["counts"]
            row = rows[0]
            assert row["batch_label"] == "UNREADY" and row["quantity"] == 3
            assert row["candidate_operation_status"] == "skipped"
            assert row["candidate"] is None and row["row_ref"] is None
            assert len(row["baseline_segments"]) == 1
            assert all(value is None for value in row["delta"].values())
            assert data["improvement_assessment"] is None
            assert not case.conn.execute(
                "SELECT 1 FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? AND operation_ref=?",
                (ref, row["operation_ref"]),
            ).fetchone()
    quantity, ready = case.conn.execute(
        "SELECT quantity,ready_status FROM Batches WHERE batch_id='UNREADY'"
    ).fetchone()
    assert (quantity, ready) == (3, "no")
    # Removing the real readiness blocker must let the same operation be scheduled.
    case.conn.execute("UPDATE Batches SET ready_status='yes' WHERE batch_id='UNREADY'")
    case.conn.commit()
    scheduled = record(case, case.settings("B1", "UNREADY"))
    for ref in scheduled["refs"]:
        data, _ = baseline(case, ref)
        row = next(row for row in data["comparisons"] if row["batch_label"] == "UNREADY")
        assert row["status"] == "matched" and row["candidate_operation_status"] == "scheduled"
        assert row["candidate"]["start"] < row["candidate"]["end"]


@pytest.mark.parametrize("source", ("plan", "candidate", "saved"))
def test_ep_trial_refs_follow_complete_original_piece_scope(tmp_path, source):
    backend = TrialWidgetServer(tmp_path)
    with backend.connect() as conn, backend.app.app_context():
        quantity = conn.execute("SELECT quantity FROM Batches WHERE batch_id='B3'").fetchone()[0]
        pieces = conn.execute("SELECT DISTINCT piece_id FROM BatchOperations WHERE batch_id='B3'").fetchall()
        assert quantity == len(pieces) == 1
        assert pieces[0][0] == "piece-A"
        if source == "candidate":
            svc = service(conn)
            value = {"base": {"candidate_ref": backend.refs["candidate_ref"]}}
            preview = svc.preview_create(value)
            draft = svc.create(value, preview["write_context"]["write_token"], "ep-trial-candidate-0001")["data"]
            kind, ref = "drafts", draft["draft_ref"]
        elif source == "saved":
            kind = "scenarios"
            ref = conn.execute("SELECT scenario_ref FROM WorkbenchTrialScenarios WHERE draft_ref=?",
                               (backend.refs["drafts"][0],)).fetchone()[0]
        else:
            kind, ref = "drafts", backend.refs["drafts"][2]
    response = backend.app.test_client().get("/api/workbench/v1/trial/" + kind + "/" + ref)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["task_count"] == (4 if source == "candidate" else 5)
    assert data["validation"]["constraints_status"] == "valid", data["validation"]
    tasks = sorted((row for row in data["tasks"] if row["batch_id"] == "B1"), key=lambda row: row["sequence"])
    assert [row["sequence"] for row in tasks] == [1, 2, 3]
    assert tasks[0]["predecessor_refs"] == tasks[0]["predecessor_operation_refs"] == []
    with backend.connect() as conn:
        sql = ("SELECT s.task_ref,d.original_json FROM WorkbenchTrialScenarioRows s "
               "JOIN WorkbenchTrialRows d ON d.row_ref=s.source_row_ref WHERE s.scenario_ref=?"
               if source == "saved" else
               "SELECT task_ref,original_json FROM WorkbenchTrialRows WHERE draft_ref=?")
        originals = {row[0]: json.loads(row[1]) for row in conn.execute(sql, (ref,))}
        if source == "saved":
            stored = {row[0]: json.loads(row[1]) for row in conn.execute(
                "SELECT task_ref,payload_json FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?", (ref,))}
            assert stored == {row["task_ref"]: row for row in data["tasks"]}
        for previous, task in zip(tasks, tasks[1:]):
            assert task["predecessor_refs"] == [previous["task_ref"]]
            expected = [previous["operation_ref"]]
            assert task["predecessor_operation_refs"] == expected
            assert originals[task["task_ref"]]["predecessor_operation_refs"] == expected
            assert previous["end"] == task["start"]
            assert task["hours"]["total_hours"] * 3600 == pytest.approx(30)
    proof = backend.proof()
    assert proof["all_connections_isolated"] and not proof["business_results_mocked"]
    assert all(row["legacy_rows_and_types_retained"] for row in proof["databases"])

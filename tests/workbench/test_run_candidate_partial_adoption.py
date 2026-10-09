"""A complete persisted candidate remains usable when comparison siblings time out."""
import json
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run import compute as compute_module
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import BASE, INTENT, api, service, snapshot
from tests.workbench.run_candidate_support import edit_artifact
from tests.workbench.test_material_stage_release import add_requirement
from tests.workbench.trial_support import connect
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as _trial_case


@pytest.fixture(name="trial_case")
def _case(tmp_path):
    yield from _trial_case.__wrapped__(tmp_path)


def persisted_partial_run(case, monkeypatch, *, setup=None, settings=None, expected_tasks=2):
    """Real engine and worker; advance only the budget clock after baseline decode."""
    compare = compute_module.run_candidate_comparison

    def complete_then_expire(**kwargs):
        measured = [0.0]
        optimize = kwargs.pop("optimize_schedule_fn")

        def real_decode(**inputs):
            outcome = optimize(**inputs)
            measured[0] = 120.0
            return outcome

        return compare(**kwargs, optimize_schedule_fn=real_decode, clock=lambda: measured[0])

    monkeypatch.setattr(compute_module, "run_candidate_comparison", complete_then_expire)
    second = case.operation(seq=2)
    if setup is not None:
        setup(case, second)
    case.conn.commit()
    accepted = case.accept(settings=settings)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "partial" and result["result_persisted"] is True
    assert result["candidates"][0]["status"] == "completed"
    assert result["candidates"][0]["task_count"] == expected_tasks
    assert all(row["status"] == "skipped" and row["task_count"] == 0 for row in result["candidates"][1:])
    return result


def test_partial_run_complete_candidate_http_preview_and_real_adoption(trial_case, monkeypatch):
    case = trial_case
    result = persisted_partial_run(case, monkeypatch)
    ref = result["candidates"][0]["candidate_ref"]
    client = api(case)
    before = snapshot(case.conn)
    preview = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]
    assert preview["validation"]["can_adopt"] is True, preview
    assert preview["scope_complete"] is True and preview["task_count"] == 2
    assert snapshot(case.conn) == before
    response = client.post(BASE + ref + "/adopt", json={"write_token": preview["write_context"]["write_token"],
                           "request_key": "partial-candidate-real-adopt", "input": INTENT})
    assert response.status_code == 200, response.get_json()
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 2
    assert case.conn.execute("SELECT state FROM WorkbenchRunJobs WHERE run_ref=?", (result["run_ref"],)).fetchone()[0] == "partial"
    actual = list(case.conn.execute("SELECT op_id,machine_id,operator_id,start_time,end_time FROM Schedule ORDER BY op_id"))
    expected = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (ref,))]
    normalized = [tuple(row[:3]) + tuple(datetime.fromisoformat(value).isoformat() for value in row[3:]) for row in actual]
    assert normalized == [tuple(item[key] for key in (
        "op_id", "machine_id", "operator_id", "start_time", "end_time")) for item in sorted(expected, key=lambda item: item["op_id"])]


def test_partial_run_complete_candidate_creates_trial_without_false_scope_issue(trial_case, monkeypatch):
    case = trial_case
    ref = persisted_partial_run(case, monkeypatch)["candidates"][0]["candidate_ref"]
    svc = trial_service(case.conn)
    intent = {"base": {"candidate_ref": ref}}
    preview = svc.preview_create(intent)
    assert not any(row["code"] == "trial_base_incomplete" for row in preview["validation"]["issues"]), preview
    draft = svc.create(intent, preview["write_context"]["write_token"], "partial-candidate-real-trial")["data"]
    assert draft["tasks_complete"] is True and len(draft["tasks"]) == 2
    assert not any(row["code"] == "trial_base_incomplete" for row in draft["validation"]["issues"])
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_skipped_sibling_and_incomplete_engine_summary_still_cannot_be_adopted(trial_case, monkeypatch):
    case = trial_case
    result = persisted_partial_run(case, monkeypatch)
    skipped = service(case.conn).preview(result["candidates"][1]["candidate_ref"])
    assert skipped["validation"]["can_adopt"] is False
    assert skipped["validation"]["issues"][0]["code"] == "candidate_incomplete"
    ref = result["candidates"][0]["candidate_ref"]
    edit_artifact(case, ref, lambda artifact: artifact["summary"].update(failed_ops=1, success=False))
    blocked = service(case.conn).preview(ref)
    assert blocked["validation"]["can_adopt"] is False
    assert blocked["validation"]["issues"][0]["code"] == "candidate_unproven"
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_partial_run_does_not_bypass_post_preview_drift_from_another_connection(trial_case, monkeypatch):
    case = trial_case
    ref = persisted_partial_run(case, monkeypatch)["candidates"][0]["candidate_ref"]
    svc = service(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"] is True
    other = connect(case.path)
    try:
        other.execute("UPDATE BatchOperations SET unit_hours=2 WHERE id=?", (case.op_id,))
        other.commit()
    finally:
        other.close()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        svc.adopt(ref, preview["write_context"]["write_token"], "partial-candidate-stale-adopt", INTENT)
    assert exc.value.code == "snapshot_stale"
    assert snapshot(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_partial_comparison_keeps_explicit_material_stage_adoption(trial_case, monkeypatch):
    case = trial_case
    result = persisted_partial_run(case, monkeypatch, setup=lambda value, second: add_requirement(value, second, []),
                                   settings=case.settings(material_strategy="stage"), expected_tasks=1)
    ref = result["candidates"][0]["candidate_ref"]
    svc = service(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"] is True, preview
    assert preview["task_count"] == 1
    svc.adopt(ref, preview["write_context"]["write_token"], "partial-stage-real-adopt", INTENT)
    assert [row[0] for row in case.conn.execute("SELECT op_id FROM Schedule")] == [case.op_id]

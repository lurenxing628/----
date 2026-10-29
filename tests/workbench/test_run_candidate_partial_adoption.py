"""A real partial run (stage material deferral) keeps its schedulable candidate adoptable and guarded."""
import json
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import BASE, INTENT, api, service, snapshot
from tests.workbench.test_material_stage_release import add_requirement
from tests.workbench.trial_support import connect
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as _trial_case


@pytest.fixture(name="trial_case")
def _case(tmp_path):
    yield from _trial_case.__wrapped__(tmp_path)


def persisted_partial_run(case):
    """Real worker run whose second operation waits for material under stage release."""
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    case.conn.commit()
    accepted = case.accept(settings=case.settings(material_strategy="stage"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "partial" and result["result_persisted"] is True
    assert result["candidates"] and all(row["status"] == "completed" and row["task_count"] == 1
                                        for row in result["candidates"])
    return result


def test_partial_run_candidate_http_preview_and_real_adoption(trial_case):
    case = trial_case
    result = persisted_partial_run(case)
    ref = result["candidates"][0]["candidate_ref"]
    client = api(case)
    before = snapshot(case.conn)
    preview = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]
    assert preview["validation"]["can_adopt"] is True, preview
    assert preview["task_count"] == 1
    assert snapshot(case.conn) == before
    response = client.post(BASE + ref + "/adopt", json={"write_token": preview["write_context"]["write_token"],
                           "request_key": "partial-candidate-real-adopt", "input": INTENT})
    assert response.status_code == 200, response.get_json()
    assert [row[0] for row in case.conn.execute("SELECT op_id FROM Schedule")] == [case.op_id]
    assert case.conn.execute("SELECT state FROM WorkbenchRunJobs WHERE run_ref=?", (result["run_ref"],)).fetchone()[0] == "partial"
    actual = list(case.conn.execute("SELECT op_id,machine_id,operator_id,start_time,end_time FROM Schedule ORDER BY op_id"))
    expected = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (ref,))]
    normalized = [tuple(row[:3]) + tuple(datetime.fromisoformat(value).isoformat() for value in row[3:]) for row in actual]
    assert normalized == [tuple(item[key] for key in (
        "op_id", "machine_id", "operator_id", "start_time", "end_time")) for item in sorted(expected, key=lambda item: item["op_id"])]


def test_partial_run_candidate_creates_trial_without_false_scope_issue(trial_case):
    case = trial_case
    ref = persisted_partial_run(case)["candidates"][0]["candidate_ref"]
    svc = trial_service(case.conn)
    intent = {"base": {"candidate_ref": ref}}
    preview = svc.preview_create(intent)
    assert not any(row["code"] == "trial_base_incomplete" for row in preview["validation"]["issues"]), preview
    draft = svc.create(intent, preview["write_context"]["write_token"], "partial-candidate-real-trial")["data"]
    assert draft["tasks_complete"] is True and len(draft["tasks"]) == 1
    assert not any(row["code"] == "trial_base_incomplete" for row in draft["validation"]["issues"])
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_partial_run_does_not_bypass_post_preview_drift_from_another_connection(trial_case):
    case = trial_case
    ref = persisted_partial_run(case)["candidates"][0]["candidate_ref"]
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

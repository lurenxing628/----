"""One arrangement authority and unchanged legacy adoption/point replay."""

import json

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.plan.point_evidence import official_point_work
from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
from tests.workbench.ea_zero_duration_support import adopt, point_candidate
from tests.workbench.run_candidate_support import candidate_case as _candidate_case
from tests.workbench.run_candidate_support import (
    compute,
    connect,
    corrupt_update,
    retained,
    stored_candidate_artifact,
)


@pytest.mark.parametrize("legacy", [False, True])
def test_point_archive_keeps_original_bytes_after_adoption_and_reopen(candidate_case, legacy):
    case = candidate_case
    ref = point_candidate(case)
    if legacy:
        artifact = stored_candidate_artifact(case.conn, ref)
        artifact.pop("task_payload_source")
        corrupt_update(case.conn, "WorkbenchRunCandidates",
            "UPDATE WorkbenchRunCandidates SET artifact_json=? WHERE candidate_ref=?",
            (json.dumps(artifact, ensure_ascii=False), ref))
    original = case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0]
    with retained(case.conn):
        before, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(ref))
    assert before["tasks"][0]["event_kind"] == "point"
    plan = adopt(case, ref)
    with connect(case.path) as reopened, retained(reopened):
        work = official_point_work(reopened, plan["version"])
        assert work[case.op_id]["witness"].quantity == 3
        after, _ = WorkbenchRunCandidateQueryService(reopened).workspace(RunCandidateReadScope(ref))
        assert after == before
        assert reopened.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0] == original


@pytest.mark.parametrize("damage", ["missing_resource_field", "unknown_field"])
def test_task_body_structure_is_checked_without_a_second_arrangement_copy(candidate_case, damage):
    case = candidate_case
    _, refs = compute(case)
    row = case.conn.execute("SELECT row_ref,payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (refs[0],)).fetchone()
    payload = json.loads(row[1])
    if damage == "missing_resource_field":
        payload.pop("machine_id")
    else:
        payload["unexpected"] = "not-an-arrangement-field"
    corrupt_update(case.conn, "WorkbenchRunCandidateTasks",
        "UPDATE WorkbenchRunCandidateTasks SET payload_json=? WHERE row_ref=?", (json.dumps(payload), row[0]))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    assert error.value.code == "candidate_artifact_invalid"


def test_legacy_arrangement_copies_still_must_agree(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    artifact = stored_candidate_artifact(case.conn, refs[0])
    artifact.pop("task_payload_source")
    artifact["validated_payload"]["schedule_rows"][0]["start_time"] = "2026-09-09T09:00:00"
    corrupt_update(case.conn, "WorkbenchRunCandidates",
        "UPDATE WorkbenchRunCandidates SET artifact_json=? WHERE candidate_ref=?",
        (json.dumps(artifact), refs[0]))
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
    assert error.value.code == "candidate_artifact_invalid"

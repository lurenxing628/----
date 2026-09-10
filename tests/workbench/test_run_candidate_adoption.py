"""Real candidate -> read-only proof -> atomic official identity and immutable history."""

import json

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.workbench.execution_ledger import ExecutionLedgerService
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.test_run_candidate_adoption_support import (
    INTENT,
    KEY,
    assert_retained,
    candidate,
    preview,
    service,
    snapshot,
)
from tests.workbench.test_run_candidate_adoption_support import candidate_case as _case  # noqa: F401


def test_real_candidate_adoption_empty_baseline_and_receipt_replay(candidate_case):
    case = candidate_case
    ref = candidate(case)
    before = snapshot(case.conn)
    changes = case.conn.total_changes
    token = preview(case, ref)
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    result = service(case.conn).adopt(ref, token, KEY, INTENT)
    official = result["data"]["official_plan"]
    assert official["version"] == 1 and official["kind"] == "official"
    assert official["plan_ref"] != ref and official["baseline_ref"] is None
    repo = WorkbenchPlanIdentityRepository(case.conn)
    assert repo.resolve_plan(official["plan_ref"]) == WorkbenchPlanLocator(1, "adopted")
    assert len(repo.get_task_refs(official["plan_ref"], [{"schedule_id": row[0], "op_id": row[1], "version": row[2]}
        for row in case.conn.execute("SELECT id,op_id,version FROM Schedule")])) == 1
    assert_retained(before, snapshot(case.conn))
    saved = snapshot(case.conn)
    replay = service(case.conn, enabled=False).adopt(ref, "expired-token", KEY, INTENT)
    assert replay["replayed"] is True and replay["receipt_ref"] == result["receipt_ref"]
    assert snapshot(case.conn) == saved
    assert service(case.conn).lookup(ref, KEY) == replay
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(ref, token, KEY, {**INTENT, "reason": "different"})
    assert error.value.code == "request_key_conflict"
    # New official is a real executable plan under the existing identity resolver.
    assert ExecutionLedgerService(case.conn)._current_plan()["capabilities"]["report_actual"] is True


def test_all_old_rows_types_blobs_and_version_sequence_retained(candidate_case):
    case = candidate_case
    case.plan(3, [case.op_id])
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=3", (b"\x00\xffold-history",))
    case.plan(7, [case.op_id])
    case.conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (40)")
    case.conn.execute("CREATE TABLE AdoptionLegacyProbe(id INTEGER PRIMARY KEY, value)")
    for index, value in enumerate((None, 7, 1.25, "old-text", b"\x00\x80\xff")):
        case.conn.execute("INSERT INTO AdoptionLegacyProbe VALUES (?,?)", (index, value))
    case.conn.execute("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','old','old',?)", (b"\xffaudit",))
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    result = service(case.conn).adopt(ref, token, KEY, INTENT)
    official = result["data"]["official_plan"]
    assert official["version"] == 41 and official["baseline_ref"] == case.plan_ref(7)
    assert_retained(before, snapshot(case.conn))
    assert case.conn.execute("SELECT typeof(result_summary) FROM ScheduleHistory WHERE version=3").fetchone()[0] == "blob"
    audit = json.loads(case.conn.execute("SELECT detail FROM OperationLogs WHERE action='adopt_run_candidate'").fetchone()[0])
    assert audit["candidate_ref"] == ref and audit["plan_ref"] == official["plan_ref"]
    assert audit["declared_operator"] == INTENT["declared_operator"]
    assert audit["application_operator"] != audit["declared_operator"]


@pytest.mark.parametrize("legacy", [False, True])
def test_completed_actuals_and_original_identity_are_not_rewritten(candidate_case, legacy):
    case = candidate_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id])
    old_task = case.task(1, case.op_id)
    if legacy:
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish")
    else:
        case.command("create", old_task, case.values(3))
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    result = service(case.conn).adopt(ref, token, KEY, INTENT)
    version = result["data"]["official_plan"]["version"]
    rows = {row["op_id"]: dict(row) for row in case.conn.execute("SELECT * FROM Schedule WHERE version=?", (version,))}
    assert rows[case.op_id]["start_time"] == "2026-09-09 08:00:00"
    assert rows[case.op_id]["end_time"] == "2026-09-09 10:00:00"
    assert rows[case.op_id]["lock_status"] == "locked"
    assert rows[successor]["start_time"] >= rows[case.op_id]["end_time"]
    assert old_task != case.task(version, case.op_id)
    assert_retained(before, snapshot(case.conn))

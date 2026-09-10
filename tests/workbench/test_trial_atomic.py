"""Independent connections, receipts, failures and exact rollback boundaries."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from tests.workbench.trial_support import (
    CommitFailureConnection,
    change,
    connect,
    create,
    official,
    service,
    snapshot,
)
from tests.workbench.trial_support import trial_case as trial_case


def intent(case, draft, start="2026-09-09T13:00:00"):
    return {"task_ref": draft["tasks"][0]["task_ref"], "machine_ref": case.ref("machine", "M2"),
            "operator_ref": case.ref("operator", "O2"), "start": start}


def test_replay_ignores_expired_context_but_rejects_changed_payload(trial_case):
    case = trial_case
    draft = create(case)
    result = change(case, draft)
    before = snapshot(case.conn)
    replayed = service(case.conn).change(draft["draft_ref"], intent(case, draft), "expired",
                                        "trial-change-00000001")
    assert replayed == dict(result, replayed=True)
    assert snapshot(case.conn) == before
    assert service(case.conn).lookup("trial-change-00000001") == replayed
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).change(draft["draft_ref"], intent(case, draft, "2026-09-09T14:00:00"), "expired",
                                 "trial-change-00000001")
    assert error.value.code == "request_key_conflict"
    assert snapshot(case.conn) == before


def test_live_fact_change_between_preview_and_create_rejected(trial_case):
    case = trial_case
    value = official(case)
    preview = service(case.conn).preview_create(value)
    case.conn.execute("UPDATE Operators SET status='inactive' WHERE operator_id='O1'")
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).create(value, preview["write_context"]["write_token"], "trial-create-00000001")
    assert error.value.code == "stale_write"
    assert snapshot(case.conn) == before


def test_racing_different_intents_one_commits_one_stale(trial_case):
    case = trial_case
    draft = create(case)
    barrier = Barrier(2)
    inputs = [intent(case, draft, start) for start in ("2026-09-09T13:00:00", "2026-09-09T14:00:00")]

    def work(index):
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait()
                try:
                    return service(conn).change(draft["draft_ref"], inputs[index], draft["write_context"]["write_token"],
                                                "trial-race-0000000" + str(index))["result"]
                except WorkbenchCommandRejected as exc:
                    return exc.code
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, range(2)))
    assert sorted(results) == ["committed", "stale_write"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialChanges").fetchone()[0] == 1


def test_same_request_race_has_one_change_and_one_receipt(trial_case):
    case = trial_case
    draft = create(case)
    value = intent(case, draft)
    barrier = Barrier(2)

    def work(_):
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait()
                return service(conn).change(draft["draft_ref"], value, draft["write_context"]["write_token"], "trial-race-same-00001")
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(work, range(2)))
    assert sorted(row["replayed"] for row in result) == [False, True]
    assert result[0]["receipt_ref"] == result[1]["receipt_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialChanges").fetchone()[0] == 1


@pytest.mark.parametrize("acknowledge", [False, True])
def test_commit_result_unknown_then_query_original_receipt(trial_case, acknowledge):
    case = trial_case
    draft = create(case)
    conn = connect(case.path, CommitFailureConnection)
    conn.fail_commit, conn.acknowledge_only = True, acknowledge
    before = snapshot(case.conn)
    try:
        with pytest.raises(WorkbenchCommandUncertain):
            service(conn).change(draft["draft_ref"], intent(case, draft), draft["write_context"]["write_token"], "trial-unknown-0000001")
    finally:
        conn.close()
    result = service(case.conn).lookup("trial-unknown-0000001")
    assert bool(result) is acknowledge
    if not acknowledge:
        assert snapshot(case.conn) == before
    else:
        assert result["data"]["tasks"][0]["machine_ref"] == case.ref("machine", "M2")
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialChanges").fetchone()[0] == 1


def test_receipt_failure_rolls_back_all_time_and_resource_fields(trial_case):
    case = trial_case
    draft = create(case)
    case.conn.execute("""CREATE TEMP TRIGGER test_trial_receipt_failure BEFORE INSERT ON WorkbenchCommandReceipts
        WHEN NEW.action='trial.change' BEGIN SELECT RAISE(ABORT,'injected receipt insert failure'); END""")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        change(case, draft)
    assert snapshot(case.conn) == before
    assert service(case.conn).lookup("trial-change-00000001") is None


def test_foreign_draft_task_cannot_be_used(trial_case):
    case = trial_case
    base = official(case)
    first = create(case, base)
    second = create(case, base, key="trial-create-00000002")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).change(second["draft_ref"], intent(case, first), second["write_context"]["write_token"], "trial-change-00000001")
    assert error.value.code == "task_not_in_draft"
    assert snapshot(case.conn) == before

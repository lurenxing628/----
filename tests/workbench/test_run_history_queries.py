"""Precise query/public DTO contracts, without production connections or writes."""

import pytest

from core.models.workbench_run_history import STATES
from tests.workbench.run_history_support import BASE, api, corrupt, dump, read, seed
from tests.workbench.run_history_support import history_case as _history_case


def test_all_states_and_awaiting_are_explicit_and_read_only(history_case):
    case = history_case
    refs = {state: seed(case, state) for state in STATES}
    pending = seed(case, "running", stage="awaiting_reconciliation")
    client, statements = api(case)
    before = dump(case.conn)
    result = read(client)
    rows = result["data"]["runs"]
    assert set(item["run_ref"] for item in rows) == set(refs.values()) | {pending}
    assert result["data"]["page"] == {"number": 1, "size": 20, "total": 7, "has_more": False}
    for item in rows:
        succeeded = item["state"] in ("complete", "partial")
        assert item["candidate_count"] == item["task_count"] == int(succeeded)
        assert item["completion_semantics"] == "execution_state_only"
        assert item["constraint_verification"] == "not_checked_by_history"
        assert item["scope_summary"]["batch_count"] == 1
        assert item["task_count_basis"] == "persisted_rows_across_candidates"
    pending_dto = next(item for item in rows if item["run_ref"] == pending)
    assert pending_dto["recovery_required"] and pending_dto["recovery_reason"]["code"] == "awaiting_reconciliation"
    assert pending_dto["counts_final"] is False
    assert dump(case.conn) == before
    assert all(not sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP")) for sql in statements)


def test_exact_pagination_and_empty_filter_never_select_latest(history_case):
    case = history_case
    refs = [seed(case, accepted="2026-09-10T12:00:00") for _ in range(5)]
    client, _ = api(case)
    first = read(client, size=2, order="asc")
    token = first["meta"]["snapshot_ref"]
    actual = list(first["data"]["runs"])
    for page in (2, 3):
        result = read(client, size=2, order="asc", page=page, snapshot_ref=token)
        assert result["meta"]["snapshot_ref"] == token
        actual.extend(result["data"]["runs"])
    assert [item["run_ref"] for item in actual] == sorted(refs)
    assert read(client, size=2, order="asc", page=4, snapshot_ref=token)["data"]["runs"] == []
    empty = read(client, state="failed")["data"]
    assert empty["runs"] == [] and empty["page"]["total"] == 0 and empty["run_count"] == 5


def test_accepted_dates_are_inclusive_factory_local_not_plan_dates(history_case):
    case = history_case
    outside = seed(case, accepted="2026-09-09T23:59:59.999999")
    lower = seed(case, accepted="2026-09-10T00:00:00")
    upper = seed(case, accepted="2026-09-10T23:59:59.999999")
    seed(case, accepted="2026-09-11T00:00:00")
    client, _ = api(case)
    result = read(client, accepted_from="2026-09-10", accepted_to="2026-09-10")
    assert [row["run_ref"] for row in result["data"]["runs"]] == [upper, lower]
    assert outside not in {row["run_ref"] for row in result["data"]["runs"]}
    assert result["data"]["time_scope"] == {"accepted_from": "2026-09-10", "accepted_to": "2026-09-10",
        "field": "accepted_at", "boundary": "inclusive_dates", "time_basis": "factory_local"}
    assert read(client, accepted_from="2026-09-25", accepted_to="2026-09-25")["data"]["runs"] == []


@pytest.mark.parametrize("query", ["foo=1", "state=queued&state=failed", "page=1&page=1", "snapshot_ref=x&snapshot_ref=y",
    "state=completed", "state=", "page=0", "page=01", "page=-1", "page=1000001", "size=51", "size=1.0", "size=true",
    "sort=task_count", "order=DESC", "accepted_from=2026-09-10", "accepted_to=2026-09-10",
    "accepted_from=2026-09-11&accepted_to=2026-09-10", "accepted_from=2026-02-30&accepted_to=2026-03-01",
    "accepted_from=2026-09-10T00:00:00Z&accepted_to=2026-09-11", "accepted_from=2026-9-1&accepted_to=2026-09-11"])
def test_reject_unknown_duplicate_or_noncanonical_query(history_case, query):
    client, _ = api(history_case)
    response = client.get(BASE + "?" + query)
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("sort", ["started_at", "finished_at"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_sorts_are_chronological_with_nulls_last(history_case, sort, order):
    case = history_case
    null_ref = seed(case)
    early = seed(case, "complete", accepted="2026-09-08T01:00:00")
    later = seed(case, "failed", accepted="2026-09-09T01:00:00")
    client, _ = api(case)
    rows = read(client, sort=sort, order=order)["data"]["runs"]
    assert [row["run_ref"] for row in rows] == ([early, later] if order == "asc" else [later, early]) + [null_ref]


def test_missing_admission_scope_values_have_null_and_reason_without_live_fallback(history_case):
    case = history_case
    ref = seed(case, settings={"private_unknown": "private-secret", "ready_check": "yes"})
    client, _ = api(case)
    item = read(client)["data"]["runs"][0]
    assert item["run_ref"] == ref and item["scope_summary"]["batch_count"] is None
    assert item["scope_summary"]["ready_check"] is None
    assert len(item["scope_summary"]["data_gaps"]) == 6
    assert "private-secret" not in str(item)


def test_current_resource_rename_and_same_key_recreation_do_not_rebind_history(history_case):
    case = history_case
    seed(case, "complete")
    client, _ = api(case)
    first = read(client)
    case.conn.execute("UPDATE Machines SET name='Renamed'")
    case.conn.execute("DELETE FROM OperatorMachine")
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL WHERE machine_id='M1'")
    case.conn.execute("DELETE FROM Machines WHERE machine_id='M1'")
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Replacement','T1')")
    case.conn.commit()
    assert read(client, snapshot_ref=first["meta"]["snapshot_ref"])["data"] == first["data"]


def test_missing_run_schema_is_not_installed(history_case):
    case = history_case
    case.conn.execute("DROP TRIGGER wb_run_admission_immutable")
    case.conn.commit()
    client, _ = api(case)
    before = dump(case.conn)
    response = client.get(BASE)
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "run_schema_unavailable"
    assert dump(case.conn) == before


@pytest.mark.parametrize("state", STATES)
def test_every_state_filter_is_exact(history_case, state):
    case = history_case
    refs = {value: seed(case, value) for value in STATES}
    client, _ = api(case)
    result = read(client, state=state)["data"]
    assert result["page"]["total"] == 1 and result["run_count"] == len(STATES)
    assert [row["run_ref"] for row in result["runs"]] == [refs[state]]


def test_failed_runs_show_their_reason_and_old_records_only_recover_user_text(history_case, monkeypatch):
    # 排产记录给出失败原因；旧版本只把原因记在诊断里，只取当时写给用户的业务原因，SQL、路径等原文不外露。
    from core.models.workbench_run_compute import CandidateRunInputError
    from core.services.workbench.run.worker import WorkbenchRunWorker

    case = history_case
    reason = "工作日历里有班次时间读不出来或者填得不对，这次排产没有开始。请到工作日历按 08:30 这样改好。"
    legacy = {"code": "candidate_computation_failed", "message": "候选排产没有完成。请到「排产记录」查看原因，改好后重新做排产检查。"}

    def failed(key, error, old=False):
        def fail(conn, row, on_progress):
            raise error
        with monkeypatch.context() as patch:
            if old:
                patch.setattr(WorkbenchRunWorker, "_public_error", lambda self, exc: dict(legacy, code=getattr(exc, "reason", legacy["code"])))
            accepted = case.accept(key=key)
            with pytest.raises(type(error)):
                WorkbenchRunWorker(case.conn, compute_runner=fail).execute(accepted["run_ref"])
        return accepted["run_ref"]

    current = failed("run-request-00000001", CandidateRunInputError("invalid_calendar_shift", reason))
    old_input = failed("run-request-00000002", CandidateRunInputError("invalid_calendar_shift", reason), old=True)
    old_bug = failed("run-request-00000003", RuntimeError("sqlite3.OperationalError: no such column x_y in /home/aps/x.py"), old=True)
    complete, unrecorded = seed(case, "complete"), seed(case, "failed")
    client, _ = api(case)
    rows = {row["run_ref"]: row["error"] for row in read(client)["data"]["runs"]}
    assert rows[current] == rows[old_input] == {"code": "invalid_calendar_shift", "message": reason}
    assert rows[old_bug] == {"code": "candidate_computation_failed", "message": "本次候选计算失败。请联系维护人员，再重新做排产检查。"}
    assert rows[complete] is None and rows[unrecorded] is None
    assert "x_y" not in str(rows) and "排产记录」查看原因" not in str(rows)

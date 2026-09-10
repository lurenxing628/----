"""Persisted candidate history remains exact, read-only and separate from trials."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_candidate_history import read_candidate_history
from tests.workbench.test_run_candidate_adoption_support import INTENT, KEY, preview, service
from tests.workbench.test_run_candidate_support import api, compute, connect, retained
from tests.workbench.test_run_candidate_support import candidate_case as _case  # noqa: F401


@pytest.mark.parametrize("has_baseline", [False, True])
def test_original_candidate_receipt_history_survives_later_official_and_reopen(candidate_case, has_baseline):
    case = candidate_case
    if has_baseline:
        case.plan(7, [case.op_id])
    run_ref, refs = compute(case)
    with retained(case.conn):
        empty, _ = read_candidate_history(case.conn, refs[0])
    assert empty["items"] == [] and empty["total"] == 0 and empty["state"] == "empty"
    token = preview(case, refs[0])
    receipt = service(case.conn).adopt(refs[0], token, KEY, INTENT)
    official = receipt["data"]["official_plan"]
    with retained(case.conn):
        data, state = read_candidate_history(case.conn, refs[0])
        assert read_candidate_history(case.conn, refs[1])[0]["items"] == []
    row, = data["items"]
    assert row["candidate_ref"] == refs[0] and row["run_ref"] == run_ref
    assert row["receipt_ref"] == receipt["receipt_ref"] and row["request_key"] == KEY
    assert row["official_plan"]["plan_ref"] == official["plan_ref"]
    assert row["official_plan"]["version"] == official["version"]
    assert row["can_open"] and row["evidence_gaps"] == []
    assert row["adoption"]["reason"] == INTENT["reason"]
    assert row["adoption"]["declared_operator"] == INTENT["declared_operator"]
    assert row["adoption"]["baseline_ref"] == (case.plan_ref(7) if has_baseline else None)
    case.plan(official["version"] + 1, [case.op_id])
    conn = connect(case.path)
    try:
        before = case.path.read_bytes()
        assert read_candidate_history(conn, refs[0]) == (data, state)
        assert conn.total_changes == 0 and case.path.read_bytes() == before
    finally:
        conn.close()


def test_missing_or_changed_original_audit_is_not_an_empty_or_replacement_history(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    receipt = service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
    version = receipt["data"]["official_plan"]["version"]
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=NULL WHERE version=?", (version,))
    case.conn.commit()
    with retained(case.conn), pytest.raises(WorkbenchCommandRejected) as error:
        read_candidate_history(case.conn, refs[0])
    assert error.value.code == "candidate_adoption_history_invalid"


def test_changed_official_rows_keep_original_receipt_but_block_original_plan_button(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    receipt = service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
    version = receipt["data"]["official_plan"]["version"]
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09 15:00:00' WHERE version=?", (version,))
    case.conn.commit()
    with retained(case.conn):
        data, _ = read_candidate_history(case.conn, refs[0])
    row, = data["items"]
    assert row["receipt_ref"] == receipt["receipt_ref"] and not row["can_open"]
    assert row["official_plan"]["plan_ref"] == receipt["data"]["official_plan"]["plan_ref"]
    assert row["evidence_gaps"] and data["state"] == "available"


def test_read_endpoints_are_get_only_exact_ref_and_byte_zero_write(candidate_case):
    case = candidate_case
    run_ref, refs = compute(case)
    receipt = service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
    client, statements = api(case)
    before = case.path.read_bytes()
    for leaf in ("analysis", "adoptions"):
        path = "/api/workbench/v1/scheduling/candidates/" + refs[0] + "/" + leaf
        response = client.get(path)
        assert response.status_code == 200, response.get_data(as_text=True)
        result = response.get_json()
        assert result["data"]["candidate_ref"] == refs[0] and result["data"]["run_ref"] == run_ref
        assert response.headers["Cache-Control"] == "no-store"
        assert client.post(path).status_code == 405
        wrong = client.get(path.replace(refs[0], receipt["data"]["official_plan"]["plan_ref"]))
        assert wrong.status_code == 404 and wrong.get_json()["committed"] is False
        assert client.get(path, query_string=[("snapshot_ref", "a"), ("snapshot_ref", "b")]).status_code == 400
    assert case.path.read_bytes() == before
    assert not any(sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"} for sql in statements)

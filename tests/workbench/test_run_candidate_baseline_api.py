"""GET-only hook, strict scope/snapshot binding and fixed query count."""

import pytest

from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_candidate_baseline_support import api, original_plan
from tests.workbench.run_candidate_support import BASE, compute, read, retained
from tests.workbench.run_candidate_support import candidate_case as _candidate_case


def test_hook_real_get_and_snapshot_unchanged_by_current_metadata(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    client, statements = api(case)
    path = "/candidates/" + refs[0] + "/baseline"
    with retained(case.conn):
        first = read(client, path)
        assert len([sql for sql in statements if sql.startswith("SELECT")]) <= 14
        token = first["meta"]["snapshot_ref"]
        again = read(client, path, snapshot_ref=token)
        assert again["data"] == first["data"] and again["meta"]["snapshot_ref"] == token
    case.conn.execute("UPDATE Machines SET name='Changed after admission'")
    case.conn.commit()
    assert read(client, path, snapshot_ref=token)["data"] == first["data"]
    assert client.post(BASE + path).status_code == 405


@pytest.mark.parametrize("query", ["version=7", "plan_ref=old", "row_ref=" + "a" * 48, "operation_ref=" + "a" * 48,
                                  "run_ref=" + "a" * 48, "page=1", "batch_ref=123", "sort=cost", "sort=start&sort=end",
                                  "range_start=2026-09-09T08:00:00", "range_start=bad&range_end=bad",
                                  "range_start=2026-09-09T08:00:00Z&range_end=2026-09-10T08:00:00Z"])
def test_bad_arguments_fail_before_sql(candidate_case, query):
    client, statements = api(candidate_case)
    response = client.get(BASE + "/candidates/" + "a" * 48 + "/baseline?" + query)
    assert response.status_code == 400 and statements == []


def test_scope_candidate_run_and_workspace_tokens_cannot_be_interchanged(candidate_case):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    accepted = case.accept(key="bu-snapshot-other-run")
    other = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["candidates"][0]["candidate_ref"]
    client, _ = api(case)
    path = "/candidates/" + refs[0] + "/baseline"
    first = read(client, path)
    token = first["meta"]["snapshot_ref"]
    for target, query in ((path, {"sort": "start"}), ("/candidates/" + refs[1] + "/baseline", {}),
                          ("/candidates/" + other + "/baseline", {}), ("/candidates/" + refs[0], {})):
        response = client.get(BASE + target, query_string={"snapshot_ref": token, **query})
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "snapshot_stale"
    workspace = read(client, "/candidates/" + refs[0])
    response = client.get(BASE + path, query_string={"snapshot_ref": workspace["meta"]["snapshot_ref"]})
    assert response.status_code == 409
    response = client.get(BASE + path, query_string={"batch_ref": "a" * 48})
    assert response.status_code == 404


def test_wrong_identity_kind_and_missing_schema_are_not_current_fallbacks(candidate_case):
    case = candidate_case
    formal = original_plan(case)
    _, refs = compute(case)
    client, _ = api(case)
    with retained(case.conn):
        for ref in (formal, case.task(7, case.op_id), "f" * 48):
            assert client.get(BASE + "/candidates/" + ref + "/baseline").status_code == 404
    case.conn.execute("DROP TABLE WorkbenchRunCandidateTasks")
    case.conn.commit()
    with retained(case.conn):
        response = client.get(BASE + "/candidates/" + refs[0] + "/baseline")
    assert response.status_code == 503

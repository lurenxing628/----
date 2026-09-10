"""Database discovery survives browser loss; bounded reads never select latest."""

import json
import subprocess
import sys

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_catalog import TrialCatalogScope
from core.services.workbench.trial_catalog import WorkbenchTrialCatalogService
from tests.workbench.trial_support import BASE, api, candidate, change, connect, create, official, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def test_fresh_browser_discovers_original_draft_and_saved_scenario(trial_case):
    case = trial_case
    original = official(case)
    first = create(case, original)
    second = create(case, original, key="trial-create-00000002")
    saved = service(case.conn).save(first["draft_ref"], {"name": "Night shift proposal"},
        first["write_context"]["write_token"], "trial-save-0000000001")["data"]
    case.plan(2, [case.op_id], start="2026-09-10T08:00:00", end="2026-09-10T11:00:00")
    client = api(case)
    before = snapshot(case.conn)
    draft_directory = client.get(BASE + "/drafts?status=editing").get_json()["data"]
    assert draft_directory["selection"] is None
    assert draft_directory["page"]["total"] == 1
    item = draft_directory["items"][0]
    assert item["draft_ref"] == second["draft_ref"]
    assert item["base"] == original["base"]
    assert item["base_display_name"] == "正式计划 v1"
    assert client.get(item["detail_target"]).get_json()["data"]["base"] == original["base"]
    scenario_directory = client.get(BASE + "/scenarios").get_json()["data"]
    entry = scenario_directory["items"][0]
    assert entry["display_name"] == "Night shift proposal"
    assert entry["scenario_ref"] == saved["scenario_ref"]
    assert entry["base"] == original["base"]
    assert client.get(entry["detail_target"]).get_json()["data"] == saved
    assert snapshot(case.conn) == before


def test_paging_counts_whole_filtered_directory_and_snapshot_reuse(trial_case):
    case = trial_case
    original = official(case)
    refs = {create(case, original, key="trial-catalog-" + str(i).zfill(8))["draft_ref"] for i in range(5)}
    client = api(case)
    first = client.get(BASE + "/drafts?size=2")
    assert first.status_code == 200
    assert first.headers["Cache-Control"] == "no-store"
    body = first.get_json()
    assert body["data"]["page"] == {"number": 1, "size": 2, "total": 5, "pages": 3}
    token = body["meta"]["snapshot_ref"]
    found = {row["draft_ref"] for row in body["data"]["items"]}
    for page in (2, 3):
        response = client.get(BASE + "/drafts", query_string={"size": 2, "page": page, "snapshot_ref": token})
        assert response.status_code == 200, response.get_json()
        found.update(row["draft_ref"] for row in response.get_json()["data"]["items"])
    assert found == refs
    assert client.get(BASE + "/drafts?size=2&page=4").status_code == 400


def test_directory_snapshot_stale_after_change_and_not_auto_rebased(trial_case):
    case = trial_case
    draft = create(case)
    client = api(case)
    token = client.get(BASE + "/drafts").get_json()["meta"]["snapshot_ref"]
    change(case, draft)
    response = client.get(BASE + "/drafts", query_string={"snapshot_ref": token})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "snapshot_stale"
    assert client.get(BASE + "/drafts").status_code == 200


def test_exact_candidate_filter_never_becomes_plan_ref(trial_case):
    case = trial_case
    original = candidate(case)
    draft = create(case, original)
    conn = connect(case.path)
    try:
        conn.execute("PRAGMA query_only=ON")
        rows, _ = WorkbenchTrialCatalogService(conn).catalog(TrialCatalogScope("drafts", base_kind="candidate_ref",
            base_ref=original["base"]["candidate_ref"]))
        assert rows["items"][0]["base"] == original["base"]
        assert rows["items"][0]["draft_ref"] == draft["draft_ref"]
        empty, _ = WorkbenchTrialCatalogService(conn).catalog(TrialCatalogScope("drafts", base_kind="plan_ref",
            base_ref=original["base"]["candidate_ref"]))
        assert empty["state"] == "empty" and empty["selection"] is None
    finally:
        conn.close()


def test_discarded_records_discoverable_without_reopening(trial_case):
    case = trial_case
    draft = create(case)
    service(case.conn).discard(draft["draft_ref"], {"confirm": True}, draft["write_context"]["write_token"], "trial-discard-0000001")
    result, _ = WorkbenchTrialCatalogService(case.conn).catalog(TrialCatalogScope("drafts", status="discarded"))
    item = result["items"][0]
    assert item["draft_ref"] == draft["draft_ref"]
    assert item["status"] == "discarded" and item["capabilities"]["edit_draft"] is False
    assert item["validation_state"] == "not_evaluated" and item["capabilities"]["adopt"] is False


@pytest.mark.parametrize("query", ["size=0", "size=51", "page=-1", "status=latest", "page=1&page=2", "source=demo", "base_kind=plan_ref"])
def test_catalog_rejects_unknown_or_unbounded_queries(trial_case, query):
    client = api(trial_case)
    assert client.get(BASE + "/drafts?" + query).status_code == 400


def test_row_bound_is_explicit_and_catalog_reads_no_snapshot_payloads(trial_case, monkeypatch):
    import data.repositories.workbench_trial_catalog_repo as module

    case = trial_case
    original = official(case)
    for i in range(3):
        create(case, original, key="trial-catalog-" + str(i).zfill(8))
    statements = []
    case.conn.set_trace_callback(statements.append)
    try:
        WorkbenchTrialCatalogService(case.conn).catalog(TrialCatalogScope("drafts", size=1))
    finally:
        case.conn.set_trace_callback(None)
    assert not any(field in sql.lower() for field in ("admission_json", "snapshot_json", "current_json", "original_json") for sql in statements)
    monkeypatch.setattr(module, "MAX_CATALOG_ROWS", 2)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchTrialCatalogService(case.conn).catalog(TrialCatalogScope("drafts", size=1))
    assert error.value.code == "query_too_large"


def test_cold_process_discovers_and_restores_without_browser_or_old_token(trial_case):
    case = trial_case
    draft = create(case)
    code = """
import json, sqlite3, sys
from flask import Flask
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_catalog import TrialCatalogScope
from core.services.workbench.trial import WorkbenchTrialService
from core.services.workbench.trial_catalog import WorkbenchTrialCatalogService
from web.routes.workbench.write_context import issue_write_context, validate_write_context
conn = sqlite3.connect(sys.argv[1])
conn.row_factory = sqlite3.Row
with Flask('trial-cold-process').app_context():
    catalog, _ = WorkbenchTrialCatalogService(conn).catalog(TrialCatalogScope('drafts'))
    ref = catalog['items'][0]['draft_ref']
    svc = WorkbenchTrialService(conn, context_factory=issue_write_context, context_validator=validate_write_context)
    data = svc.get(ref)
    try:
        svc.discard(ref, {'confirm': True}, sys.argv[2], 'trial-cold-rejected-0001')
    except WorkbenchCommandRejected as exc:
        outcome = exc.code
    else:
        outcome = 'unexpected_write'
    print(json.dumps({'draft_ref': ref, 'task_ref': data['tasks'][0]['task_ref'],
                      'original': data['tasks'][0]['original'], 'base': data['base'],
                      'old_token_outcome': outcome, 'changes': conn.total_changes}))
conn.close()
"""
    completed = subprocess.run([sys.executable, "-c", code, str(case.path), draft["write_context"]["write_token"]],
                               capture_output=True, text=True, timeout=30, check=True)
    result = json.loads(completed.stdout)
    assert result["draft_ref"] == draft["draft_ref"]
    assert result["task_ref"] == draft["tasks"][0]["task_ref"]
    assert result["base"] == draft["base"] and result["original"] == draft["tasks"][0]["original"]
    assert result["old_token_outcome"] == "stale_write"
    assert result["changes"] == 0

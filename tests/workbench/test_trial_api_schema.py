"""Only registration hooks, exact DDL, readonly GETs and explicit business status."""

import hashlib
import json

import pytest

from core.infrastructure.workbench_trial_schema import contract_issues, install, objects
from tests.workbench.trial_support import BASE, CommitFailureConnection, api, create, official, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def test_frozen_v27_trial_ddl_and_readonly_contract(trial_case):
    conn = trial_case.conn
    digest = hashlib.sha256(json.dumps(objects(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == "f025c779d645c7a39666681c0c285eddf119a172cb93e339809e44282b972164"
    before = snapshot(conn)
    assert contract_issues(conn) == []
    with pytest.raises(RuntimeError):
        install(conn)
    conn.execute("BEGIN")
    install(conn)
    conn.rollback()
    assert snapshot(conn) == before


def test_partial_schema_is_not_repaired(trial_case):
    conn = trial_case.conn
    conn.execute("DROP INDEX idx_wb_trial_status")
    conn.commit()
    assert contract_issues(conn) == ["missing_trial_schema:idx_wb_trial_status"]
    before = snapshot(conn)
    conn.execute("BEGIN")
    with pytest.raises(RuntimeError):
        install(conn)
    conn.rollback()
    assert snapshot(conn) == before


def test_api_lifecycle_200_conflict_not_valid_and_no_hidden_publish(trial_case):
    case = trial_case
    intent = official(case)
    client = api(case)
    preview = client.post(BASE + "/drafts/preview", json=intent)
    assert preview.status_code == 200, preview.get_json()
    token = preview.get_json()["data"]["write_context"]["write_token"]
    result = client.post(BASE + "/drafts", json={"input": intent, "write_token": token, "request_key": "trial-create-00000001"})
    assert result.status_code == 200, result.get_json()
    draft = result.get_json()["data"]
    value = {"task_ref": draft["tasks"][0]["task_ref"], "machine_ref": case.ref("machine", "M2"),
             "operator_ref": case.ref("operator", "O1"), "start": "2026-09-09T13:00:00"}
    response = client.post(BASE + "/drafts/" + draft["draft_ref"] + "/change", json={"input": value,
        "write_token": draft["write_context"]["write_token"], "request_key": "trial-change-00000001"})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["validation"]["constraints_status"] == "blocked"
    assert data["validation"]["can_adopt"] is False
    before = snapshot(case.conn)
    read = client.get(BASE + "/drafts/" + draft["draft_ref"])
    assert read.status_code == 200
    assert read.headers["Cache-Control"] == "no-store"
    assert snapshot(case.conn) == before
    assert client.get(BASE + "/commands/trial-change-00000001").get_json()["data"]["state"] == "committed"
    assert client.get(BASE + "/commands/trial-change-missing-00001").get_json()["data"]["state"] == "not_observed"
    assert not any("adopt" in rule.rule or "publish" in rule.rule for rule in case.app.url_map.iter_rules())


def test_unknown_ref_and_ambiguous_base_never_use_latest(trial_case):
    case = trial_case
    official(case)
    client = api(case)
    before = snapshot(case.conn)
    assert client.get(BASE + "/drafts/" + "a" * 48).status_code == 404
    assert client.post(BASE + "/drafts/preview", json={"base": {"plan_ref": "a" * 48, "candidate_ref": "b" * 48}}).status_code == 400
    assert snapshot(case.conn) == before


def test_unknown_result_uses_trial_receipt_route_without_shared_registration(trial_case):
    case = trial_case
    draft = create(case)
    client = api(case, CommitFailureConnection)
    CommitFailureConnection.fail_commit = True
    try:
        response = client.post(BASE + "/drafts/" + draft["draft_ref"] + "/discard", json={"input": {"confirm": True},
            "write_token": draft["write_context"]["write_token"], "request_key": "trial-api-unknown-0001"})
    finally:
        CommitFailureConnection.fail_commit = False
    assert response.status_code == 500, response.get_json()
    error = response.get_json()
    assert error["committed"] == "unknown"
    assert error["error"]["request_ref"]
    target = error["error"]["result_target"]
    assert target == BASE + "/commands/trial-api-unknown-0001"
    assert client.get(target).get_json()["data"]["state"] == "not_observed"

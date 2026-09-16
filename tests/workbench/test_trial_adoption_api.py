"""HTTP method/input boundaries, original-key recovery and unknown ACK response."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from flask import g, request

from core.services.workbench.trial_adoption import WorkbenchTrialAdoptionService
from tests.workbench.trial_adoption_support import BASE, INTENT, KEY, api, saved_scenario
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import CommitFailureConnection, snapshot


def test_real_http_preview_confirm_and_receipt(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    before = snapshot(case.conn)
    response = client.post(path + "/adopt-preview", json={})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    preview = response.get_json()["data"]
    assert preview["scenario_ref"] == saved["scenario_ref"] and preview["draft_ref"] == saved["draft_ref"]
    assert preview["validation"]["can_adopt"] and snapshot(case.conn) == before
    body = {"write_token": preview["write_context"]["write_token"], "request_key": KEY, "input": INTENT}
    response = client.post(path + "/adopt", json=body)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    receipt = client.get(path + "/adoption-commands/" + KEY).get_json()["data"]
    assert receipt["state"] == "committed" and receipt["receipt"]["receipt_ref"] == result["receipt_ref"]
    assert client.get(path + "/adopt").status_code == 405
    unknown = client.get(path + "/adoption-commands/not-yet-seen-request").get_json()["data"]
    assert unknown == {"state": "not_observed", "receipt": None, "may_be_in_flight": True, "can_retry_automatically": False}


@pytest.mark.parametrize("ready_status", ["no", "partial"])
def test_readiness_warning_becomes_visible_adoption_blocker(trial_case, ready_status):
    case = trial_case
    case.conn.execute("UPDATE Batches SET ready_status=?", (ready_status,))
    case.conn.commit()
    saved = saved_scenario(case, changed=False)
    original_issues = saved["validation"]["issues"]
    assert original_issues and all(row["severity"] == "warning" for row in original_issues)
    client = api(case)
    before = snapshot(case.conn)
    response = client.post(BASE + saved["scenario_ref"] + "/adopt-preview", json={})
    assert response.status_code == 200, response.get_json()
    envelope = response.get_json()
    # Exercise the actual strict frontend parser against the real HTTP DTO.
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Node is required for the TrialAdoptionAPI source contract"
    source = Path(__file__).resolve().parents[2] / "frontend/workbench/app/TrialAdoptionAPI.js"
    script = """
const fs = require('fs'), assert = require('assert');
global.window = {};
require(process.argv[1]);
const value = JSON.parse(fs.readFileSync(0, 'utf8')), api = window.TrialAdoptionAPI;
const parsed = api.preview(value.response, api.source(value.saved.scenario_ref, value.saved));
assert.equal(parsed.validation.can_adopt, false);
assert.equal(parsed.validation.issues[0].code, 'batch_not_ready');
assert(parsed.validation.issues[0].message.includes('齐套'));
assert.equal(parsed.write_context.write_token, null);
"""
    result = subprocess.run([node, "-e", script, str(source)],
                            input=json.dumps({"response": envelope, "saved": saved}),
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    data = envelope["data"]
    assert data["validation"]["issues"] == data["write_context"]["blocked_reasons"]
    assert all(row["severity"] == "blocker" for row in data["validation"]["issues"])
    assert data["write_context"]["capabilities"]["trial.scenario.adopt"] is False
    assert snapshot(case.conn) == before
    assert saved["validation"]["issues"] == original_issues


@pytest.mark.parametrize("suffix,body", [
    ("/adopt-preview?scope=visible", {}), ("/adopt-preview", {"candidate_ref": "a" * 48}),
    ("/adopt", {"input": INTENT}),
    ("/adopt", {"input": dict(INTENT, version=99), "request_key": KEY, "write_token": "bad"}),
    ("/adopt", {"input": dict(INTENT, confirm=False), "request_key": KEY, "write_token": "bad"}),
])
def test_client_cannot_supply_replacement_scope_or_identity(trial_case, suffix, body):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    before = snapshot(case.conn)
    response = client.post(BASE + saved["scenario_ref"] + suffix, json=body)
    assert response.status_code in (400, 422) and response.get_json()["committed"] is False
    assert snapshot(case.conn) == before


def test_disabled_host_gate_blocks_without_an_independent_scenario_flag(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case, enabled=False)
    case.app.config["WORKBENCH_TRIAL_ADOPTION_ENABLED"] = True
    path = BASE + saved["scenario_ref"]
    assert WorkbenchTrialAdoptionService(case.conn).preview(saved["scenario_ref"])["validation"]["can_adopt"] is False
    assert not client.post(path + "/adopt-preview", json={}).get_json()["data"]["validation"]["can_adopt"]
    response = client.post(path + "/adopt", json={"write_token": "fake", "request_key": KEY, "input": INTENT})
    assert response.status_code == 409 and response.get_json()["committed"] is False
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 1


def test_http_ack_unknown_points_to_original_scenario_and_key(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case, factory=CommitFailureConnection)
    path = BASE + saved["scenario_ref"]

    @case.app.before_request
    def lose_ack():
        if request.path.endswith("/adopt"):
            g.db.fail_commit = g.db.acknowledge_only = True

    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    response = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert response.status_code == 500
    value = response.get_json()
    assert value["committed"] == "unknown" and value["error"]["request_key"] == KEY
    assert value["error"]["result_target"] == path + "/adoption-commands/" + KEY
    assert value["error"]["retryable"] is False
    receipt = client.get(value["error"]["result_target"]).get_json()["data"]
    assert receipt["state"] == "committed" and receipt["receipt"]["data"]["scenario_ref"] == saved["scenario_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 2

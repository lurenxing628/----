"""HTTP method/input boundaries, original-key recovery and unknown ACK response."""


from flask import g, request

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

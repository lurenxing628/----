"""Real Flask JSON boundary, explicit activation, receipt lookup and no timeout dispatch."""

import pytest
from flask import Blueprint, g

from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

BASE = "/api/workbench/v1/scheduling"


@pytest.fixture(name="jobs_api")
def jobs_api(job_case):
    case = job_case
    bp = Blueprint("av_jobs", __name__)
    register_preflight_routes(bp)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = case.conn

    calls = []
    case.app.extensions["workbench_run_dispatcher"] = calls.append
    case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = True
    return case.app.test_client(), case, calls


def intent(client, case):
    preflight = client.post(BASE + "/preflight", json=case.settings())
    assert preflight.status_code == 200
    data = preflight.get_json()["data"]
    assert data["write_context"]["write_token"] is None
    assert data["write_context"]["capabilities"]["scheduling.run"] is False
    ref = data["input_ref"]
    preview = client.post(BASE + "/runs/preview", json={"input_ref": ref})
    assert preview.status_code == 200
    assert preview.get_json()["meta"]["as_of"] and preview.get_json()["meta"]["snapshot_ref"]
    token = preview.get_json()["data"]["write_context"]["write_token"]
    return {"input_ref": ref, "write_token": token, "request_key": "run-request-00000001"}


def test_accept_query_replay_dispatch_once(jobs_api):
    client, case, calls = jobs_api
    value = intent(client, case)
    first = client.post(BASE + "/runs", json=value)
    assert first.status_code == 202
    ref = first.get_json()["run_ref"]
    assert calls == [ref]
    for _ in range(3):
        replay = client.post(BASE + "/runs", json={**value, "write_token": None})
        assert replay.status_code == 202 and replay.get_json()["replayed"]
        query = client.get(BASE + "/runs/" + ref)
        assert query.status_code == 200 and query.get_json()["data"]["state"] == "queued"
        assert query.get_json()["meta"]["as_of"] and query.get_json()["meta"]["snapshot_ref"]
    assert calls == [ref]
    receipt = client.get(BASE + "/requests/" + value["request_key"])
    assert receipt.get_json()["data"]["run"]["run_ref"] == ref
    assert receipt.get_json()["meta"]["as_of"] and receipt.get_json()["meta"]["snapshot_ref"]
    assert client.get(BASE + "/requests/" + value["request_key"] + "?rerun=true").status_code == 400
    assert query.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("missing", ["flag", "dispatcher"])
def test_host_must_connect_and_enable_both_capability_conditions(jobs_api, missing):
    client, case, calls = jobs_api
    value = intent(client, case)
    if missing == "flag":
        case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = False
    else:
        del case.app.extensions["workbench_run_dispatcher"]
    preview = client.post(BASE + "/runs/preview", json={"input_ref": value["input_ref"]})
    assert preview.get_json()["data"]["write_context"]["capabilities"]["scheduling.run"] is False
    response = client.post(BASE + "/runs", json=value)
    assert response.status_code == 503 and response.get_json()["committed"] is False
    assert calls == []


def test_dispatch_failure_keeps_committed_acceptance_visible(jobs_api):
    client, case, calls = jobs_api
    value = intent(client, case)

    def fail(ref):
        calls.append(ref)
        raise RuntimeError("host worker queue unavailable")

    case.app.extensions["workbench_run_dispatcher"] = fail
    response = client.post(BASE + "/runs", json=value)
    assert response.status_code == 202 and response.get_json()["dispatch_pending"] is True
    ref = response.get_json()["run_ref"]
    assert client.get(BASE + "/runs/" + ref).get_json()["data"]["state"] == "queued"
    assert client.post(BASE + "/runs", json=value).get_json()["replayed"]
    assert calls == [ref]


def test_accept_storage_uncertainty_has_correct_request_lookup(jobs_api, monkeypatch):
    client, case, calls = jobs_api
    value = intent(client, case)

    def fail(*args, **kwargs):
        raise RuntimeError("receipt disk failed")

    monkeypatch.setattr(WorkbenchCommandRepository, "insert", fail)
    response = client.post(BASE + "/runs", json=value)
    data = response.get_json()
    assert response.status_code == 500 and data["committed"] == "unknown"
    assert data["error"]["result_target"] == BASE + "/requests/" + value["request_key"]
    assert calls == []


@pytest.mark.parametrize("value", [None, [], {}, {"input_ref": "x"}, {"input_ref": "x", "write_token": None, "request_key": "short"}])
def test_malformed_admission_is_not_dispatched(jobs_api, value):
    client, case, calls = jobs_api
    response = client.post(BASE + "/runs", json=value)
    assert response.status_code == 400 and calls == []


def test_expired_preflight_cannot_be_resurrected_by_fresh_preview(jobs_api, monkeypatch):
    import web.public_token_registry as tokens

    client, case, calls = jobs_api
    value = intent(client, case)
    old_now = tokens.time.time()
    monkeypatch.setattr(tokens.time, "time", lambda: old_now + 1000)
    assert client.post(BASE + "/runs/preview", json={"input_ref": value["input_ref"]}).status_code == 409
    response = client.post(BASE + "/runs", json=value)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert calls == []

"""Maintenance exclusion belongs to one request, not a count or shared app."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import g

from tests.workbench.test_request_lifecycle_support import LifecycleCase, http_json, http_server
from tests.workbench.test_request_lifecycle_support import request_case as _request_case  # noqa: F401
from web.bootstrap.workbench_request_lifecycle import close_workbench_request_connection


def test_exact_owner_exclusion_requires_closed_connection_and_other_request_completion(request_case):
    case, shared = request_case, {}
    other = LifecycleCase(case.path)
    owner_ready, other_entered = threading.Event(), threading.Event()
    owner_release = threading.Event()

    @case.app.get("/owner")
    def owner():
        assert other_entered.wait(10)
        lease = case.gate.maintenance_owner()
        shared["lease"] = lease
        assert lease.drain() is False  # Owner's g.db is still open.
        with pytest.raises(RuntimeError, match="Request threads cannot"):
            lease.drain(wait=True)
        close_workbench_request_connection(g.pop("db"))
        assert lease.drain() is False  # Other app has its own active request.
        owner_ready.set()
        assert owner_release.wait(10)
        assert lease.drain() is True
        lease.resume()
        return {"ok": True}

    @other.app.get("/borrower")
    def borrower():
        other_entered.set()
        assert owner_ready.wait(10)
        with pytest.raises(RuntimeError, match="cannot borrow"):
            shared["lease"].drain()
        with pytest.raises(RuntimeError, match="already stopping"):
            other.gate.maintenance_owner()
        return {"ok": True}

    with http_server(case.app) as port1, http_server(other.app) as port2, ThreadPoolExecutor(2) as pool:
        first = pool.submit(http_json, port1, "/owner", method="GET")
        second = pool.submit(http_json, port2, "/borrower", method="GET")
        try:
            assert owner_ready.wait(10)
            assert http_json(port1, "/workbench")[0] == 503
            assert http_json(port2, "/workbench")[0] == 503
            assert second.result(10)[0] == 200
            assert shared["lease"].drain(wait=True, timeout=1) is True
        finally:
            owner_release.set()
        assert first.result(10)[0] == 200
    assert case.gate.status["state"] == "accepting"
    with pytest.raises(RuntimeError, match="expired"):
        shared["lease"].drain()
    assert case.gate.shutdown()


@pytest.mark.parametrize("shutdown", [False, True])
def test_owner_completion_never_implicitly_reopens_and_shutdown_cannot_be_undone(request_case, shutdown):
    case, saved = request_case, []

    @case.app.get("/maintenance")
    def maintenance():
        lease = case.gate.maintenance_owner()
        saved.append(lease)
        close_workbench_request_connection(g.pop("db"))
        assert lease.drain()
        if shutdown:
            with ThreadPoolExecutor(1) as pool:
                assert pool.submit(case.gate.shutdown, False).result(5) is False
            with pytest.raises(RuntimeError, match="stopping"):
                lease.resume()
        return {"ok": True}

    with pytest.raises(RuntimeError, match="exact active request owner"):
        case.gate.maintenance_owner()
    assert case.app.test_client().get("/maintenance", buffered=True).status_code == 200
    assert case.app.test_client().post("/workbench", buffered=True).status_code == 503
    with pytest.raises(RuntimeError, match="expired"):
        saved[0].drain()
    assert case.gate.shutdown()

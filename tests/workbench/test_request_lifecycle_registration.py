"""DB identity, idempotence, request-thread waits and same-DB app isolation."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from flask import Flask, Response, g

from tests.workbench.test_request_lifecycle_support import LifecycleCase, http_json, http_server
from tests.workbench.test_request_lifecycle_support import request_case as _request_case  # noqa: F401
from web.bootstrap.workbench_request_lifecycle import (
    install_workbench_request_lifecycle,
    lookup_workbench_request_lifecycle,
    stop_workbench_requests_for_database,
)


def test_install_is_db_lock_free_and_normalized_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "never-created.sqlite"
    app = Flask("cf-no-side-effects")
    app.config["DATABASE_PATH"] = str(path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("install must not open DB or acquire launcher locks")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr("web.bootstrap.launcher_runtime_lock.acquire_runtime_lock", forbidden)
    monkeypatch.setattr("web.bootstrap.launcher_runtime_lock.release_runtime_lock", forbidden)
    with ThreadPoolExecutor(max_workers=4) as pool:
        gates = list(pool.map(lambda _: install_workbench_request_lifecycle(app), range(8)))
    assert len({id(gate) for gate in gates}) == 1
    assert len(app.before_request_funcs[None]) == 1
    assert lookup_workbench_request_lifecycle(str(tmp_path) + "/./never-created.sqlite") is gates[0]
    assert not path.exists() and not list(tmp_path.iterdir())
    assert gates[0].shutdown()


@pytest.mark.parametrize("path", [None, "", " ", ":memory:", "file:shared?mode=memory", 12, "x\x00y"])
def test_unknown_database_never_guesses_another_registered_database(request_case, path):
    with pytest.raises(ValueError, match="explicit file database"):
        lookup_workbench_request_lifecycle(path)
    with pytest.raises(ValueError, match="explicit file database"):
        stop_workbench_requests_for_database(path)
    assert request_case.gate.status["state"] == "accepting"


def test_explicit_unregistered_database_is_not_a_quiescence_proof(request_case, tmp_path):
    path = tmp_path / "different.sqlite"
    assert lookup_workbench_request_lifecycle(path) is None
    with pytest.raises(RuntimeError, match="No request lifecycle registered"):
        stop_workbench_requests_for_database(path)
    assert request_case.gate.status["state"] == "accepting"


def test_database_drift_and_closed_reinstall_are_rejected(request_case, tmp_path):
    case = request_case
    case.app.config["DATABASE_PATH"] = str(tmp_path / "changed.sqlite")
    with pytest.raises(RuntimeError, match="database changed"):
        install_workbench_request_lifecycle(case.app)
    with pytest.raises(RuntimeError, match="configuration changed"):
        case.app.test_client().get("/workbench")
    assert case.opened == []
    case.app.config["DATABASE_PATH"] = case.path
    assert case.gate.shutdown()
    with pytest.raises(RuntimeError, match="already closed"):
        install_workbench_request_lifecycle(case.app)
    other = Flask("cf-reinstall")
    other.config["DATABASE_PATH"] = case.path
    with pytest.raises(RuntimeError, match="stopping, closed"):
        install_workbench_request_lifecycle(other)


def test_late_install_refuses_to_put_admission_after_open_db(tmp_path):
    app = Flask("cf-late-install")
    app.config["DATABASE_PATH"] = str(tmp_path / "never.sqlite")
    app.before_request(lambda: None)
    with pytest.raises(RuntimeError, match="before DB-opening"):
        install_workbench_request_lifecycle(app)


def test_request_and_stream_threads_cannot_wait_for_themselves(request_case):
    case = request_case
    seen = []

    def check():
        for wait in (False, True):
            with pytest.raises(RuntimeError, match="Request threads cannot"):
                case.gate.shutdown(wait=wait)
            with pytest.raises(RuntimeError, match="Request threads cannot"):
                case.gate.drain(wait=wait)
        seen.append(True)
        assert case.gate.status["state"] == "accepting"

    @case.app.get("/self-drain")
    def self_drain():
        check()
        def stream():
            check()  # No Flask request context here; WSGI frame still forbids it.
            yield b"ok"
        return Response(stream())

    assert case.app.test_client().get("/self-drain", buffered=True).data == b"ok"
    assert seen == [True, True] and case.gate.shutdown()


def test_suspended_response_owner_cannot_wait_after_request_context_has_popped(request_case):
    case = request_case

    @case.app.get("/suspended")
    def suspended():
        return Response(iter((b"first", b"second")))

    response = case.app.test_client().get("/suspended", buffered=False)
    assert case.gate.status["active"] == 1
    with pytest.raises(RuntimeError, match="unclosed HTTP response"):
        case.gate.shutdown()
    assert case.gate.status["state"] == "accepting"
    response.close()
    assert case.gate.shutdown()


@pytest.mark.parametrize("same_app", [False, True])
def test_two_requests_count_both_and_other_db_stays_independent(request_case, tmp_path, same_app):
    first = request_case
    second = (SimpleNamespace(app=first.app, gate=first.gate, entered=threading.Event(), release=threading.Event())
              if same_app else LifecycleCase(first.path))
    assert second.gate is first.gate
    other = Flask("cf-other-database")
    other.config["DATABASE_PATH"] = str(tmp_path / "other.sqlite")
    other_gate = install_workbench_request_lifecycle(other)
    assert other_gate is not first.gate

    def add_hold(case, name):
        def hold():
            assert g.db.execute("SELECT 1").fetchone()[0] == 1
            case.entered.set()
            assert case.release.wait(10)
            return {"ok": True}
        case.app.add_url_rule("/" + name, name, hold, methods=["GET"])

    add_hold(first, "hold_one")
    add_hold(second, "hold_two")
    with http_server(first.app) as port1, http_server(second.app) as port2, ThreadPoolExecutor(2) as pool:
        one = pool.submit(http_json, port1, "/hold_one", method="GET")
        two = pool.submit(http_json, port2, "/hold_two", method="GET")
        try:
            assert first.entered.wait(10) and second.entered.wait(10)
            assert first.gate.status["active"] == 2
            assert first.gate.shutdown(wait=False) is False
            assert other_gate.status["state"] == "accepting"
            first.release.set()
            assert one.result(10)[0] == 200
            assert second.gate.status["active"] == 1
            assert second.gate.shutdown(timeout=0.05) is False
            for port in (port1, port2):
                assert http_json(port, "/hold", method="GET")[0] == 503
        finally:
            first.release.set()
            second.release.set()
        assert two.result(10)[0] == 200
    assert stop_workbench_requests_for_database(first.path) is True
    assert first.gate.status["active"] == 0 and other_gate.shutdown()

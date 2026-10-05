"""Real threaded HTTP waits until SQLite commit/rollback AND response close."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.workbench.request_lifecycle_support import PATHS, http_json, http_server
from tests.workbench.request_lifecycle_support import request_case as _request_case  # noqa: F401
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock


@pytest.mark.parametrize("rollback", [False, True])
def test_http_transaction_and_close_finish_before_lock_release(request_case, tmp_path, rollback):
    case = request_case
    case.app.config["TESTING"] = False
    case.rollback = rollback
    case.close_release.clear()
    scope = str(tmp_path / "launcher")
    payload = acquire_runtime_lock(scope, db_path=case.path)
    lock = Path(db_scope_lock_path(case.path))
    original = lock.read_bytes()
    done = threading.Event()

    def shutdown():
        assert case.gate.shutdown(wait=True)
        assert case.counts() == ((0, 0) if rollback else (1, 1))
        release_runtime_lock(scope, db_path=case.path)
        done.set()

    try:
        with http_server(case.app) as port, ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(http_json, port, PATHS[0])
            try:
                assert case.entered.wait(10)
                assert case.gate.shutdown(wait=False) is False
                drain = pool.submit(shutdown)
                assert not done.wait(0.1)
                assert lock.read_bytes() == original and Path(payload["path"]).exists()
                opened, statements = len(case.opened), len(case.statements)
                for path in PATHS:
                    status, response = http_json(port, path)
                    assert status == 503
                    if path.startswith("/api/workbench/"):
                        assert set(response) == {"ok", "committed", "error"}
                        assert response["committed"] is False
                        assert response["error"]["code"] == "request_lifecycle_stopping"
                        assert set(response["error"]) == {"code", "message", "fields", "retryable", "request_ref"}
                        assert "没有执行" in response["error"]["message"]
                    else:
                        assert "没有执行" in response.decode("utf-8")
                assert (len(case.opened), len(case.statements)) == (opened, statements)
                case.release.set()
                assert case.close_entered.wait(10)
                assert not done.wait(0.1) and lock.read_bytes() == original
            finally:
                case.release.set()
                case.close_release.set()
            assert writer.result(10)[0] == (500 if rollback else 200)
            drain.result(10)
        assert done.is_set() and not lock.exists() and case.gate.status["active"] == 0
    finally:
        release_runtime_lock(scope, db_path=case.path)


def test_close_failure_poison_survives_factory_logging_and_cleanup_retry(request_case):
    case = request_case

    class BrokenClose(sqlite3.Connection):
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise sqlite3.OperationalError("CF injected close failure")
            super().close()

    case.connection_factory = BrokenClose
    case.release.set()
    response = case.app.test_client().post(PATHS[0], buffered=True)
    assert response.status_code == 200
    assert case.gate.status["active"] == 0
    assert case.gate.status["cleanup_failures"] == 1
    assert case.gate.shutdown(timeout=0) is False
    assert case.counts() == (1, 1)

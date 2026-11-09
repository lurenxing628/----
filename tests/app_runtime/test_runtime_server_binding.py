"""Exercise real Windows sockets, including a reusable competing listener."""

from __future__ import annotations

import os
import socket
import threading
import urllib.request
from typing import Any, cast

import pytest
from flask import Flask

from web.bootstrap import factory, runtime_server

windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows exclusive listener semantics")


def test_windows_bind_publishes_reserved_endpoint_without_reverse_dns(monkeypatch):
    calls = []

    class Listener:
        def setsockopt(self, level, option, value):
            calls.append(("setsockopt", level, option, value))

        def bind(self, endpoint):
            calls.append(("bind", endpoint))

        def getsockname(self):
            return ("127.0.0.1", 32123)

    def reject_reverse_dns(host):
        raise AssertionError("Binding a loopback listener must not resolve its host name")

    monkeypatch.setattr(socket, "SO_EXCLUSIVEADDRUSE", -5, raising=False)
    monkeypatch.setattr(socket, "getfqdn", reject_reverse_dns)
    server = cast(Any, object.__new__(runtime_server._WindowsRuntimeServer))
    server.socket = Listener()
    server.server_address = ("127.0.0.1", 0)
    server.server_bind()
    assert calls == [("setsockopt", socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1),
                     ("bind", ("127.0.0.1", 0))]
    assert server.server_address == ("127.0.0.1", 32123)
    assert server.server_name == "127.0.0.1"
    assert server.server_port == 32123


@windows_only
def test_listener_rejects_even_a_reusable_competing_bind():
    server = runtime_server.create_runtime_server(Flask("exclusive-listener"), "127.0.0.1", 0)
    try:
        assert server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE) == 1
        assert server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as competitor:
            competitor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError):
                competitor.bind(server.server_address)
    finally:
        server.server_close()


@windows_only
def test_competing_reusable_listener_is_not_stolen():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupier.bind(("127.0.0.1", 0))
        occupier.listen()
        endpoint = occupier.getsockname()
        with pytest.raises(runtime_server.RuntimeBindError):
            runtime_server.create_runtime_server(Flask("blocked-listener"), *endpoint)
        assert occupier.getsockname() == endpoint
        assert occupier.fileno() != -1


@windows_only
def test_fallback_serves_on_the_same_reserved_socket(monkeypatch):
    app = Flask("fallback-listener")

    @app.route("/")
    def marker():
        return "reserved-listener"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupier.bind(("127.0.0.1", 0))
        occupier.listen()
        busy_port = occupier.getsockname()[1]
        monkeypatch.setattr(runtime_server, "candidate_ports", lambda preferred: [preferred])
        server = runtime_server.prepare_runtime_server(app, "127.0.0.1", busy_port)
        descriptor = server.socket.fileno()
        host, actual_port = server.server_address[:2]
        assert actual_port not in (0, busy_port)
        thread = threading.Thread(target=factory.serve_runtime_app, kwargs={"server": server}, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://{host}:{actual_port}/", timeout=5) as response:
                assert response.read() == b"reserved-listener"
            assert server.socket.fileno() == descriptor
            assert occupier.getsockname()[1] == busy_port
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        assert not thread.is_alive()


@windows_only
def test_failed_bind_does_not_leak_a_socket(monkeypatch):
    sockets = []
    original_bind = runtime_server._WindowsRuntimeServer.server_bind

    def record_bind(server):
        sockets.append(server.socket)
        return original_bind(server)

    monkeypatch.setattr(runtime_server._WindowsRuntimeServer, "server_bind", record_bind)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.bind(("127.0.0.1", 0))
        occupier.listen()
        endpoint = occupier.getsockname()
        for _ in range(3):
            with pytest.raises(runtime_server.RuntimeBindError):
                runtime_server.create_runtime_server(Flask("failed-listener"), *endpoint)
        assert len(sockets) == 3
        assert all(listener.fileno() == -1 for listener in sockets)
    server = runtime_server.create_runtime_server(Flask("released-listener"), *endpoint)
    server.server_close()


@windows_only
def test_failed_listen_releases_the_bound_socket(monkeypatch):
    sockets = []

    def fail_listen(listener, backlog):
        sockets.append(listener)
        raise OSError("controlled listen failure")

    with monkeypatch.context() as patch:
        patch.setattr(socket.socket, "listen", fail_listen)
        with pytest.raises(runtime_server.RuntimeBindError, match="controlled listen failure"):
            runtime_server.create_runtime_server(Flask("activation-failure"), "127.0.0.1", 0)
    assert len(sockets) == 1
    assert sockets[0].fileno() == -1


def test_prepared_runtime_server_fallback_matches_published_contract_endpoint(tmp_path, monkeypatch):
    import web.bootstrap.entrypoint as entrypoint_mod
    from web.bootstrap.launcher_contracts import read_runtime_contract_result

    runtime_dir = tmp_path / "app"
    runtime_dir.mkdir()
    db_path = tmp_path / "data" / "aps.db"
    db_path.parent.mkdir()
    log_dir = runtime_dir / "logs"
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.delenv("APS_HOST", raising=False)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.bind(("127.0.0.1", 0))
        occupier.listen()
        busy_port = occupier.getsockname()[1]

        with pytest.raises(runtime_server.RuntimeBindError):
            runtime_server.create_runtime_server(Flask("occupied-port-check"), "127.0.0.1", busy_port)

        monkeypatch.setenv("APS_PORT", str(busy_port))
        monkeypatch.setattr(runtime_server, "candidate_ports", lambda preferred: [preferred])

        app = Flask("contract-endpoint-match")
        app.config.update(
            DEBUG=False,
            DATABASE_PATH=str(db_path),
            LOG_DIR=str(log_dir),
            BACKUP_DIR=str(runtime_dir / "backups"),
            EXCEL_TEMPLATE_DIR=str(runtime_dir / "templates"),
            APP_UI_MODE="new_ui",
        )
        app.extensions["workbench_startup_maintenance_records"] = ()
        monkeypatch.setattr(
            "web.bootstrap.workbench_system_restore.install_workbench_system_restore_host",
            lambda target_app, runtime: None,
        )

        class _StubRuntime:
            ready = True

            def __init__(self, target_db: str) -> None:
                self.db_path = target_db

            class proof:
                @staticmethod
                def verify() -> None:
                    return None

            @staticmethod
            def shutdown(wait: bool = True) -> bool:
                return True

        observed = {}

        def _serve(*, server):
            contract_res = read_runtime_contract_result(str(log_dir))
            assert contract_res.ok and contract_res.payload is not None
            observed["server_address"] = server.server_address[:2]
            observed["contract_endpoint"] = (contract_res.payload["host"], contract_res.payload["port"])
            observed["env_endpoint"] = (os.environ.get("APS_HOST"), int(os.environ["APS_PORT"]))

        from dataclasses import replace

        deps = replace(
            entrypoint_mod._default_deps("new_ui"),
            create_app=lambda: app,
            install_run_runtime=lambda target_app, runtime_lock: _StubRuntime(str(db_path)),
            serve_runtime_app=_serve,
            resolve_startup_debug_flag=lambda: False,
            should_own_runtime_resources=lambda debug: True,
            should_use_runtime_reloader=lambda debug: False,
        )
        rc = entrypoint_mod.app_main("new_ui", anchor_file=str(runtime_dir / "app.py"), argv=[], deps=deps)
        assert rc == 0
        actual_host, actual_port = observed["server_address"]
        assert actual_host == "127.0.0.1"
        assert actual_port not in (0, busy_port)
        assert observed["contract_endpoint"] == (actual_host, actual_port)
        assert observed["env_endpoint"] == (actual_host, actual_port)

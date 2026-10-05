"""web.runtime_host 接缝：bootstrap 装进 app.extensions 的进程能力，routes 只经这里读取。"""

import pytest
from flask import Flask

from web import runtime_host


def _app():
    app = Flask("runtime-host-seam")
    return app


def test_request_shutdown_requires_an_installed_host():
    app = _app()
    with pytest.raises(RuntimeError, match="runtime host is not installed"):
        runtime_host.request_shutdown(app)
    app.extensions[runtime_host.RUNTIME_HOST_EXTENSION] = {"request_shutdown": "not callable"}
    with pytest.raises(RuntimeError, match="runtime host is not installed"):
        runtime_host.request_shutdown(app)


def test_install_runtime_host_routes_shutdown_requests_with_the_logger():
    app, calls = _app(), []
    runtime_host.install_runtime_host(app, request_shutdown=lambda logger=None: calls.append(logger) or 1)
    assert runtime_host.request_shutdown(app, logger="log") is True
    assert calls == ["log"]


class _Host(runtime_host.SystemRestoreHost):
    status = {"restart_required": False}

    def execute(self, service, *, request_key, intent, guard, audit, restore_runner):
        raise AssertionError("not exercised")

    def execute_file(self, service, *, request_key, action, intent, guard, audit):
        raise AssertionError("not exercised")

    def capture_maintenance_records(self):
        raise AssertionError("not exercised")

    def automatic_maintenance(self):
        raise AssertionError("not exercised")

    def audit_restore_result(self, result):
        raise AssertionError("not exercised")


def test_restore_host_needs_both_keys_pointing_at_one_contract_instance():
    app, host = _app(), _Host()
    assert runtime_host.restore_host(app) is None
    app.extensions[runtime_host.RESTORE_HOST_EXTENSION] = host
    assert runtime_host.restore_host(app) is None, "缺守卫键不算已安装"
    app.extensions[runtime_host.RESTORE_HOST_GUARD] = _Host()
    assert runtime_host.restore_host(app) is None, "两把钥匙必须指向同一实例"
    app.extensions[runtime_host.RESTORE_HOST_GUARD] = host
    assert runtime_host.restore_host(app) is host
    app.extensions[runtime_host.RESTORE_HOST_EXTENSION] = object()
    assert runtime_host.restore_host(app) is None, "不满足契约的对象不当宿主"

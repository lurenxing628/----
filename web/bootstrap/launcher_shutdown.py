"""DB-free, exact-server stop transport, outside business HTTP admission."""

import secrets
import threading
from typing import Optional

from werkzeug.serving import BaseWSGIServer
from werkzeug.wrappers import Response

from core.infrastructure.backup import BackupManager, MaintenanceWindowError
from core.infrastructure.migration_common import fallback_log
from core.models.enums import YesNo

HOST_STOP_PATH = "/system/runtime/host-stop"


class RuntimeHostStopTransport:
    def __init__(self, app):
        self.app = app
        self.server: Optional[BaseWSGIServer] = None
        self._lock = threading.Lock()
        self._requested = False

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO") != HOST_STOP_PATH:
            return self.app(environ, start_response)
        status, code = self._stop(environ)
        response = Response('{"app":"aps","status":"' + status + '"}', status=code,
                            content_type="application/json", headers={"Cache-Control": "no-store"})
        return response(environ, start_response)

    def _stop(self, environ):
        expected = str(self.app.config.get("APS_RUNTIME_SHUTDOWN_TOKEN") or "")
        provided = str(environ.get("HTTP_X_APS_SHUTDOWN_TOKEN") or "")
        if (environ.get("REMOTE_ADDR") not in ("127.0.0.1", "::1") or not expected
                or not provided or not secrets.compare_digest(expected, provided)):
            return "forbidden", 403
        if (environ.get("REQUEST_METHOD") != "POST" or environ.get("QUERY_STRING")
                or environ.get("CONTENT_LENGTH", "") not in ("", "0")
                or environ.get("HTTP_TRANSFER_ENCODING")):
            return "invalid_stop_request", 400
        with self._lock:
            if self.server is None:
                return "shutdown_unavailable", 503
            if not self._requested:
                self._requested = True
                threading.Thread(target=self.server.shutdown, name="runtime-host-stop", daemon=True).start()
        # This is acceptance, NOT proof of HTTP/worker drain or lock release.
        return "shutting_down", 202


class RuntimeExitBackupManager(BackupManager):
    def __init__(self, app):
        super().__init__(db_path=app.config["DATABASE_PATH"], backup_dir=app.config["BACKUP_DIR"],
                         keep_days=app.config.get("BACKUP_KEEP_DAYS", 7), logger=app.logger)
        self._system_restore_app = app


def drain_before_exit_backup(manager):
    from .workbench_request_lifecycle import lookup_workbench_request_lifecycle
    from .workbench_run_runtime import stop_workbench_runs_for_database
    from .workbench_system_restore_recovery import assert_exit_system_restore_ready

    assert_exit_system_restore_ready(manager)
    gate = lookup_workbench_request_lifecycle(manager.db_path)
    if gate is not None and gate.shutdown(wait=True) is not True:
        raise RuntimeError("HTTP responses or database connections have not safely finished")
    if stop_workbench_runs_for_database(manager.db_path) is not True:
        raise RuntimeError("Workbench background worker has not stopped")
    assert_exit_system_restore_ready(manager)


def read_exit_backup_enabled(manager, connect):
    conn = None
    try:
        conn = connect(manager.db_path)
        from core.services.system import SystemConfigService

        cfg = SystemConfigService(conn, logger=manager.logger).get_snapshot_readonly(
            backup_keep_days_default=int(getattr(manager, "keep_days", 7) or 7))
        return cfg.auto_backup_enabled == YesNo.YES.value
    except Exception as exc:
        fallback_log(manager.logger, "error", "读取退出自动备份配置失败：" + str(exc))
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                fallback_log(manager.logger, "error", "关闭退出自动备份配置连接失败：" + str(exc))
                raise


def run_exit_backup(manager, is_enabled):
    from .workbench_system_restore_recovery import assert_exit_system_restore_ready

    try:
        drain_before_exit_backup(manager)
        enabled = is_enabled(manager)
    except Exception as exc:
        fallback_log(manager.logger, "error", "退出自动备份已跳过：维护状态或停止屏障未核实：" + str(exc))
        return False
    if enabled is not True:
        if enabled is None:
            fallback_log(manager.logger, "warning", "退出自动备份已跳过：读取配置失败。")
        else:
            fallback_log(manager.logger, "info", "退出自动备份已跳过：auto_backup_enabled=no。")
        return False
    try:
        assert_exit_system_restore_ready(manager)
        manager.backup(suffix="exit")
        return True
    except MaintenanceWindowError as exc:
        fallback_log(manager.logger, "warning" if exc.code == "busy" else "error", "退出自动备份已跳过：" + exc.message)
        return False
    except Exception as exc:
        fallback_log(manager.logger, "error", "退出自动备份失败：" + str(exc))
        return False

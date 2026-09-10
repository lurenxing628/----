"""DB-free maintenance receipt transport; never forwards a privileged app request.

The host can also serve RestoreStatusTransport(None, journal, status) alone when
startup refuses a pending journal. That recovery server must keep the original
launcher lock and must not construct the normal app, open SQLite or start workers.
"""

import json
import re
import uuid

from werkzeug.wrappers import Response

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key

BASE = "/api/workbench/v1/system"


class RecoveryJournal:
    """Invalid configuration still permits host status, never a database read."""

    def __init__(self, directory, database_path):
        self.directory, self.database_path = directory, database_path

    def _journal(self):
        from core.services.workbench.system_journal import SystemMaintenanceJournal
        return SystemMaintenanceJournal(self.directory, self.database_path)

    def lookup(self, key):
        return self._journal().lookup(key)

    def records(self):
        return self._journal().records()

    def public(self, row, replayed=False):
        return self._journal().public(row, replayed)


class RestoreStatusTransport:
    def __init__(self, application, journal, status):
        self.application, self.journal, self.status = application, journal, status

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        status = self.status()
        stopped = status["state"] != "ready"
        if stopped and environ.get("REQUEST_METHOD") == "GET" and path in ("/", "/workbench", "/workbench/", "/workbench/trial"):
            from .workbench_system_restore_view import recovery_response
            return recovery_response(environ, self.journal, status, self._result)(environ, start_response)
        status_path = path == BASE + "/restore-host"
        result_path = path.startswith(BASE + "/results/") or path.startswith(BASE + "/jobs/")
        if not status_path and not (stopped and result_path):
            if stopped:
                return self._error("system_restore_stopped", "系统已为恢复停止普通服务，请核查原回执并重启宿主；不要重复执行。", 503)(environ, start_response)
            if self.application is not None:
                return self.application(environ, start_response)
            return self._error("maintenance_active", "维护记录未核实，普通服务未启动。", 503)(environ, start_response)
        if environ.get("REQUEST_METHOD") != "GET" or environ.get("QUERY_STRING"):
            return self._error("invalid_input", "维护核查只接受无查询参数的GET。", 400)(environ, start_response)
        try:
            data = {"kind": "restore_host", "host": status} if status_path else self._result(path, status)
            payload = {"ok": True, "schema_version": 1, "data": data, "warnings": [],
                       "meta": {"source": "production", "result_source": "external_maintenance_journal",
                                "request_ref": uuid.uuid4().hex, "time_basis": "factory_local"}}
            response = self._response(payload, 200)
        except WorkbenchCommandRejected as exc:
            response = self._error(exc.code, str(exc), exc.status)
        except Exception:
            response = self._error("maintenance_unconfirmed", "维护记录无法核实；系统保持停止，请保留现场。", 503)
        return response(environ, start_response)

    def _result(self, path, status):
        if path.startswith(BASE + "/results/"):
            key = path[len(BASE + "/results/"):]
            validate_request_key(key)
            row = self.journal.lookup(key)
        else:
            reference = path[len(BASE + "/jobs/"):]
            if not re.fullmatch(r"[a-f0-9]{32}", reference):
                raise WorkbenchCommandRejected("invalid_input", "维护记录引用无效。", 400)
            row = next((item for item in self.journal.records() if item["job_ref"] == reference), None)
        if row is None:
            return {"kind": "not_recorded", "host": status,
                    "message": "数据库外未查到此回执，不能认定未执行；当前数据库回执须在核实并重启后查询。"}
        return {"kind": "file_operation", "operation": self.journal.public(row, True), "host": status}

    @staticmethod
    def _response(payload, status):
        return Response(json.dumps(payload, ensure_ascii=True), status=status, content_type="application/json",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    def _error(self, code, message, status):
        return self._response({"ok": False, "committed": "unknown", "error": {
            "code": code, "message": message, "fields": [], "retryable": False,
            "request_ref": uuid.uuid4().hex}}, status)


def install_restore_status_transport(app, controller):
    app.wsgi_app = RestoreStatusTransport(app.wsgi_app, controller.journal, lambda: controller.status)

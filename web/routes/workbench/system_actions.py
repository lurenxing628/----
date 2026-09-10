"""Restore retains the legacy independent flow and requires an explicit host guard."""

from flask import current_app, g, jsonify

from core.infrastructure.backup import maintenance_window
from core.infrastructure.database import ensure_schema, get_connection
from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_system import RESTORE_DISABLED, object_fields
from core.services.system.backup_restore import audit_backup_operation, run_backup_restore
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.system_config import SystemConfigWorkspace
from core.services.workbench.system_files import SystemFileWorkspace

from .system_context import command_body, journal, query_payload, resolve_context, system_endpoint


@system_endpoint
def system_config_save():
    body = command_body()
    service = SystemConfigWorkspace(g.db, current_app.logger, current_app.config.get("BACKUP_KEEP_DAYS", 7))
    def guard():
        if current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"):
            journal().assert_ready()
        return service.check(resolve_context("config", body["write_token"]))
    with maintenance_window(current_app.config["DATABASE_PATH"], logger=current_app.logger, action="workbench_config"):
        if current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR") and journal().lookup(body["request_key"]):
            raise WorkbenchCommandRejected("request_key_conflict", "该请求标识已用于文件维护，请核对原结果。")
        return jsonify(service.save(request_key=body["request_key"], values=body["input"], guard=guard))


@system_endpoint
def system_result(request_key):
    validate_request_key(request_key)
    if current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"):
        row = journal().lookup(request_key)
        if row:
            return query_payload({"kind": "file_operation", "operation": journal().public(row, True)})
    result = WorkbenchCommandService(g.db, current_app.logger).lookup(request_key)
    if result:
        # This endpoint is system-only, even if a caller provides another domain's key.
        stored = WorkbenchCommandService(g.db, current_app.logger).repo.get(request_key)
        if stored is None or stored["action"] != "system.config.save":
            raise WorkbenchCommandRejected("entity_not_found", "没有找到本系统操作结果。", 404)
        return query_payload({"kind": "config", "command": result})
    return query_payload({"kind": "not_recorded", "message": "尚未查到持久结果；不能据此认定未执行，请继续核实原请求。"})


@system_endpoint
def system_job_result(job_ref):
    import re
    if not re.fullmatch(r"[a-f0-9]{32}", job_ref):
        raise WorkbenchCommandRejected("invalid_input", "维护记录引用无效。", 400)
    records = journal()
    for row in records.records():
        if row["job_ref"] == job_ref:
            return query_payload({"kind": "file_operation", "operation": records.public(row, True)})
    raise WorkbenchCommandRejected("entity_not_found", "未找到该维护记录。", 404)


def _file_service():
    return SystemFileWorkspace(database_path=current_app.config["DATABASE_PATH"], backup_dir=current_app.config["BACKUP_DIR"],
                               journal_dir=current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"), logger=current_app.logger)


def _restore_runner(manager, path):
    import os
    return run_backup_restore(filename=os.path.basename(path), backup_path=path,
                              database_path=current_app.config["DATABASE_PATH"], backup_dir=current_app.config["BACKUP_DIR"],
                              manager=manager, logger=current_app.logger, ensure_schema_func=ensure_schema)


def _audit_file(result):
    # Restore audit connections are owned and tracked by the restore host.
    conn = get_connection(current_app.config["DATABASE_PATH"])
    try:
        return audit_backup_operation(conn, current_app.logger, result)
    finally:
        conn.close()


@system_endpoint
def system_file_action(action):
    body = command_body()
    object_fields(body["input"], () if action == "create" else ("backup_ref",))
    if action == "restore":
        # No maintenance window may be held while the host waits for other
        # admitted requests: their existing maintenance/write work must finish.
        if journal().lookup(body["request_key"]) is None and WorkbenchCommandService(g.db, current_app.logger).lookup(body["request_key"]):
            raise WorkbenchCommandRejected("request_key_conflict", "该请求标识已用于数据库命令，请核对原结果。")
        return _execute_file_action(action, body)
    with maintenance_window(current_app.config["DATABASE_PATH"], logger=current_app.logger, action="workbench_file"):
        if WorkbenchCommandService(g.db, current_app.logger).lookup(body["request_key"]):
            raise WorkbenchCommandRejected("request_key_conflict", "该请求标识已用于数据库命令，请核对原结果。")
        return _execute_file_action(action, body)


def _execute_file_action(action, body):
    service = _file_service()
    def guard():
        if action == "create":
            resolve_context("create", body["write_token"])
            return None
        if resolve_context("file", body["write_token"]) != body["input"]["backup_ref"]:
            raise WorkbenchCommandRejected("stale_write", "所选备份和确认上下文不一致。")
        return resolve_context("backup", body["input"]["backup_ref"])
    if action == "restore":
        from web.bootstrap.workbench_system_restore import EXTENSION, GUARD, WorkbenchSystemRestoreHost
        host = current_app.extensions.get(EXTENSION)
        if not isinstance(host, WorkbenchSystemRestoreHost) or current_app.extensions.get(GUARD) is not host:
            raise WorkbenchCommandRejected("maintenance_unavailable", RESTORE_DISABLED, 503)
        result = host.execute(service, request_key=body["request_key"], intent=body["input"], guard=guard,
                              audit=host.audit_restore_result, restore_runner=_restore_runner)
        return query_payload({"kind": "file_operation", "operation": result, "host": host.status})
    result = service.execute(request_key=body["request_key"], action=action, intent=body["input"], guard=guard,
                             audit=_audit_file, restore_runner=None)
    return query_payload({"kind": "file_operation", "operation": result})

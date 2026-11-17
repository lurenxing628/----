"""Restore retains the legacy independent flow and requires an explicit host guard."""

from flask import current_app, g

from core.infrastructure.backup import maintenance_window
from core.infrastructure.database import ensure_schema
from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_system import RESTORE_DISABLED, is_maintenance_job_ref, system_object
from core.services.system.backup_restore import audit_backup_operation, run_backup_restore
from core.services.workbench import messages
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.system.config import SystemConfigWorkspace
from core.services.workbench.system.files import SystemFileWorkspace
from web.api_responses import json_response
from web.runtime_host import restore_host, wall_clock

from .read_context import current_snapshot_time
from .system_context import journal, query_payload, resolve_context, system_command_body, system_endpoint


@system_endpoint
def system_config_save():
    body = system_command_body()
    service = SystemConfigWorkspace(g.db, current_app.logger, current_app.config["BACKUP_KEEP_DAYS"])
    with maintenance_window(current_app.config["DATABASE_PATH"], logger=current_app.logger, action="workbench_config"):
        records = journal()
        entries = records.records()
        if any(row["request_key"] == body["request_key"] for row in entries):
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号已经用在文件维护上了，这次没有重复执行。请点「查询结果」核对上次的结果。")
        def guard():
            records.assert_ready(entries)
            return service.check(resolve_context("config", body["write_token"], database=records.scope_from_records(entries)))
        return json_response(service.save(request_key=body["request_key"], values=body["input"], guard=guard))


@system_endpoint
def system_result(request_key):
    validate_request_key(request_key)
    as_of = current_snapshot_time()
    records = journal()
    row = records.lookup(request_key)
    if row:
        return query_payload({"kind": "file_operation", "operation": records.public(row, True)}, as_of)
    commands = WorkbenchCommandService(g.db, current_app.logger)
    stored = commands.lookup(
        request_key,
        action="system.config.save",
        conflict_message="这个操作编号已经用在其他操作上了，这次没有重复执行。请核对上次的结果。",
    )
    if stored is not None:
        return query_payload({"kind": "config", "command": stored}, as_of)
    return query_payload({"kind": "not_recorded", "message": messages.pending("操作")}, as_of)


@system_endpoint
def system_job_result(job_ref):
    if not is_maintenance_job_ref(job_ref):
        raise WorkbenchCommandRejected("invalid_input", "这条维护记录的编号已失效，详情没有打开。请刷新页面后重新选择。", 400)
    as_of = current_snapshot_time()
    records = journal()
    row = records.lookup_job(job_ref)
    if row is not None:
        return query_payload({"kind": "file_operation", "operation": records.public(row, True)}, as_of)
    raise WorkbenchCommandRejected("entity_not_found", "找不到这条维护记录，详情没有打开。请刷新页面后重新选择。", 404)


def _file_service():
    return SystemFileWorkspace(database_path=current_app.config["DATABASE_PATH"], backup_dir=current_app.config["BACKUP_DIR"],
                               journal_dir=current_app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"], logger=current_app.logger,
                               clock=wall_clock(current_app))


def _restore_runner(manager, path):
    import os
    return run_backup_restore(filename=os.path.basename(path), backup_path=path,
                              database_path=current_app.config["DATABASE_PATH"],
                              manager=manager, logger=current_app.logger, ensure_schema_func=ensure_schema)


def _audit_file(result):
    # Restore audit connections are owned and tracked by the restore host.
    return audit_backup_operation(g.db, current_app.logger, result)


@system_endpoint
def system_file_action(action):
    body = system_command_body()
    system_object(body["input"], () if action == "create" else ("backup_ref",))
    commands = WorkbenchCommandService(g.db, current_app.logger)
    service = _file_service()
    if action == "restore":
        # No maintenance window may be held while the host waits for other
        # admitted requests: their existing maintenance/write work must finish.
        return _execute_file_action(action, body, service, commands)
    with maintenance_window(current_app.config["DATABASE_PATH"], logger=current_app.logger, action="workbench_file"):
        if commands.has_receipt(body["request_key"]):
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号已经用在数据库维护上了，这次没有重复执行。请点「查询结果」核对上次的结果。")
        return _execute_file_action(action, body, service, commands)


def _execute_file_action(action, body, service, commands):
    def guard():
        if action == "restore" and commands.has_receipt(body["request_key"]):
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号已经用在数据库维护上了，这次没有重复执行。请点「查询结果」核对上次的结果。")
        database = service.journal.database_scope
        if action == "create":
            resolve_context("create", body["write_token"], database=database)
            return None
        if resolve_context("file", body["write_token"], database=database) != body["input"]["backup_ref"]:
            raise WorkbenchCommandRejected("stale_write", "本页数据已过期，所选备份和确认内容对不上，备份没有改动。请刷新页面后重新选择备份。")
        return resolve_context("backup", body["input"]["backup_ref"], database=database)
    # 回执描述的是维护操作做完后的状态，时刻在命令执行完、组装响应时取。
    host = restore_host(current_app)
    if action == "restore":
        if host is None:
            raise WorkbenchCommandRejected("maintenance_unavailable", RESTORE_DISABLED, 503)
        result = host.execute(service, request_key=body["request_key"], intent=body["input"], guard=guard,
                              audit=host.audit_restore_result, restore_runner=_restore_runner)
        return query_payload({"kind": "file_operation", "operation": result, "host": host.status}, current_snapshot_time())
    values = {"request_key": body["request_key"], "action": action, "intent": body["input"], "guard": guard,
              "audit": _audit_file}
    result = host.execute_file(service, **values) if host is not None else service.execute(**values)
    return query_payload({"kind": "file_operation", "operation": result}, current_snapshot_time())

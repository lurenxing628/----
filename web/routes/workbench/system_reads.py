"""System maintenance collections with explicit log-window and snapshot semantics."""

from flask import current_app, g, request

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_system import RESTORE_DISABLED, filter_records, query_input
from core.services.workbench.system_config import SystemConfigWorkspace
from core.services.workbench.system_maintenance_records import maintenance_records
from core.services.workbench.system_reads import log_records
from core.services.workbench.system_redaction import public_system_text

from .api_responses import query_success
from .read_context import bind_read_snapshot
from .system_context import issue_context, journal, system_endpoint


def restore_available():
    return callable(current_app.extensions.get("workbench_system_restore_guard"))


def file_capabilities():
    try:
        journal().assert_ready()
        reason = ""
    except Exception as exc:
        reason = str(exc) if isinstance(exc, WorkbenchCommandRejected) else "维护记录读不出来，数据没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。"
    return {"create": not bool(reason), "delete": not bool(reason),
            "restore": not bool(reason) and restore_available(), "blocked_reason": reason,
            "restore_reason": reason or ("" if restore_available() else RESTORE_DISABLED)}


def collection(kind):
    if any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "筛选条件有重复项，当前筛选没有变化。请刷新页面后重新选择。", 400)
    query = query_input(request.args.to_dict(), kind)
    if kind == "backups":
        event_journal = journal() if current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR") else None
        rows, sources = maintenance_records(g.db, current_app.config["BACKUP_DIR"], event_journal)
    else:
        rows, sources = log_records(g.db, current_app.config["LOG_DIR"], current_app.logger)
    filtered = filter_records(rows, query)
    scope = {key: value for key, value in query.items() if key not in ("page", "page_size")}
    snapshot = bind_read_snapshot({"kind": "system." + kind, **scope}, input_fingerprint({"rows": filtered, "sources": sources}), request.args.get("snapshot_ref"))
    return filtered, sources, query, snapshot


@system_endpoint
def system_collection(kind):
    with TransactionManager(g.db).transaction():
        rows, sources, query, snapshot = collection(kind)
    count, size, page = len(rows), query["page_size"], query["page"]
    pages = max(1, (count + size - 1) // size)
    if page > pages:
        raise WorkbenchCommandRejected("invalid_input", "翻页位置已失效，请回到第 1 页重新查询。", 400)
    public = []
    for row in rows[(page - 1) * size:page * size]:
        item = {key: value for key, value in row.items() if not key.startswith("_")}
        if kind == "backups" and row["record_kind"] == "backup_file":
            reference = issue_context("backup", {"filename": row["filename"], "signature": row["_signature"]})
            item["backup_ref"] = reference
            item["write_context"] = {"write_token": issue_context("file", reference)}
        public.append(item)
    data = {"rows": public, "page": {"number": page, "size": size, "total": count, "pages": pages},
            "sources": sources, "scope": "backup-files-and-maintenance-events" if kind == "backups" else "bounded-log-windows"}
    if kind == "backups":
        data.update({"capabilities": file_capabilities(), "create_context": {"write_token": issue_context("create", {})}})
    return query_success(data, snapshot)


@system_endpoint
def system_config_read():
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "读取设置不需要筛选条件。请刷新页面后重试。", 400)
    with TransactionManager(g.db).transaction():
        data, fingerprint = SystemConfigWorkspace(g.db, current_app.logger, current_app.config.get("BACKUP_KEEP_DAYS", 7)).snapshot()
    data["stored_values"] = {key: public_system_text(value, 256) if value is not None else None for key, value in data["stored_values"].items()}
    data["write_context"] = {"write_token": issue_context("config", fingerprint)}
    snapshot = bind_read_snapshot({"kind": "system.config"}, fingerprint)
    return query_success(data, snapshot)

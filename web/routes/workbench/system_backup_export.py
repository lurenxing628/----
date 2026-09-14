"""Read an immutable response from a current, server-issued backup selection."""

import os
from urllib.parse import quote

from flask import Response, current_app, request

from core.infrastructure.safe_files import read_fixed_bytes
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from core.services.workbench.system_reads import backup_signature

from .system_context import resolve_context, system_endpoint
from .system_reads import collection


def _selected_filename(selected, rows):
    name = selected["filename"]
    if (not isinstance(name, str) or os.path.basename(name) != name or "\\" in name
            or not name.startswith("aps_backup_") or not name.endswith(".db")):
        raise WorkbenchCommandRejected("invalid_input", "这个备份文件的编号已失效，没有开始下载。请刷新页面后重新选择备份。", 400)
    row = next((row for row in rows if row["record_kind"] == "backup_file" and row["filename"] == name), None)
    if row is None:
        raise WorkbenchCommandRejected("entity_not_found", "所选备份不在当前清单里，没有开始下载。请刷新页面后重新选择备份。", 404)
    if row["_signature"] != selected["signature"]:
        raise WorkbenchCommandRejected("snapshot_stale", "备份文件有变化，没有开始下载。请刷新页面后重新点「下载备份」。")
    return name


def _selected_bytes(selected, rows):
    name = _selected_filename(selected, rows)
    path = os.path.join(current_app.config["BACKUP_DIR"], name)
    try:
        before = backup_signature(path)
        if before != selected["signature"]:
            raise WorkbenchCommandRejected("snapshot_stale", "备份文件有变化，没有开始下载。请刷新页面后重新点「下载备份」。")
        data = read_fixed_bytes(path)
        after = backup_signature(path)
    except OSError as exc:
        raise WorkbenchCommandRejected("entity_not_found", "所选备份已经不在或读不出来，没有开始下载。请刷新页面后重新选择备份。", 404) from exc
    if after != before or len(data) != before["size"]:
        raise WorkbenchCommandRejected("snapshot_stale", "下载过程中备份文件发生变化，没有给出文件。请刷新页面后重新点「下载备份」。")
    if not data.startswith(b"SQLite format 3\x00"):
        raise WorkbenchCommandRejected("backup_format_invalid", "所选文件不是本软件能识别的备份，没有给出文件。请刷新页面后重新选择备份。", 422)
    return data, name


@system_endpoint
def system_backup_export(backup_ref):
    if not request.args.get("snapshot_ref"):
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
    selected = resolve_context("backup", backup_ref)
    rows, _sources, _query, _snapshot = collection("backups")
    data, name = _selected_bytes(selected, rows)
    response = Response(data, content_type="application/vnd.sqlite3")
    response.headers["Content-Disposition"] = "attachment; filename=aps-backup.db; filename*=UTF-8''" + quote(name, safe="")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-APS-Backup-Ref"] = backup_ref
    return response

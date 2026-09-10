"""Read an immutable response from a current, server-issued backup selection."""

import os
from urllib.parse import quote

from flask import Response, current_app, request

from core.infrastructure.safe_files import read_fixed_bytes
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.system_reads import backup_signature

from .system_context import resolve_context, system_endpoint
from .system_reads import collection


def _selected_filename(selected, rows):
    name = selected["filename"]
    if (not isinstance(name, str) or os.path.basename(name) != name or "\\" in name
            or not name.startswith("aps_backup_") or not name.endswith(".db")):
        raise WorkbenchCommandRejected("invalid_input", "备份引用无效。", 400)
    row = next((row for row in rows if row["record_kind"] == "backup_file" and row["filename"] == name), None)
    if row is None:
        raise WorkbenchCommandRejected("entity_not_found", "所选备份不在当前已读取范围，请刷新后重新选择。", 404)
    if row["_signature"] != selected["signature"]:
        raise WorkbenchCommandRejected("snapshot_stale", "备份文件已变化，请重新读取清单后下载。")
    return name


def _selected_bytes(selected, rows):
    name = _selected_filename(selected, rows)
    path = os.path.join(current_app.config["BACKUP_DIR"], name)
    try:
        before = backup_signature(path)
        if before != selected["signature"]:
            raise WorkbenchCommandRejected("snapshot_stale", "备份文件已变化，请重新读取清单后下载。")
        data = read_fixed_bytes(path)
        after = backup_signature(path)
    except OSError as exc:
        raise WorkbenchCommandRejected("entity_not_found", "所选备份已不存在或无法读取，请刷新。", 404) from exc
    if after != before or len(data) != before["size"]:
        raise WorkbenchCommandRejected("snapshot_stale", "备份在读取期间发生变化，未提供下载文件。")
    if not data.startswith(b"SQLite format 3\x00"):
        raise WorkbenchCommandRejected("backup_format_invalid", "所选文件不是可识别的 SQLite 备份，未提供下载。", 422)
    return data, name


@system_endpoint
def system_backup_export(backup_ref):
    if not request.args.get("snapshot_ref"):
        raise WorkbenchCommandRejected("snapshot_stale", "请先读取备份清单再下载。")
    selected = resolve_context("backup", backup_ref)
    rows, _sources, _query, _snapshot = collection("backups")
    data, name = _selected_bytes(selected, rows)
    response = Response(data, content_type="application/vnd.sqlite3")
    response.headers["Content-Disposition"] = "attachment; filename=aps-backup.db; filename*=UTF-8''" + quote(name, safe="")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-APS-Backup-Ref"] = backup_ref
    return response

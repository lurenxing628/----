"""Downloads are the same filtered snapshot, never raw logs or user-supplied paths."""

from urllib.parse import quote

from flask import Response

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from core.services.workbench.system_exports import diagnostic_zip, logs_csv

from .system_context import system_endpoint
from .system_reads import collection


@system_endpoint
def system_log_export(format_name):
    from flask import request
    if not request.args.get("snapshot_ref"):
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
    rows, sources, query, snapshot = collection("logs")
    if format_name == "csv":
        data, mime, name, ascii_name = logs_csv(rows), "text/csv; charset=utf-8", "系统日志片段.csv", "aps-system-log.csv"
    else:
        data = diagnostic_zip(rows, sources, snapshot["as_of"])
        mime, name, ascii_name = "application/zip", "系统诊断包-已脱敏.zip", "aps-system-diagnostic.zip"
    response = Response(data, content_type=mime)
    response.headers["Content-Disposition"] = ("attachment; filename=" + ascii_name
                                               + "; filename*=UTF-8''" + quote(name, safe=""))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

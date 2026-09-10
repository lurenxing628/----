"""Downloads are the same filtered snapshot, never raw logs or user-supplied paths."""

from flask import Response

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.system_exports import diagnostic_zip, logs_csv

from .system_context import system_endpoint
from .system_reads import collection


@system_endpoint
def system_log_export(format_name):
    from flask import request
    if not request.args.get("snapshot_ref"):
        raise WorkbenchCommandRejected("snapshot_stale", "请先读取日志范围再导出。")
    rows, sources, query, snapshot = collection("logs")
    if format_name == "csv":
        data, mime, name = logs_csv(rows), "text/csv; charset=utf-8", "aps-system-log-window.csv"
    else:
        data = diagnostic_zip(rows, sources, snapshot["as_of"])
        mime, name = "application/zip", "aps-system-diagnostic-redacted.zip"
    response = Response(data, content_type=mime)
    response.headers["Content-Disposition"] = 'attachment; filename="' + name + '"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

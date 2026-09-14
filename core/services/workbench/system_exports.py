"""Sanitized bounded diagnostic ZIP and exact queried-window CSV, without raw files."""

import csv
import io
import json
import zipfile

from core.models.workbench_system import (
    LOG_RECORD_STATUS_LABELS,
    LOG_RECORD_TYPE_LABELS,
    LOG_SOURCE_LABELS,
    log_level_label,
)


def logs_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["来源", "时间", "类型", "级别", "记录状态", "摘要", "详情"])
    for row in rows:
        # 闭合枚举直接下标：取不到就报错，不静默把英文码写进用户的文件。
        cells = [LOG_SOURCE_LABELS[row["file"]], row["time"], LOG_RECORD_TYPE_LABELS[row["type"]], log_level_label(row["level"]),
                 LOG_RECORD_STATUS_LABELS[row["status"]], row["summary"], row["body"]]
        writer.writerow(["'" + str(value) if str(value or "").lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")) else value for value in cells])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def diagnostic_zip(rows, sources, as_of):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("logs.csv", logs_csv(rows))
        archive.writestr("diagnostic_info.json", json.dumps({
            "scope": "sanitized-log-windows", "as_of": as_of, "time_basis": "factory_local",
            "sources": sources, "rows": len(rows), "redacted": True,
            "excludes": ["database", "raw-log-files", "credentials", "absolute-paths", "browser-storage"],
            "note": "每个运行日志文件取最近 200 条，操作日志取最近 500 条；不是全部历史日志。",
        }, ensure_ascii=False, indent=2))
        for source in sources:
            if source["state"] in ("error", "missing"):
                archive.writestr(source["source"] + "_READ_FAILED.txt", source.get("message", "没有读到这个来源的日志文件，包里不放这部分内容。"))
    return stream.getvalue()

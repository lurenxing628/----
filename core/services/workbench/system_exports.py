"""Sanitized bounded diagnostic ZIP and exact queried-window CSV, without raw files."""

import csv
import io
import json
import zipfile


def logs_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["来源", "工厂本地时间", "类型", "级别", "记录状态", "摘要", "详情"])
    for row in rows:
        cells = [row["file"], row["time"], row["type"], row["level"], row["status"], row["summary"], row["body"]]
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
            "note": "每个运行文件最近200条，操作日志最近500条；不是全历史日志包。",
        }, ensure_ascii=False, indent=2))
        for source in sources:
            if source["state"] in ("error", "missing"):
                archive.writestr(source["source"] + "_READ_FAILED.txt", source.get("message", "日志文件不存在，未提供此来源内容。"))
    return stream.getvalue()

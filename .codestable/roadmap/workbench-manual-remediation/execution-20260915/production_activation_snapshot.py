"""Read-only, type-aware main database evidence for the final activation."""
import collections
import datetime
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def typed_value(kind, value):
    if isinstance(value, bytes):
        value = value.hex()
    elif isinstance(value, float):
        value = value.hex()
    return [kind, value]


def main():
    expected_pid = int(sys.argv[1])
    destination = Path(sys.argv[2]).resolve()
    root = Path.cwd().resolve()
    runtime = json.loads((root / "logs/aps_runtime.json").read_text())
    assert runtime["pid"] == expected_pid
    assert runtime["port"] == 5000 and runtime["host"] == "127.0.0.1"
    assert Path(runtime["runtime_dir"]).resolve() == root
    listener = subprocess.check_output(
        ["lsof", "-nP", "-t", "-iTCP:5000", "-sTCP:LISTEN"], text=True).strip()
    assert listener == str(expected_pid), listener
    command = subprocess.check_output(
        ["ps", "-p", str(expected_pid), "-o", "command="], text=True).strip()
    assert "Python -B app.py" in command, command
    cwd = subprocess.check_output(
        ["lsof", "-a", "-p", str(expected_pid), "-d", "cwd", "-Fn"], text=True)
    assert "n" + str(root) in cwd.splitlines(), cwd
    database = Path(runtime["db_path"]).resolve(strict=True)
    assert database == Path((root / "logs/aps_db_path.txt").read_text().strip()).resolve()
    result = {
        "captured_at": datetime.datetime.now().astimezone().isoformat(),
        "runtime": {key: runtime[key] for key in (
            "pid", "port", "host", "db_path", "runtime_dir", "exe_path", "started_at")},
        "process_command": command,
        "database": str(database),
        "connection": "SQLite URI mode=ro and PRAGMA query_only=ON; read transaction",
        "build_id": json.loads((root / "static/workbench/asset-manifest.json").read_text())["build_id"],
        "tables": {},
    }
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    for name, sql in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        columns = [row[1] for row in connection.execute("PRAGMA table_info(" + quote(name) + ")")]
        expressions = []
        for column in columns:
            expressions.extend(["typeof(" + quote(column) + ")", quote(column)])
        row_hashes = collections.Counter()
        for row in connection.execute("SELECT " + ",".join(expressions) + " FROM " + quote(name)):
            row_hashes[digest([typed_value(row[i], row[i + 1]) for i in range(0, len(row), 2)])] += 1
        result["tables"][name] = {
            "columns": columns,
            "rows": sum(row_hashes.values()),
            "ddl_sha256": digest(sql),
            "typed_rows_sha256": digest(sorted(row_hashes.items())),
            "typed_row_hash_counts": dict(sorted(row_hashes.items())),
        }
    result["sqlite_master_sha256"] = digest(connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall())
    result["schema_rows"] = connection.execute("SELECT * FROM SchemaVersion").fetchall()
    result["integrity_check"] = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    result["foreign_key_check"] = connection.execute("PRAGMA foreign_key_check").fetchall()
    result["operation_logs_columns"] = [row[1] for row in connection.execute("PRAGMA table_info(OperationLogs)")]
    result["operation_logs_last_three"] = connection.execute("SELECT * FROM OperationLogs ORDER BY rowid DESC LIMIT 3").fetchall()
    connection.close()
    result["retained_backups"] = []
    for name in (
            "aps_backup_20260915_210510_manual_d73e63ee6bab.db",
            "aps_backup_20260915_210639_before_migrate_v31_to_v32.db"):
        path = root / "backups" / name
        result["retained_backups"].append({
            "path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"snapshot": str(destination), "pid": expected_pid,
                      "table_count": len(result["tables"]), "integrity": result["integrity_check"],
                      "foreign_key_failures": len(result["foreign_key_check"]),
                      "build_id": result["build_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

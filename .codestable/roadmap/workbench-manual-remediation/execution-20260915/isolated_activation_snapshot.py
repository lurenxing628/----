"""Read-only evidence for the retained manual acceptance instance on port 5005."""
import collections
import datetime
import json
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path

from production_activation_snapshot import digest, quote, typed_value


def main():
    evidence = Path(__file__).resolve().parent
    original = next(row for row in json.loads((evidence / "isolated-env-before-closeout.json").read_text())
                    if row["port"] == 5005)
    root = Path(original["root"])
    runtime = json.loads((root / "logs/aps_runtime.json").read_text())
    pid = int(sys.argv[1])
    assert runtime["pid"] == pid and runtime["port"] == 5005
    assert runtime["db_path"] == original["database"]
    assert Path(runtime["runtime_dir"]).resolve() == root
    assert subprocess.check_output(["lsof", "-nP", "-t", "-iTCP:5005", "-sTCP:LISTEN"], text=True).strip() == str(pid)
    command = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True).strip()
    assert Path(shlex.split(command)[-1]).resolve() == Path(original["launcher"])
    result = {"captured_at": datetime.datetime.now().astimezone().isoformat(),
              "database": runtime["db_path"], "pid": pid, "port": 5005,
              "started_at": runtime["started_at"], "command": command,
              "query_mode": "SQLite mode=ro, query_only=ON, read transaction", "tables": {}}
    connection = sqlite3.connect(Path(runtime["db_path"]).as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    for name, sql in connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        columns = [row[1] for row in connection.execute("PRAGMA table_info(" + quote(name) + ")")]
        expressions = []
        for column in columns:
            expressions.extend(["typeof(" + quote(column) + ")", quote(column)])
        hashes = collections.Counter()
        for row in connection.execute("SELECT " + ",".join(expressions) + " FROM " + quote(name)):
            hashes[digest([typed_value(row[i], row[i + 1]) for i in range(0, len(row), 2)])] += 1
        result["tables"][name] = {"columns": columns, "rows": sum(hashes.values()),
                                  "ddl_sha256": digest(sql), "typed_rows_sha256": digest(sorted(hashes.items())),
                                  "typed_row_hash_counts": dict(sorted(hashes.items()))}
    result["sqlite_master_sha256"] = digest(connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall())
    result["schema_rows"] = connection.execute("SELECT * FROM SchemaVersion").fetchall()
    result["integrity_check"] = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    result["foreign_key_check"] = connection.execute("PRAGMA foreign_key_check").fetchall()
    result["schedule_version_counts"] = connection.execute("SELECT version,count(*) FROM Schedule GROUP BY version ORDER BY version").fetchall()
    result["calibration_adoptions"] = connection.execute(
        "SELECT adoption_ref,template_revision_before,template_revision_after,old_unit_hours,new_unit_hours,sample_count FROM WorkbenchCalibrationAdoptions").fetchall()
    result["sqlite_sequence"] = connection.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall()
    result["operation_logs_last_three"] = connection.execute("SELECT * FROM OperationLogs ORDER BY rowid DESC LIMIT 3").fetchall()
    connection.close()
    destination = Path(sys.argv[2])
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"snapshot": str(destination), "pid": pid, "tables": len(result["tables"]),
                      "batches": result["tables"]["Batches"]["rows"],
                      "operations": result["tables"]["BatchOperations"]["rows"],
                      "reports": result["tables"]["WorkbenchProductionReports"]["rows"],
                      "schedule_version_counts": result["schedule_version_counts"],
                      "calibration_adoptions": result["calibration_adoptions"],
                      "integrity": result["integrity_check"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

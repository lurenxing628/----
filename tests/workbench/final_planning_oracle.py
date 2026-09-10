"""D independent SQLite/read witnesses for actual full-entry browser requests."""

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from tests.workbench.piece_main_oracle import APPEND_TABLES, CLOCK_TABLES, encoded


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def startup_retention(before, after, check):
    for table in before:
        if table not in ("OperationLogs", "sqlite_sequence"):
            check(before[table] == after[table], "Restart changed business table: " + table)
    logs, restarted = before["OperationLogs"], after["OperationLogs"]
    check(restarted[:len(logs)] == logs, "Restart modified an original audit log")
    added = restarted[len(logs):]
    check(len(added) == 1, "Restart must append exactly one plugin startup audit")
    if len(added) == 1:
        row = added[0]
        check(all(row[key] == value for key, value in {
            "module": "plugins", "action": "load", "target_type": "runtime", "target_id": "plugins",
            "log_level": "INFO", "error_code": None, "error_message": None, "operator": None}.items()),
            "Unexpected startup audit content")
        original = next(item for item in logs if item["module"] == "plugins" and item["action"] == "load")
        earlier, later = json.loads(original["detail"]), json.loads(row["detail"])
        check(datetime.fromisoformat(later["loaded_at"]) >= datetime.fromisoformat(earlier["loaded_at"]), "Plugin load clock regressed")
        check({key: value for key, value in earlier.items() if key != "loaded_at"} ==
              {key: value for key, value in later.items() if key != "loaded_at"}, "Plugin startup changed loaded configuration")
    expected = [dict(row, seq=row["seq"] + 1) if row["name"] == "OperationLogs" else row for row in before["sqlite_sequence"]]
    check(expected == after["sqlite_sequence"], "Restart changed an unrelated sequence")


def candidate_download(browser, check):
    evidence = browser.get("candidate_download")
    if evidence is None:
        return
    with Path(evidence["path"]).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    tasks = evidence["tasks"]
    check(len(rows) == len(tasks), "Candidate CSV did not preserve complete row count")
    for column, field in (("行引用", "row_ref"), ("工序引用", "operation_ref"), ("安排开始", "start"), ("安排结束", "end")):
        check([row[column] for row in rows] == ["'" + task[field] for task in tasks], "Candidate CSV drift: " + column)
    check(all(row["候选引用"] == "'" + evidence["candidate_ref"] and row["运行引用"] == "'" + evidence["run_ref"] for row in rows),
          "Candidate CSV changed source identity")


def verify(root, first, second):
    first_dir = root / "sessions" / first["ready"]["session"]
    second_dir = root / "sessions" / second["ready"]["session"]
    before, after = read(first_dir / "business-before.json"), read(first_dir / "business-after.json")
    browser = read(root / "final_planning_actions.json")
    result = {"root": str(root), "errors": [], "tables": len(before),
              "actions": len(browser["actions"]), "changed_tables": [],
              "source_build": read(root / "piece_main_build.json")}

    def check(ok, message):
        if not ok:
            result["errors"].append(message)

    check(set(before) == set(after), "Schema tables changed")
    for table, rows in before.items():
        now = after[table]
        if rows == now:
            continue
        result["changed_tables"].append(table)
        check(table in APPEND_TABLES | CLOCK_TABLES, "Unexpected mutation: " + table)
        if table not in CLOCK_TABLES:
            check(not (Counter(map(encoded, rows)) - Counter(map(encoded, now))), "Original row lost: " + table)
        elif table == "WorkbenchPlanIdentityClock":
            check(now[0]["revision"] >= rows[0]["revision"], "Identity clock regressed")
        else:
            clocks = {row["name"]: row["seq"] for row in now}
            check(all(clocks.get(row["name"], -1) >= row["seq"] for row in rows), "Sequence regressed")
    check(read(second_dir / "business-before.json") == read(second_dir / "business-after.json"),
          "New-process browser reads mutated the database")
    startup_retention(after, read(second_dir / "business-before.json"), check)
    result["new_process_read_only"] = True
    witness = [json.loads(line) for line in (root / "final_planning_official.jsonl").read_text(encoding="utf-8").splitlines()]
    initial = {name: before[name] for name in ("Schedule", "ScheduleHistory")}
    current = initial
    adopted = 0
    for row in witness:
        if row["method"] == "POST" and row["path"].endswith("/adopt") and row["status"] == 200:
            adopted += 1
            check(len(row["official"]["ScheduleHistory"]) == len(current["ScheduleHistory"]) + 1,
                  "Adoption did not create exactly one official version")
            current = row["official"]
        else:
            check(row["official"] == current, "Non-adoption request changed official plan: " + row["path"])
    check(adopted == 2, "Expected candidate adoption and scenario adoption only")
    check(len(after["WorkbenchRunJobs"]) == 1 and after["WorkbenchRunJobs"][0]["state"] == "complete", "Real worker did not complete")
    check(len(after["WorkbenchRunCandidates"]) == 4, "Expected four persisted candidates")
    expected = read(root / "run-seed.json")
    expected_ops = {row["operation_id"]: row for row in expected["operations"]}
    datasets = [("candidate:" + row["candidate_ref"], json.loads(row["artifact_json"])["validated_payload"]["schedule_rows"])
                for row in after["WorkbenchRunCandidates"]]
    datasets += [("official:" + str(version), [row for row in after["Schedule"] if row["version"] == version]) for version in (5, 6)]
    for label, rows in datasets:
        by_id = {row["op_id"]: row for row in rows}
        check(len(rows) == len(expected_ops) and set(by_id) == set(expected_ops), label + " incomplete scope")
        for op_id, row in by_id.items():
            duration = (datetime.fromisoformat(row["end_time"]) - datetime.fromisoformat(row["start_time"])).total_seconds()
            check(duration == expected_ops[op_id]["total_hours"] * 3600, label + " duration mismatch")
        for old in before["Schedule"]:
            if old["version"] == 4:
                now = by_id[old["op_id"]]
                for field in ("start_time", "end_time", "machine_id", "operator_id"):
                    check(now[field].replace("T", " ") == old[field].replace("T", " "), label + " protected seed changed")
    observed = Counter((row["method"], urlsplit(row["url"]).path,
                        (row.get("input") or {}).get("request_key")) for row in browser["requests"] if row["method"] == "POST")
    journal = [json.loads(line) for line in (first_dir / "server-requests.jsonl").read_text(encoding="utf-8").splitlines()]
    actual = Counter((row["method"], row["path"], row.get("request_key")) for row in journal if row["method"] == "POST")
    check(actual == observed, "Server POSTs do not equal browser-triggered POSTs")
    candidate_download(browser, check)
    conn = sqlite3.connect((root / "db/aps-live.db").as_uri() + "?mode=ro", uri=True)
    try:
        check(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failed")
        check(not conn.execute("PRAGMA foreign_key_check").fetchall(), "Foreign keys failed")
    finally:
        conn.close()
    result["evidence_hashes"] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (root / "final_planning_actions.json", root / "final_planning_restart.json", root / "piece_main_build.json")}
    result["official_versions"] = [5, 6]
    return result

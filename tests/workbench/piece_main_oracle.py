"""Read-only 77-table retention and business proofs for the browser's actual writes."""

import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

APPEND_TABLES = {
    "OperationLogs", "Schedule", "ScheduleHistory", "ScheduleVersionSeq",
    "WorkbenchCommandReceipts", "WorkbenchDashboardItems", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs",
    "WorkbenchRunJobs", "WorkbenchRunReceipts", "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks",
    "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialChanges", "WorkbenchTrialScenarios",
    "WorkbenchTrialScenarioRows",
}
CLOCK_TABLES = {"sqlite_sequence", "WorkbenchPlanIdentityClock"}
WRITE_PATH = re.compile(r"^/api/workbench/v1/(entities/batch/query|scheduling/(preflight|runs(?:/preview)?|"
                        r"candidates/[^/]+/adopt(?:-preview)?)|trial/(drafts(?:/preview|/[^/]+/(?:change|save))?|"
                        r"scenarios/[^/]+/adopt(?:-preview)?))$")


def encoded(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def verify(root):
    root = Path(root)
    before, after, browser = read(root, "business-before.json"), read(root, "business-after.json"), read(root, "piece_main_browser.json")
    result = {"table_count": len(before), "changed_tables": [], "retained_nonempty_tables": [], "errors": []}

    def check(condition, message):
        if not condition:
            result["errors"].append(message)

    check(len(before) == 77 and set(before) == set(after), "Expected exactly the same 77 schema tables")
    for name, rows in before.items():
        now = after[name]
        if rows == now:
            if rows:
                result["retained_nonempty_tables"].append(name)
            continue
        result["changed_tables"].append({"table": name, "before": len(rows), "after": len(now)})
        check(name in APPEND_TABLES | CLOCK_TABLES, "Unexpected table changed: " + name)
        if name not in CLOCK_TABLES:
            check(not (Counter(map(encoded, rows)) - Counter(map(encoded, now))), "Old rows modified/deleted: " + name)
        elif name == "WorkbenchPlanIdentityClock":
            check(len(rows) == len(now) == 1 and now[0]["singleton"] == rows[0]["singleton"]
                  and now[0]["revision"] >= rows[0]["revision"], "Identity clock must only advance")
        else:
            clocks = {row["name"]: row["seq"] for row in now}
            check(all(row["name"] in clocks and clocks[row["name"]] >= row["seq"] for row in rows), "SQLite sequences must not decrease")
            changed = {row["name"] for row in now if row not in rows}
            check(changed <= APPEND_TABLES, "Unrelated SQLite sequence changed")

    for table in ("Batches", "BatchOperations", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions",
                  "ScheduleCandidate", "ScheduleCandidateRows", "ScheduleCandidateSelection",
                  "ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow"):
        check(bool(before[table]), "Retention witness must not be empty: " + table)
        check(before[table] == after[table], "Original source changed: " + table)
    check(before["OperationExecutionEvents"] == after["OperationExecutionEvents"], "Legacy execution changed")
    check(bool(before["WorkbenchCommandReceipts"]), "Original receipt witness is missing")
    keys = {row["input"]["request_key"] for row in browser["requests"] if isinstance(row.get("input"), dict) and row["input"].get("request_key")}
    from urllib.parse import urlsplit

    requests = [row for row in browser["requests"] if row["method"] != "GET"]
    check(all(row["method"] == "POST" and WRITE_PATH.fullmatch(urlsplit(row["url"]).path) for row in requests),
          "Browser called an out-of-scope mutation route")
    journal = [json.loads(line) for line in Path(read(root, "server-ready.json")["journal"]).read_text(encoding="utf-8").splitlines()]
    actual = Counter((row["method"], row["path"], row.get("request_key")) for row in journal if row["method"] == "POST")
    observed = Counter((row["method"], urlsplit(row["url"]).path, (row.get("input") or {}).get("request_key")) for row in requests)
    check(actual == observed, "Every server POST must correspond to an observed browser action")
    original_keys = {row["request_key"] for row in before["WorkbenchCommandReceipts"]}
    receipts = [row for row in after["WorkbenchCommandReceipts"] if row["request_key"] not in original_keys]
    check(all(row["request_key"] in keys for row in receipts), "Non-fixture command lacks an actual browser request")
    check(len(after["WorkbenchRunJobs"]) == 1 and after["WorkbenchRunJobs"][0]["state"] == "complete", "Expected one real completed worker run")
    if after["WorkbenchRunJobs"]:
        check(after["WorkbenchRunJobs"][0]["request_key"] in keys, "Worker run was not browser-created")
    result["browser_command_keys"] = sorted(keys)
    result["receipt_count"] = len(receipts)

    expected = read(root, "run-seed.json")
    original_version = expected["official_version"]
    outcomes = [json.loads(row["outcome_json"]) for row in receipts]
    adopted = [row["data"]["official_plan"] for row in outcomes if isinstance(row.get("data"), dict) and "official_plan" in row["data"]]
    result["adopted_versions"] = sorted(row["version"] for row in adopted)
    check(len(after["ScheduleHistory"]) == len(before["ScheduleHistory"]) + len(adopted), "Official versions differ from actual adoption receipts")
    schedule = after["Schedule"]
    op_index = {row["id"]: row for row in before["BatchOperations"]}
    expected_ops = {row["operation_id"]: row for row in expected["operations"]}
    datasets = [("candidate:" + row["candidate_ref"], json.loads(row["artifact_json"])["validated_payload"]["schedule_rows"])
                for row in after["WorkbenchRunCandidates"]]
    datasets += [("official:" + str(plan["version"]), [row for row in schedule if row["version"] == plan["version"]]) for plan in adopted]
    for label, rows in datasets:
        by_id = {row["op_id"]: row for row in rows}
        check(set(by_id) == set(expected_ops) and len(rows) == len(expected_ops), label + ": incomplete/duplicate identity")
        for op_id, row in by_id.items():
            start, end = (datetime.fromisoformat(row[key]) for key in ("start_time", "end_time"))
            check((end - start).total_seconds() == expected_ops[op_id]["total_hours"] * 3600, label + ": wrong work duration " + str(op_id))
            work = op_index[op_id]
            if work["batch_id"] != "B1":
                continue
            predecessors = [other for other in op_index.values() if other["batch_id"] == "B1" and (
                work["seq"] == 20 and other["seq"] == 10 or
                work["seq"] == 30 and other["seq"] == 20 and other["piece_id"] == work["piece_id"] or
                work["seq"] == 40 and other["seq"] == 30)]
            for previous in predecessors:
                check(datetime.fromisoformat(by_id[previous["id"]]["end_time"]) <= start, label + ": wrong fan-out/join dependency")
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                collision = max(datetime.fromisoformat(left["start_time"]), datetime.fromisoformat(right["start_time"])) < min(
                    datetime.fromisoformat(left["end_time"]), datetime.fromisoformat(right["end_time"]))
                shared = left["machine_id"] == right["machine_id"] or left["operator_id"] == right["operator_id"]
                check(not (collision and shared), label + ": machine/operator double booking")
        old = next(row for row in before["Schedule"] if row["version"] == original_version)
        check(all(by_id[old["op_id"]][field].replace("T", " ") == old[field].replace("T", " ")
                  for field in ("start_time", "end_time", "machine_id", "operator_id")), label + ": protected work moved")
        if label.startswith("official:"):
            check(by_id[old["op_id"]]["lock_status"] == "locked", label + ": actual work lost its lock")
    result["verified_schedule_sources"] = [label for label, _ in datasets]
    database = root / "db/aps-live.db"
    conn = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        check(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failed")
        check(conn.execute("PRAGMA foreign_key_check").fetchall() == [], "Foreign keys failed")
        result["reopened_read_only"] = True
    finally:
        conn.close()
    (root / "piece_main_retention.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    evidence = verify(Path(sys.argv[1]))
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    sys.exit(bool(evidence["errors"]))

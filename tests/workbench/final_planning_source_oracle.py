"""SQLite witnesses for the separate candidate-to-draft, no-adoption workflow."""

import json
import sqlite3
from collections import Counter
from urllib.parse import urlsplit

from tests.workbench.final_planning_oracle import read
from tests.workbench.piece_main_oracle import APPEND_TABLES, CLOCK_TABLES, encoded


def verify_source_only(root, host):
    session = root / "sessions" / host["ready"]["session"]
    before, after = read(session / "business-before.json"), read(session / "business-after.json")
    browser = read(root / "final_planning_candidate-source.json")
    errors = []

    def check(value, message):
        if not value:
            errors.append(message)

    check(set(before) == set(after), "Schema tables changed")
    for table, rows in before.items():
        now = after[table]
        if now == rows:
            continue
        check(table in APPEND_TABLES | CLOCK_TABLES, "Unexpected mutation: " + table)
        if table not in CLOCK_TABLES:
            check(not (Counter(map(encoded, rows)) - Counter(map(encoded, now))), "Original rows lost: " + table)
        elif table == "WorkbenchPlanIdentityClock":
            check(now[0]["revision"] >= rows[0]["revision"], "Identity clock regressed")
        else:
            clocks = {row["name"]: row["seq"] for row in now}
            check(all(clocks.get(row["name"], -1) >= row["seq"] for row in rows), "Sequence regressed")
    for table in ("Schedule", "ScheduleHistory", "BatchOperations", "OperatorCalendar", "WorkCalendar"):
        check(before[table] == after[table], "Candidate trial modified production facts: " + table)
    witness = [json.loads(line) for line in (root / "final_planning_official.jsonl").read_text(encoding="utf-8").splitlines()]
    for row in witness:
        check(row["official"] == {name: before[name] for name in ("Schedule", "ScheduleHistory")},
              "Non-adoption workflow changed formal plan: " + row["path"])
    check(not any(row["method"] == "POST" and row["url"].endswith("/adopt") for row in browser["requests"]), "Adoption was sent")
    check(len(after["WorkbenchRunJobs"]) == 1 and after["WorkbenchRunJobs"][0]["state"] == "complete", "Run is not complete")
    check(len(after["WorkbenchRunCandidates"]) == 4, "Candidate cohort changed")
    draft = browser["candidate_source_draft"]
    check(len(after["WorkbenchTrialDrafts"]) == 1 and after["WorkbenchTrialDrafts"][0]["draft_ref"] == draft["draft_ref"], "Draft not persisted")
    check(draft["task_count"] == 13 and len(after["WorkbenchTrialRows"]) == 13, "Candidate draft scope is incomplete")
    observed = Counter((row["method"], urlsplit(row["url"]).path, (row.get("input") or {}).get("request_key"))
                       for row in browser["requests"] if row["method"] == "POST")
    journal = [json.loads(line) for line in (session / "server-requests.jsonl").read_text(encoding="utf-8").splitlines()]
    actual = Counter((row["method"], row["path"], row.get("request_key")) for row in journal if row["method"] == "POST")
    check(observed == actual, "Server POSTs differ from browser-triggered POSTs")
    conn = sqlite3.connect((root / "db/aps-live.db").as_uri() + "?mode=ro", uri=True)
    try:
        check(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failed")
        check(not conn.execute("PRAGMA foreign_key_check").fetchall(), "Foreign keys failed")
    finally:
        conn.close()
    return {"root": str(root), "width": browser["width"], "theme": browser["theme"], "errors": errors,
            "tables": len(before), "original_rows_retained": not errors,
            "formal_plan_unchanged": all(before[name] == after[name] for name in ("Schedule", "ScheduleHistory")),
            "source_build": read(root / "piece_main_build.json"), "actions": len(browser["actions"])}

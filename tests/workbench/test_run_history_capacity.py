"""Thousands of durable candidates with bounded query count and no payload access."""

import sqlite3
import time

from tests.workbench.test_run_history_support import BASE, api, dump, read, seed
from tests.workbench.test_run_history_support import history_case as _history_case


def test_350_runs_5000_candidates_batched_counts_without_reading_payloads(history_case):
    case = history_case
    seed(case, "complete", counts=tuple([1] * 50))
    denied_reads = {"WorkbenchRunJobs": {"facts_json", "execution_json", "baseline_json"},
                    "WorkbenchRunCandidates": {"artifact_json"}, "WorkbenchRunCandidateTasks": {"payload_json"}}
    touched = set()

    def authorize(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ:
            touched.add((table, column))
            assert column not in denied_reads.get(table, set())
            assert table not in ("Machines", "Operators", "Batches", "BatchOperations", "Schedule", "ScheduleHistory")
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    client, statements = api(case, authorize)
    assert read(client)["data"]["runs"][0]["candidate_count"] == 50
    initial_queries = len(statements)
    for _ in range(99):
        seed(case, "complete", counts=tuple([1] * 50))
    for _ in range(250):
        seed(case, "queued")
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 5000
    before = dump(case.conn)
    statements.clear()
    start = time.monotonic()
    first = read(client, state="complete", size=50)
    elapsed = time.monotonic() - start
    assert len(statements) == initial_queries and initial_queries <= 20
    second = read(client, state="complete", size=50, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
    all_rows = first["data"]["runs"] + second["data"]["runs"]
    assert first["data"]["run_count"] == 350 and first["data"]["page"]["total"] == 100
    assert len({row["run_ref"] for row in all_rows}) == 100
    assert sum(row["candidate_count"] for row in all_rows) == sum(row["task_count"] for row in all_rows) == 5000
    assert ("WorkbenchRunCandidateTasks", "row_ref") in touched
    assert dump(case.conn) == before
    print(f"BQ directory evidence: runs=350 candidates=5000 tasks=5000 queries={initial_queries} first_page_seconds={elapsed:.3f}")


def test_directory_capacity_fails_explicitly_instead_of_truncating(history_case, monkeypatch):
    from core.services.workbench import run_history_storage

    seed(history_case)
    seed(history_case)
    client, _ = api(history_case)
    monkeypatch.setattr(run_history_storage, "MAX_DIRECTORY_ROWS", 1)
    response = client.get(BASE)
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "run_history_capacity_exceeded"

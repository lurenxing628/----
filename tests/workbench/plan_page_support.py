"""Temporary SQLite fixtures and repeatable page measurements, never app/real DB."""

import sqlite3
from pathlib import Path
from time import perf_counter

from tests.workbench.plan_catalog_support import END, START


def create_scale_database(path, *, history_count=10000, rows_per_history=50, scenario_count=2000):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('PAGE-P', 'Page scale')")
    conn.execute("INSERT INTO Batches(batch_id, part_no, quantity) VALUES ('PAGE-B', 'PAGE-P', 1)")
    conn.executemany(
        "INSERT INTO BatchOperations(id, op_code, batch_id, seq, op_type_name) VALUES (?, ?, 'PAGE-B', ?, 'Scale op')",
        ((op, f"PAGE-OP-{op}", op) for op in range(1, rows_per_history + 1)),
    )
    conn.executemany(
        "INSERT INTO ScheduleHistory(version, strategy, result_status, result_summary) VALUES (?, 'catalog', ?, '{}')",
        ((version, "partial" if version == history_count else "success") for version in range(1, history_count + 1)),
    )
    conn.executemany(
        "INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (?, ?, ?, ?)",
        ((version, op, START, END) for version in range(1, history_count + 1)
         for op in range(1, rows_per_history + 1)),
    )
    conn.executemany(
        "INSERT INTO ScheduleAdjustmentScenario(scenario_id, source_draft_id, base_version, base_plan_role, "
        "base_source_table, status, validation_status, row_count) VALUES (?, ?, ?, 'adopted', 'schedule', 'active', 'valid', 20)",
        ((f"S{i:06d}", f"D{i:06d}", history_count - ((i - 1) % history_count))
         for i in range(1, scenario_count + 1)),
    )
    conn.executemany(
        "INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id, source_table, op_id, start_time, end_time) "
        "VALUES (?, 'schedule', ?, ?, ?)",
        ((f"S{i:06d}", op, START, END) for i in range(1, scenario_count + 1) for op in range(1, 21)),
    )
    conn.commit()
    return conn


def measure_page(conn, loader, *, repeats=3, **kwargs):
    samples = []
    sql_counts = []
    vm_steps = []
    entry_counts = []
    for _ in range(repeats):
        statements = []
        progress = [0]

        def tick():
            progress[0] += 100
            return 0

        conn.set_trace_callback(statements.append)
        conn.set_progress_handler(tick, 100)
        start = perf_counter()
        try:
            page = loader(conn, **kwargs)
        finally:
            elapsed = perf_counter() - start
            conn.set_trace_callback(None)
            conn.set_progress_handler(None, 0)
        samples.append(round(elapsed * 1000, 3))
        sql_counts.append(len(statements))
        vm_steps.append(progress[0])
        entry_counts.append(len(page.entries))
    return {"elapsed_ms": samples, "sql_counts": sql_counts, "vm_steps_approx": vm_steps, "entries": entry_counts}

"""Bounded SQL, consistent snapshots, and production-parser delivery contracts."""

import sqlite3
from time import perf_counter

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.services.workbench import plan_delivery, plan_delivery_repository
from tests.workbench.plan_delivery_support import add_operation, context, grow_tasks, read, readonly, seed_delivery


@pytest.mark.parametrize("batches", [False, True])
def test_real_10000_tasks_are_complete_and_queries_are_chunked(schema_conn, batches):
    conn = schema_conn
    seed_delivery(conn)
    grow_tasks(conn, 9999, batches=batches)
    ctx = context(conn)
    sql = []
    changes = conn.total_changes
    conn.set_trace_callback(sql.append)
    started = perf_counter()
    try:
        public, facts = read(conn, ctx)
    finally:
        conn.set_trace_callback(None)
    elapsed = perf_counter() - started
    assert len(facts["tasks"]) == len(facts["operations"]) == 10000
    assert sum(item["task_count"] for item in public["items"]) == 10000
    assert public["batch_count"] == (10000 if batches else 1)
    assert all(item["schedule_complete"] for item in public["items"])
    assert public["items_complete"] and public["completeness"] == "complete"
    assert len(sql) < 150, "No per-task or per-batch SELECT loop"
    assert conn.total_changes == changes
    assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")) for statement in sql)
    size = len(canonical_json(public).encode("utf-8"))
    print("delivery_scale tasks=10000 batches={} seconds={:.3f} sql={} bytes={}".format(public["batch_count"], elapsed, len(sql), size))


def test_10001_full_plan_rows_fail_before_parsing_even_in_tiny_scope(schema_conn, monkeypatch):
    conn = schema_conn
    seed_delivery(conn)
    ctx = context(conn, start="2026-09-09T08:00:00", end="2026-09-09T09:00:00")
    grow_tasks(conn, 10000)

    def forbidden(rows):
        pytest.fail("Oversized full plan must be refused before parsing or visible-range filtering")

    monkeypatch.setattr(plan_delivery, "task_intervals", forbidden)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read(conn, ctx)
    assert exc.value.code == "query_too_large" and exc.value.status == 413


def test_full_batch_operation_limit_cannot_be_hidden_by_few_scheduled_tasks(schema_conn, monkeypatch):
    conn = schema_conn
    seed_delivery(conn)
    ctx = context(conn)
    conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name) VALUES (?,'CAT-B',?,'Missing')",
                     (("missing-" + str(seq), seq) for seq in range(2, 12)))
    conn.commit()
    monkeypatch.setattr(plan_delivery_repository, "MAX_PLAN_TASKS", 10)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read(conn, ctx)
    assert exc.value.code == "query_too_large"


def test_public_size_limit_is_all_or_error(schema_conn, monkeypatch):
    seed_delivery(schema_conn)
    ctx = context(schema_conn)
    monkeypatch.setattr(plan_delivery, "MAX_PLAN_RESPONSE_BYTES", 500)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read(schema_conn, ctx)
    assert exc.value.code == "query_too_large"


def test_reads_share_callers_wal_snapshot_and_refs_survive_reopen(schema_conn, tmp_path):
    seed_delivery(schema_conn)
    path = str(tmp_path / "delivery-snapshot.sqlite")
    writer = sqlite3.connect(path)
    schema_conn.backup(writer)
    writer.execute("PRAGMA journal_mode=WAL")
    reader = sqlite3.connect(path)
    reader.row_factory = sqlite3.Row
    try:
        scope, identity = context(reader)
        with readonly(reader):
            before, facts = plan_delivery.read_plan_delivery(reader, scope=scope, identity=identity)
            writer.execute("UPDATE Batches SET due_date='2026-09-01' WHERE batch_id='CAT-B'")
            writer.commit()
            same = plan_delivery.read_plan_delivery(reader, scope=scope, identity=identity)
            assert same == (before, facts) and reader.in_transaction
        after, fresh = read(reader, (scope, identity))
        assert input_fingerprint(fresh) != input_fingerprint(facts)
        assert after["items"][0]["risk"] == "overdue"
        assert after["items"][0]["batch_ref"] == before["items"][0]["batch_ref"]
    finally:
        reader.close()
        writer.close()


def test_declared_date_converter_cannot_hide_bad_due_as_database_decode_error(schema_conn, tmp_path):
    from core.infrastructure.database import get_connection

    seed_delivery(schema_conn)
    path = str(tmp_path / "delivery-converters.sqlite")
    with sqlite3.connect(path) as target:
        schema_conn.backup(target)
    conn = get_connection(path)
    try:
        ctx = context(conn)
        conn.execute("UPDATE Batches SET due_date='bad-date' WHERE batch_id='CAT-B'")
        conn.commit()
        item = read(conn, ctx)[0]["items"][0]
        assert item["risk"] == "unknown" and "due_date_invalid" in item["issues"]
    finally:
        conn.close()


@pytest.mark.parametrize("source", ["candidate", "scenario"])
def test_full_source_limit_is_candidate_and_scenario_specific(schema_conn, monkeypatch, source):
    conn = schema_conn
    seed = seed_delivery(conn)
    ctx = context(conn, role="baseline_best", scenario_id="DELIVERY-SCENARIO" if source == "scenario" else None)
    op = add_operation(conn, version=None)
    if source == "candidate":
        conn.execute("INSERT INTO ScheduleCandidateRows(version,candidate_id,op_id,start_time,end_time) "
                     "VALUES (2,?,?,'2026-09-10 01:00:00','2026-09-10 03:00:00')", (seed["baseline"], op))
    else:
        conn.execute("INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id,source_table,op_id,start_time,end_time) "
                     "VALUES ('DELIVERY-SCENARIO','candidate_rows',?,'2026-09-10 01:00:00','2026-09-10 03:00:00')", (op,))
    conn.commit()
    monkeypatch.setattr(plan_delivery_repository, "MAX_PLAN_TASKS", 1)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read(conn, ctx)
    assert exc.value.code == "query_too_large"

"""Lower helper + real append persistence only; no production guard is patched out."""

import json
import sqlite3
from dataclasses import asdict

import pytest

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_run_job import durable_value
from core.services.workbench.official_plan_persistence import persist_official_plan_in_tx
from core.services.workbench.piece_adoption import validate_piece_adoption
from tests.workbench.piece_adoption_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.piece_adoption_support import greedy_payload, lower_input, slot_payload, split
from tests.workbench.run_candidate_adoption_support import assert_retained, snapshot
from tests.workbench.run_candidate_support import connect


def _lower_save(case, prepared, value, engine_results, engine):
    proof = validate_piece_adoption(case.conn, prepared=prepared, payload=value)
    # The origin is explicitly lower-layer evidence, not an invented candidate/scenario.
    audit = {"action": "ec_lower_piece_validation", "source": engine,
             "engine_results": durable_value(engine_results), "validated_payload": durable_value(value),
             "source_work": [asdict(op) for op in prepared.operations], "piece_proof": asdict(proof)}
    return persist_official_plan_in_tx(case.conn, prepared=prepared, payload=value,
        baseline={"version": 1, "plan_ref": case.plan_ref(1)}, audit=audit, application_operator="EC lower test")


@pytest.mark.parametrize("engine", ["real_greedy_lower", "real_slot_engine_with_actuals_lower"])
def test_new_version_retains_true_origin_old_raw_plan_and_execution(candidate_case, engine):
    case = candidate_case
    ids = split(case, common=False, quantity=2, unit=0 if engine == "real_greedy_lower" else 0.25)
    first = ids["item-A", 20]
    if engine == "real_greedy_lower":
        case.conn.execute("UPDATE BatchOperations SET setup_hours=0.25")
    case.plan(1, [first], end="2026-09-09T08:15:00")
    if engine == "real_greedy_lower":
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
        case.conn.commit()
    else:
        case.command("create", case.task(1, first), case.values(1))
    prepared = lower_input(case)
    if engine == "real_greedy_lower":
        results, value = greedy_payload(prepared)
    else:
        value = slot_payload(prepared)
        results = value.schedule_rows
    before = snapshot(case.conn)
    raw = {name: before[name] for name in ("BatchOperations", "Batches", "WorkbenchProductionReports",
                                          "WorkbenchProductionReportRevisions", "OperationExecutionEvents")}
    case.conn.execute("BEGIN IMMEDIATE")
    try:
        result = _lower_save(case, prepared, value, results, engine)
        case.conn.commit()
    except Exception:
        case.conn.rollback()
        raise
    after = snapshot(case.conn)
    assert_retained(before, after)
    assert all(after[name] == rows for name, rows in raw.items())
    assert result["official_plan"]["version"] == 2
    assert result["row_count"] == len(prepared.operations) == 4
    summary = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=2").fetchone()[0])
    assert summary["source"] == engine
    assert summary["engine_results"] == durable_value(results)
    assert summary["source_work"] == [asdict(op) for op in prepared.operations]
    assert summary["baseline_ref"] == case.plan_ref(1)
    new_ref = result["official_plan"]["plan_ref"]
    assert new_ref != case.plan_ref(1)
    assert case.conn.execute("SELECT count(*) FROM WorkbenchTaskRefs WHERE plan_ref=?", (new_ref,)).fetchone()[0] == 4
    saved = {row["op_id"]: dict(row) for row in case.conn.execute("SELECT * FROM Schedule WHERE version=2")}
    for row in value.schedule_rows:
        assert saved[row.op_id]["start_time"] == row.start_time.isoformat(sep=" ")
        assert saved[row.op_id]["end_time"] == row.end_time.isoformat(sep=" ")
        assert saved[row.op_id]["machine_id"] == row.machine_id
        assert saved[row.op_id]["operator_id"] == row.operator_id
    assert saved[first]["lock_status"] == "locked"
    assert case.conn.execute("SELECT count(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0


@pytest.mark.parametrize("table", ["ScheduleHistory", "OperationLogs"])
def test_failure_after_real_schedule_insert_rolls_back_every_table(candidate_case, table):
    case = candidate_case
    ids = split(case, common=False)
    case.plan(1, [ids["item-A", 20]], end="2026-09-09T08:15:00")
    case.conn.execute('CREATE TRIGGER ec_piece_fail BEFORE INSERT ON "' + table + '" '
                      "BEGIN SELECT RAISE(ABORT,'EC persistence failure'); END")
    case.conn.commit()
    prepared = lower_input(case)
    value = slot_payload(prepared)
    before = snapshot(case.conn)
    case.conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(Exception) as caught:
            _lower_save(case, prepared, value, value.schedule_rows, "real_slot_engine_lower")
        assert "EC persistence failure" in str(caught.value.__cause__ or caught.value)
    finally:
        case.conn.rollback()
    assert snapshot(case.conn) == before


def test_writer_lock_covers_helper_and_save_and_second_connection_drift_is_rejected(candidate_case):
    case = candidate_case
    ids = split(case, common=False)
    case.plan(1, [ids["item-A", 20]], end="2026-09-09T08:15:00")
    prepared = lower_input(case)
    value = slot_payload(prepared)
    other = connect(case.path)
    other.execute("PRAGMA busy_timeout=1")
    before = snapshot(case.conn)
    case.conn.execute("BEGIN IMMEDIATE")
    try:
        validate_piece_adoption(case.conn, prepared=prepared, payload=value)
        assert case.conn.in_transaction
        assert case.conn.execute("PRAGMA query_only").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            other.execute("UPDATE BatchOperations SET unit_hours=0.5 WHERE id=?", (ids["item-A", 20],))
        other.rollback()
        _lower_save(case, prepared, value, value.schedule_rows, "real_slot_engine_lower")
    finally:
        case.conn.rollback()
    assert snapshot(case.conn) == before
    try:
        other.execute("UPDATE BatchOperations SET unit_hours=0.5 WHERE id=?", (ids["item-A", 20],))
        other.commit()
        after_edit = snapshot(case.conn)
        with pytest.raises(PieceAdoptionBlocked) as caught:
            validate_piece_adoption(case.conn, prepared=prepared, payload=value)
        assert caught.value.code == "piece_raw_changed"
        assert snapshot(case.conn) == after_edit
    finally:
        other.close()

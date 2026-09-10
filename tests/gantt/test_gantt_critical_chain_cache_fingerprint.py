"""D03: full query content, not COUNT/MAX(id)/MAX(created_at), identifies a chain."""

from __future__ import annotations

import logging
import sqlite3

import pytest

from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.gantt_critical_chain_snapshot import CriticalChainSnapshot
from tests.gantt.gantt_critical_chain_cache_support import SOURCES, assert_matches_direct, cache_db, reset_cache


@pytest.mark.parametrize("source", SOURCES)
def test_restore_then_same_second_same_ids_reschedule_misses_cache(monkeypatch, source):
    reset_cache(monkeypatch)
    with cache_db(source, seed=False) as case:
        snapshot = sqlite3.connect(":memory:")
        try:
            case.conn.backup(snapshot)
            case.seed_rows()
            assert case.read()["ids"] == ["A", "B"]
            assert case.read()["cache_hit"] is True
            before = case.old_aggregate()
            sequence = tuple(case.conn.execute("SELECT * FROM sqlite_sequence WHERE name = ?", (case.table,)).fetchone())

            snapshot.backup(case.conn)
            case.seed_rows(machine_b="M2")
            assert case.old_aggregate() == before
            assert tuple(case.conn.execute("SELECT * FROM sqlite_sequence WHERE name = ?", (case.table,)).fetchone()) == sequence
            changed = case.read()
            assert changed["ids"] == ["B"]
            assert changed["cache_hit"] is False
            assert_matches_direct(case, changed)
            assert case.read()["cache_hit"] is True
        finally:
            snapshot.close()


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("assignment", [
    "machine_id = 'M2'", "operator_id = 'O2'", "start_time = '2026-09-08 08:30:00'",
    "end_time = '2026-09-08 12:00:00'", "end_time = 'bad-time'", "op_id = 1",
])
def test_in_place_row_change_with_identical_aggregates(monkeypatch, source, assignment):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        if assignment == "op_id = 1":
            case.conn.execute("DELETE FROM " + case.table + " WHERE op_id = 1")
            case.conn.commit()
        case.read()
        before = case.old_aggregate()
        case.conn.execute("UPDATE " + case.table + " SET " + assignment + " WHERE op_id = 2")
        case.conn.commit()
        assert case.old_aggregate() == before
        changed = case.read()
        assert changed["cache_hit"] is False
        assert_matches_direct(case, changed)
        assert case.read()["cache_hit"] is True


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("assignment", ["op_code = 'B2'", "batch_id = 'X'", "piece_id = 'piece2'", "seq = 3"])
def test_joined_operation_changes_invalidate_without_plan_writes(monkeypatch, source, assignment):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        case.read()
        before = case.old_aggregate()
        case.conn.execute("UPDATE BatchOperations SET " + assignment + " WHERE id = 2")
        case.conn.commit()
        assert case.old_aggregate() == before
        changed = case.read()
        assert changed["cache_hit"] is False
        assert_matches_direct(case, changed)


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("field", ["op_type_name", "part_no", "part_name"])
def test_joined_fallback_labels_are_content(monkeypatch, source, field):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        case.conn.execute("UPDATE BatchOperations SET op_code = '', seq = '', op_type_name = '' WHERE id = 1")
        case.conn.commit()
        first = case.read()
        if field == "op_type_name":
            case.conn.execute("UPDATE BatchOperations SET op_type_name = 'New-cut' WHERE id = 1")
        else:
            case.conn.execute("UPDATE Batches SET " + field + " = 'New-part' WHERE batch_id = 'X'")
        case.conn.commit()
        changed = case.read()
        assert changed["cache_hit"] is False
        assert changed["edges"][0]["from_label"] != first["edges"][0]["from_label"]
        assert_matches_direct(case, changed)


@pytest.mark.parametrize("source", SOURCES)
def test_process_and_operator_edge_changes(monkeypatch, source):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        case.conn.execute("UPDATE " + case.table + " SET machine_id = NULL, operator_id = 'O1'")
        case.conn.commit()
        assert case.read()["edges"][0]["edge_type"] == "operator"
        case.conn.execute("UPDATE " + case.table + " SET operator_id = NULL")
        case.conn.execute("UPDATE BatchOperations SET batch_id = 'X' WHERE id = 2")
        case.conn.commit()
        process = case.read()
        assert process["cache_hit"] is False
        assert process["edges"][0]["edge_type"] == "process"
        case.conn.execute("UPDATE BatchOperations SET piece_id = 'different' WHERE id = 2")
        case.conn.commit()
        parallel = case.read()
        assert parallel["cache_hit"] is False
        assert parallel["ids"] == ["B"]
        assert_matches_direct(case, parallel)


def test_fingerprint_failure_bypasses_warm_cache_and_logs(monkeypatch, caplog):
    reset_cache(monkeypatch)
    with cache_db() as case:
        case.read()
        cache = dict(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE)
        case.provider.logger = logging.getLogger(__name__)

        def fail(_self):
            raise TypeError("unsupported input")

        monkeypatch.setattr(CriticalChainSnapshot, "fingerprint", fail)
        case.conn.execute("UPDATE Schedule SET machine_id = 'M2' WHERE op_id = 2")
        case.conn.commit()
        with caplog.at_level(logging.WARNING):
            for _ in range(2):
                result = case.read()
                assert result["cache_hit"] is False
                assert result["ids"] == ["B"]
                assert_matches_direct(case, result)
        assert "unsupported input" in caplog.text
        assert dict(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) == cache


def test_cache_capacity_evicts_oldest_key(monkeypatch):
    reset_cache(monkeypatch, cache_max=2)
    with cache_db() as case:
        assert case.read(1)["cache_hit"] is False
        assert case.read(2)["cache_hit"] is False
        assert case.read(3)["cache_hit"] is False
        assert len(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) == 2
        assert case.read(3)["cache_hit"] is True
        assert case.read(1)["cache_hit"] is False


def test_fingerprint_keeps_types_order_and_all_columns():
    def fingerprint(rows):
        return CriticalChainSnapshot(rows).fingerprint()

    assert fingerprint([{"b": 1, "a": "x"}]) == fingerprint([{"a": "x", "b": 1}])
    cases = [[], [{"a": None}], [{"a": "None"}], [{"a": 1}], [{"a": "1"}],
             [{"a": "x\ny"}], [{"a": "x"}, {"a": "y"}], [{"a": "y"}, {"a": "x"}],
             [{"a": "x", "extra": "y"}]]
    assert len({fingerprint(rows) for rows in cases}) == len(cases)
    with pytest.raises(TypeError):
        fingerprint([{"unsupported": object()}])

"""Source boundaries, read failures and cache lifecycle over real detail rows."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

import core.services.scheduler.gantt_critical_chain_provider as provider_module
from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.gantt_critical_chain_snapshot import CriticalChainSnapshot
from tests.gantt.gantt_critical_chain_cache_support import SOURCES, assert_matches_direct, cache_db, reset_cache


@pytest.mark.parametrize("source", SOURCES)
def test_one_detail_select_per_call_but_compute_only_on_miss(monkeypatch, source):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        queries = []
        calls = []
        name = "compute_critical_chain" if source == "schedule" else "compute_critical_chain_from_rows"
        original = getattr(provider_module, name)

        def compute(*args):
            calls.append(args)
            return original(*args)

        monkeypatch.setattr(provider_module, name, compute)
        case.conn.set_trace_callback(queries.append)
        assert case.read()["cache_hit"] is False
        assert case.read()["cache_hit"] is True
        assert len(calls) == 1
        assert len([sql for sql in queries if "LEFT JOIN BatchOperations" in sql]) == 2
        assert not any("COUNT(*)" in sql or sql.startswith(("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT")) for sql in queries)
        assert case.conn.in_transaction is False


@pytest.mark.parametrize("source", SOURCES)
def test_read_failure_cannot_use_warm_cache(monkeypatch, source):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        assert case.read()["available"] is True
        before = dict(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE)
        case.conn.execute("ALTER TABLE BatchOperations RENAME TO HiddenOperations")
        failed = case.read()
        assert failed["available"] is False
        assert failed["cache_hit"] is False
        assert failed["ids"] == []
        assert failed["reason_code"] == ("repo_exception" if source == "schedule" else "rows_load_exception")
        assert dict(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) == before
        case.conn.execute("ALTER TABLE HiddenOperations RENAME TO BatchOperations")
        assert case.read()["available"] is True


@pytest.mark.parametrize("phase", ["load", "compute"])
def test_clear_cache_blocks_inflight_refill(monkeypatch, phase):
    reset_cache(monkeypatch)
    with cache_db() as case:
        if phase == "load":
            target, name = case.provider, "_load_plan_rows_snapshot"
        else:
            target, name = provider_module, "compute_critical_chain"
        original = getattr(target, name)

        def clear_during_request(*args, **kwargs):
            value = original(*args, **kwargs)
            GanttCriticalChainProvider.clear_cache()
            return value

        monkeypatch.setattr(target, name, clear_during_request)
        result = case.read()
        assert result["ids"] == ["A", "B"]
        assert result["cache_hit"] is False
        assert not GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE


@pytest.mark.parametrize("source", SOURCES)
def test_unrelated_plan_changes_do_not_invalidate(monkeypatch, source):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        case.read()
        if source == "schedule":
            sql = "INSERT INTO Schedule(version, op_id, machine_id, start_time, end_time) VALUES (2, 1, 'other', 'x', 'y')"
        elif source == "candidate_rows":
            sql = "INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, start_time, end_time) VALUES (1, 202, 1, 'x', 'y')"
        else:
            sql = "INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id, source_table, op_id, start_time, end_time) VALUES ('S2', 'schedule', 1, 'x', 'y')"
        case.conn.execute(sql)
        case.conn.commit()
        assert case.read()["cache_hit"] is True


@pytest.mark.parametrize("assignment", ["status = 'discarded'", "status = 'published'", "base_version = 2"])
def test_scenario_parent_predicate_is_part_of_snapshot(monkeypatch, assignment):
    reset_cache(monkeypatch)
    with cache_db("adjustment_scenario_rows") as case:
        assert case.read()["ids"] == ["A", "B"]
        case.conn.execute("UPDATE ScheduleAdjustmentScenario SET " + assignment)
        case.conn.commit()
        result = case.read()
        assert result["cache_hit"] is False
        assert result["ids"] == []
        assert_matches_direct(case, result)
        case.conn.execute("UPDATE ScheduleAdjustmentScenario SET status = 'active', base_version = 1")
        case.conn.commit()
        assert case.read()["ids"] == ["A", "B"]


def test_scenario_identity_and_resolved_candidate_ignore_current_selection(monkeypatch):
    reset_cache(monkeypatch)
    with cache_db("adjustment_scenario_rows") as case:
        assert case.read()["ids"] == ["A", "B"]
        other = dict(case.plan, scenario_id="S2")
        assert case.read(plan=other)["ids"] == []
        assert case.read()["ids"] == ["A", "B"]
    with cache_db("candidate_rows") as case:
        case.read()
        case.conn.execute("INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table) VALUES (1, 'baseline_best', 202, 'candidate_rows')")
        case.conn.commit()
        assert case.read()["cache_hit"] is True
        assert case.read(plan=dict(case.plan, candidate_id=202))["ids"] == []


@pytest.mark.parametrize("plan", [
    {"source_table": "unknown"}, {"source_table": "candidate_rows", "candidate_id": None},
    {"source_table": "adjustment_scenario_rows", "scenario_id": None},
])
def test_invalid_resolution_is_unavailable_not_cached(monkeypatch, plan):
    reset_cache(monkeypatch)
    with cache_db() as case:
        case.read()
        before = dict(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE)
        result = case.read(plan=plan)
        assert result["available"] is False
        assert result["reason_code"] == "rows_load_exception"
        assert not result["cache_hit"]
        assert dict(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) == before


def test_identical_rows_keep_role_source_and_database_scopes_separate(monkeypatch):
    reset_cache(monkeypatch)
    with cache_db("candidate_rows") as case, cache_db("candidate_rows") as other:
        assert case.read()["cache_hit"] is False
        assert other.read()["cache_hit"] is False
        assert case.read(plan=dict(case.plan, selected_role="critical_best"))["cache_hit"] is False
        assert case.read()["cache_hit"] is True
        # Identical empty snapshots must still keep their source identities.
        assert case.read(9)["cache_hit"] is False
        assert case.read(9, plan=dict(case.plan, source_table="schedule"))["cache_hit"] is False


def test_concurrent_cache_reads_use_real_per_thread_connections(monkeypatch):
    reset_cache(monkeypatch, cache_max=4)

    def worker(_index):
        with cache_db() as case:
            for version in range(16):
                result = case.read(version + 1)
                assert result["available"] is True
                assert result["ids"] == (["A", "B"] if version == 0 else [])
            hit = case.read(16)
            hit["ids"].append("mutated")
            assert case.read(16)["ids"] == []

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(16)))
    assert len(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) <= 4


def test_duplicate_task_order_is_not_sorted_away(monkeypatch):
    reset_cache(monkeypatch)
    with cache_db() as case:
        rows = [dict(row, op_code="same") for row in case.rows()]
        forward = CriticalChainSnapshot(rows)
        backward = CriticalChainSnapshot(list(reversed(rows)))
        assert forward.fingerprint() != backward.fingerprint()
        assert provider_module.compute_critical_chain(forward, 1)["makespan_end"] != provider_module.compute_critical_chain(backward, 1)["makespan_end"]

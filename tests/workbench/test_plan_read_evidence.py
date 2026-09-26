"""Verified archive reuse has a read-transaction lifetime, never a request TTL."""

import sqlite3
from contextlib import closing, nullcontext

import pytest

from core.infrastructure.read_evidence import read_evidence_scope, verified_read
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.facts import trial_scenario_archive
from core.services.workbench.plan import queries
from tests.workbench.plan_adoption_baseline_support import mutate_json, two_versions
from tests.workbench.plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401


def test_wal_writer_does_not_change_the_held_snapshot_and_next_read_is_fresh(tmp_path):
    path = str(tmp_path / "facts.sqlite")
    with closing(sqlite3.connect(path)) as reader, closing(sqlite3.connect(path)) as writer:
        reader.execute("PRAGMA journal_mode=WAL")
        reader.execute("CREATE TABLE facts(value INTEGER)")
        reader.execute("INSERT INTO facts VALUES (1)")
        reader.commit()
        calls = []
        def load():
            calls.append(True)
            return reader.execute("SELECT value FROM facts").fetchone()[0]
        reader.execute("BEGIN")
        assert load() == 1
        with read_evidence_scope(reader):
            assert verified_read(reader, "fact", load) == 1
            writer.execute("UPDATE facts SET value=2")
            writer.commit()
            assert verified_read(reader, "fact", load) == 1
            assert len(calls) == 2
        reader.commit()
        reader.execute("BEGIN")
        with read_evidence_scope(reader):
            assert verified_read(reader, "fact", load) == 2
        assert len(calls) == 3


def test_scope_rejects_writes_restores_query_only_and_does_not_commit():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("CREATE TABLE facts(value INTEGER)")
        conn.execute("BEGIN")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            with read_evidence_scope(conn):
                conn.execute("INSERT INTO facts VALUES (1)")
        assert conn.in_transaction
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0
        conn.execute("INSERT INTO facts VALUES (2)")
        conn.rollback()


def test_nested_connections_and_failures_do_not_share_or_retain_evidence():
    with closing(sqlite3.connect(":memory:")) as one, closing(sqlite3.connect(":memory:")) as two:
        one.execute("BEGIN")
        two.execute("BEGIN")
        with read_evidence_scope(one):
            assert verified_read(one, "same", lambda: "one") == "one"
            assert verified_read(two, "same", lambda: "two-direct") == "two-direct"
            with pytest.raises(ValueError):
                with read_evidence_scope(two):
                    assert verified_read(two, "same", lambda: "two") == "two"
                    raise ValueError("stop nested read")
            assert verified_read(one, "same", lambda: "wrong") == "one"
        assert verified_read(one, "same", lambda: "fresh-outside") == "fresh-outside"


def test_finished_transaction_cannot_serve_verified_evidence():
    with closing(sqlite3.connect(":memory:")) as conn:
        with pytest.raises(RuntimeError, match="existing read transaction"):
            with read_evidence_scope(conn):
                pass
        conn.execute("BEGIN")
        with read_evidence_scope(conn):
            assert verified_read(conn, "value", lambda: 1) == 1
            conn.commit()
            with pytest.raises(RuntimeError, match="snapshot changed"):
                verified_read(conn, "value", lambda: 2)


def test_plan_dto_and_fingerprint_are_identical_with_one_archive_verification(trial_case, monkeypatch):
    _, official = two_versions(trial_case)
    reader = queries.WorkbenchPlanQueryService(trial_case.conn)
    scope = PlanReadScope(official["plan_ref"])
    original = trial_scenario_archive._load_saved_scenario
    calls = []
    def load(conn, ref):
        calls.append(ref)
        return original(conn, ref)
    monkeypatch.setattr(trial_scenario_archive, "_load_saved_scenario", load)
    with reader.read_snapshot():
        actual = reader.workspace(scope)
    assert len(calls) == 1
    monkeypatch.setattr(queries, "read_evidence_scope", lambda _: nullcontext())
    calls.clear()
    with reader.read_snapshot():
        uncached = reader.workspace(scope)
    assert actual == uncached
    assert len(calls) > 1


def test_separate_workspace_reads_reverify_corrupted_saved_source(trial_case, monkeypatch):
    _, official = two_versions(trial_case)
    reader = queries.WorkbenchPlanQueryService(trial_case.conn)
    scope = PlanReadScope(official["plan_ref"])
    with reader.read_snapshot():
        first, _ = reader.workspace(scope)
    assert first["projections"]["baseline"]["state"] == "available"
    mutate_json(trial_case.conn, "WorkbenchTrialScenarios", "snapshot_json",
        lambda saved: saved["tasks"][0].update(start="2026-09-09T09:00:00"))
    with reader.read_snapshot():
        second, _ = reader.workspace(scope)
    assert second["projections"]["baseline"]["state"] == "unavailable"

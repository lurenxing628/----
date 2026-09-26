"""Committed receipts remain usable while DELETE-mode readers/writers are active."""

import sqlite3
from contextlib import closing

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.test_commands import INPUT, KEY, run


@pytest.fixture
def replay_database(schema_conn, tmp_path):
    path = tmp_path / "receipt-replay.sqlite"
    with closing(sqlite3.connect(str(path), timeout=0.05)) as conn:
        schema_conn.backup(conn)
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
        saved = run(conn)
        yield path, conn, saved


def forbidden_guard(*_args):
    pytest.fail("A committed receipt must not repeat domain validation or mutation")


@pytest.mark.parametrize("lock_sql", ["BEGIN", "BEGIN IMMEDIATE"])
def test_committed_replay_does_not_compete_for_another_connections_lock(replay_database, lock_sql):
    path, conn, saved = replay_database
    with closing(sqlite3.connect(str(path), timeout=0.05)) as contender:
        contender.execute(lock_sql)
        # Pin a real shared read lock, or reserve the only writer slot. Neither
        # prevents reading a previously committed immutable receipt.
        contender.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()
        before = conn.total_changes
        try:
            repeated = run(conn, guard=forbidden_guard, mutate=forbidden_guard)
        finally:
            contender.rollback()
        assert repeated == {**saved, "replayed": True}
        assert conn.total_changes == before and not conn.in_transaction
        assert conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1


@pytest.mark.parametrize("override", [
    {"action": "op_type.update"},
    {"context_ref": "different.collection"},
    {"normalized_input": {**INPUT, "name": "different"}},
])
def test_replay_under_writer_lock_still_rejects_changed_intent(replay_database, override):
    path, conn, _saved = replay_database
    with closing(sqlite3.connect(str(path), timeout=0.05)) as contender:
        contender.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                run(conn, guard=forbidden_guard, mutate=forbidden_guard, **override)
        finally:
            contender.rollback()
    assert rejected.value.code == "request_key_conflict"
    assert not conn.in_transaction


def test_existing_receipt_still_refuses_caller_owned_transaction(replay_database):
    _path, conn, _saved = replay_database
    with TransactionManager(conn).transaction():
        with pytest.raises(RuntimeError, match="最外层事务"):
            run(conn)
        assert conn.in_transaction


def test_malformed_saved_receipt_is_uncertain_and_never_reexecutes(replay_database):
    _path, conn, _saved = replay_database
    conn.execute("UPDATE WorkbenchCommandReceipts SET outcome_json='{}' WHERE request_key=?", (KEY,))
    conn.commit()
    before = conn.total_changes
    with pytest.raises(WorkbenchCommandUncertain) as uncertain:
        run(conn, guard=forbidden_guard, mutate=forbidden_guard)
    assert uncertain.value.request_key == KEY
    assert conn.total_changes == before
    assert not conn.in_transaction


def test_first_lookup_miss_is_rechecked_after_another_submit_commits(replay_database, monkeypatch):
    path, conn, saved = replay_database
    # Start a genuinely new intent, then commit it through another connection
    # after the first lookup has observed no receipt and before our write begins.
    new_key = KEY + "-racing"
    command = WorkbenchCommandService(conn)
    original_get = command.repo.get
    competing = []

    def get(request_key):
        row = original_get(request_key)
        if not competing:
            assert row is None
            with closing(sqlite3.connect(str(path), timeout=0.05)) as contender:
                contender.row_factory = sqlite3.Row
                competing.append(run(contender, request_key=new_key, normalized_input={"same": True},
                                     mutate=lambda _: WorkbenchCommandOutcome("unchanged", {"ref": saved["data"]["ref"]})))
        return row

    monkeypatch.setattr(command.repo, "get", get)
    repeated = command.execute(request_key=new_key, action="op_type.create", context_ref="op_type.collection",
                               normalized_input={"same": True}, guard=forbidden_guard, mutate=forbidden_guard)
    assert repeated == {**competing[0], "replayed": True}
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE request_key=?", (new_key,)).fetchone()[0] == 1

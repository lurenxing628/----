"""Ordinary command intent, nested domain transactions and uncertain commits."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
)
from core.services.process.op_type_service import OpTypeService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

KEY = "request-test-000000001"
INPUT = {"code": "TURN", "name": "Turning", "category": "internal"}


def create(conn, seen=None):
    def mutate(_context):
        if seen is not None:
            seen.append("create")
        item = OpTypeService(conn).create(INPUT["code"], INPUT["name"])
        identity = WorkbenchIdentityRepository(conn).find_active("op_type", item.op_type_id)
        return WorkbenchCommandOutcome("committed", {"ref": identity.ref, "name": item.name})
    return mutate


def run(conn, **overrides):
    arguments = {"request_key": KEY, "action": "op_type.create", "context_ref": "op_type.collection",
                 "normalized_input": INPUT, "guard": lambda: None, "mutate": create(conn)}
    arguments.update(overrides)
    return WorkbenchCommandService(conn).execute(**arguments)


def test_one_intent_replays_exact_result_before_expired_guard(schema_conn):
    seen = []
    first = run(schema_conn, mutate=create(schema_conn, seen))

    def expired():
        pytest.fail("A committed intent must replay without reusing an expired edit context")

    second = run(schema_conn, guard=expired, normalized_input=dict(reversed(list(INPUT.items()))))
    assert seen == ["create"]
    assert first["ok"] and not first["replayed"] and second["replayed"]
    assert {**first, "replayed": True} == second
    assert WorkbenchCommandService(schema_conn).lookup(KEY) == second
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 1
    assert not schema_conn.in_transaction


@pytest.mark.parametrize("override", [
    {"action": "op_type.update"}, {"context_ref": "another.collection"},
    {"normalized_input": {**INPUT, "name": "Another"}},
])
def test_same_key_different_intent_is_conflict(schema_conn, override):
    run(schema_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run(schema_conn, **override)
    assert error.value.code == "request_key_conflict" and error.value.status == 409
    assert error.value.committed is False
    assert schema_conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1


@pytest.mark.parametrize("key", ["", "short", "x" * 129, "with spaces 1234567890", None])
def test_bad_request_key_never_runs_domain_action(schema_conn, key):
    with pytest.raises(WorkbenchCommandRejected) as error:
        run(schema_conn, request_key=key)
    assert error.value.status == 400
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1, 2}])
def test_non_json_input_never_runs_domain_action(schema_conn, bad):
    with pytest.raises(WorkbenchCommandRejected) as error:
        run(schema_conn, normalized_input={"value": bad})
    assert error.value.status == 400
    assert schema_conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0


def test_stale_guard_observes_actual_latest_revision(schema_conn):
    item = OpTypeService(schema_conn).create("OLD", "Old")
    repo = WorkbenchIdentityRepository(schema_conn)
    before = repo.find_active("op_type", item.op_type_id)
    OpTypeService(schema_conn).update(item.op_type_id, name="Changed elsewhere")

    def guard():
        latest = repo.get(before.ref)
        if latest.revision != before.revision:
            raise WorkbenchCommandRejected("stale_write", "数据已变化，请重新核对。")
        return latest

    with pytest.raises(WorkbenchCommandRejected, match="数据已变化"):
        run(schema_conn, guard=guard)
    assert OpTypeService(schema_conn).get("OLD").name == "Changed elsewhere"
    assert repo.find_active("op_type", INPUT["code"]) is None


def test_receipt_failure_rolls_back_nested_domain_and_identity(schema_conn, monkeypatch):
    service = WorkbenchCommandService(schema_conn)

    def unavailable(**_kwargs):
        raise OSError("fixture receipt storage unavailable")

    monkeypatch.setattr(service.repo, "insert", unavailable)
    with pytest.raises(WorkbenchCommandUncertain) as error:
        service.execute(request_key=KEY, action="op_type.create", context_ref="op_type.collection",
                        normalized_input=INPUT, guard=lambda: None, mutate=create(schema_conn))
    assert error.value.request_key == KEY and error.value.committed == "unknown"
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 0
    assert schema_conn.execute("SELECT COUNT(*) FROM WorkbenchEntityRefs").fetchone()[0] == 0
    assert service.lookup(KEY) is None and not schema_conn.in_transaction


@pytest.mark.parametrize("result", [None, WorkbenchCommandOutcome("accepted", {}),
                                    WorkbenchCommandOutcome("committed", {"bad": float("inf")})])
def test_invalid_result_rolls_back_domain_change(schema_conn, result):
    def mutate(context):
        create(schema_conn)(context)
        return result

    with pytest.raises(WorkbenchCommandUncertain):
        run(schema_conn, mutate=mutate)
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 0
    assert WorkbenchCommandService(schema_conn).lookup(KEY) is None


def test_cannot_claim_durable_result_inside_callers_transaction(schema_conn):
    with TransactionManager(schema_conn).transaction():
        with pytest.raises(RuntimeError, match="最外层事务"):
            run(schema_conn)
        assert schema_conn.in_transaction


class CommitFault:
    def __init__(self, conn, after):
        self.conn, self.after, self.once = conn, after, True

    def __getattr__(self, key):
        return getattr(self.conn, key)

    def commit(self):
        if not self.once:
            return self.conn.commit()
        self.once = False
        if self.after:
            self.conn.commit()
        raise sqlite3.OperationalError("fixture commit outcome unavailable")


@pytest.mark.parametrize("after", [False, True])
def test_commit_uncertainty_is_resolved_by_persisted_receipt(schema_conn, after):
    faulty = CommitFault(schema_conn, after)
    with pytest.raises(WorkbenchCommandUncertain) as error:
        run(faulty)
    assert error.value.committed == "unknown"
    observed = WorkbenchCommandService(schema_conn).lookup(KEY)
    assert bool(observed) is after
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == int(after)
    result = run(schema_conn)
    assert result["replayed"] is after
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 1


def test_parallel_same_intent_commits_once_and_survives_reconnect(tmp_path):
    db = tmp_path / "commands.db"
    with sqlite3.connect(str(db)) as conn:
        conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    barrier, mutations = Barrier(4), []

    def submit(_index):
        conn = sqlite3.connect(str(db), timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            barrier.wait(timeout=5)
            return run(conn, mutate=create(conn, mutations))
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert mutations == ["create"]
    assert sum(not result["replayed"] for result in results) == 1
    assert len({result["receipt_ref"] for result in results}) == 1
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        assert WorkbenchCommandService(conn).lookup(KEY)["receipt_ref"] == results[0]["receipt_ref"]
        assert conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1


def test_lookup_missing_receipt_is_readonly_not_a_claim_request_cannot_finish(schema_conn):
    service = WorkbenchCommandService(schema_conn)
    before = schema_conn.total_changes
    assert service.lookup(KEY) is None
    assert schema_conn.total_changes == before and not schema_conn.in_transaction

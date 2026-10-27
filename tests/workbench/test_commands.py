"""Ordinary command intent, nested domain transactions and uncertain commits."""


from datetime import date

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.content import same
from core.models.op_type import OpType
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.op_type_repo import OpTypeRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.write_context import issue_write_context, validate_write_context

KEY = "request-test-000000001"
INPUT = {"code": "TURN", "name": "Turning", "category": "internal"}


def create(conn, seen=None):
    def mutate(_context):
        if seen is not None:
            seen.append("create")
        with TransactionManager(conn).transaction():
            item = OpTypeRepository(conn).create(OpType(op_type_id=INPUT["code"], name=INPUT["name"], category="internal"))
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
    # Literal JSON marker dictionaries differ from the actual SQLite value type.
    assert not same(b"\x00", {"$sqlite_blob": "AA=="})
    assert not same(float("inf"), {"$sqlite_real": "inf"})
    assert not same(date(2026, 5, 1), {"storage_type": "date", "iso": "2026-05-01"})
    from flask import Flask
    with Flask("content-binding").app_context():
        raw = {"value": b"\x00", "date": date(2026, 5, 1)}
        context = issue_write_context("content-source", ["content.check"], raw)
        validate_write_context(context["write_token"], "content-source", "content.check", raw)
        read = bind_read_snapshot({"kind": "content-source"}, raw)
        assert bind_read_snapshot({"kind": "content-source"}, raw, read["snapshot_ref"]) == read
        with pytest.raises(WorkbenchCommandRejected):
            validate_write_context(context["write_token"], "content-source", "content.check",
                                   {"value": {"$sqlite_blob": "AA=="}, "date": date(2026, 5, 1)})
    row = WorkbenchCommandService(schema_conn).repo.get(KEY)
    assert row["input_json"] is not None
    with pytest.raises(WorkbenchCommandRejected) as changed:
        run(schema_conn, guard=expired, normalized_input={**INPUT, "name": "Another name"})
    assert changed.value.code == "request_key_conflict"
    # Every receipt stores its original intent; a corrupted one is a damaged archive and nothing is re-run.
    schema_conn.execute("UPDATE WorkbenchCommandReceipts SET input_json='{invalid' WHERE request_key=?", (KEY,))
    schema_conn.commit()
    before = schema_conn.total_changes
    with pytest.raises(WorkbenchCommandUncertain):
        run(schema_conn, guard=expired)
    assert schema_conn.total_changes == before


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


def test_response_counts_and_sends_the_same_strict_utf8_envelope(monkeypatch):
    from flask import Flask

    from web import api_responses

    encoded = []
    canonical = api_responses.canonical_json

    def encode(value):
        content = canonical(value)
        encoded.append(content)
        return content

    monkeypatch.setattr(api_responses, "canonical_json", encode)
    with Flask("actual-output-budget").app_context():
        data, snapshot = {"label": "加工中文"}, {"as_of": "2026-10-15T12:00:00"}
        response = api_responses.query_success(data, snapshot)
        actual_bytes = len(response.data)
        assert response.data == encoded[0].encode("utf-8") and "加工中文".encode() in response.data
        assert len(encoded) == 1
        exact = api_responses.query_success(data, snapshot, byte_limit=actual_bytes)
        assert len(exact.data) == actual_bytes and len(encoded) == 2
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            api_responses.query_success(data, snapshot, byte_limit=actual_bytes - 1)
        assert rejected.value.code == "query_too_large" and rejected.value.status == 413 and len(encoded) == 3
        with pytest.raises(ValueError):
            api_responses.query_success({"value": float("nan")}, snapshot)


def test_command_input_admission_keeps_json_types_and_returns_stored_shape(schema_conn):
    for value in (date(2026, 10, 15), b"raw", float("inf")):
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            run(schema_conn, normalized_input={"value": value})
        assert rejected.value.code == "invalid_input"
    first = run(schema_conn, mutate=lambda _: WorkbenchCommandOutcome("committed", {"values": (1, "中文")}))
    assert first["data"]["values"] == [1, "中文"]
    assert WorkbenchCommandService(schema_conn).lookup(KEY) == {**first, "replayed": True}


def test_token_clock_starts_under_the_registry_lock_and_preserves_receipt_replay(schema_conn, monkeypatch):
    from threading import Event, Thread
    from types import SimpleNamespace

    from flask import Flask

    from web import public_token_registry as tokens
    from web.routes.workbench.resource_action_context import PREVIEW_SCOPE, resolve_context, retain_context

    app, clock = Flask("token-lock-clock"), [1000.0]
    monkeypatch.setattr(tokens, "time", SimpleNamespace(time=lambda: clock[0]))
    original_lock, attempting = tokens._LOCK, Event()

    class ObservedLock:
        def __enter__(self):
            attempting.set()
            original_lock.acquire()

        def __exit__(self, *args):
            original_lock.release()

    def wait_across_clock(operation, before, after):
        result = {}

        def worker():
            with app.app_context():
                try:
                    result["value"] = operation()
                except Exception as exc:
                    result["error"] = exc

        attempting.clear()
        clock[0] = before
        # Keep the real registry lock held until this worker tries to acquire it.
        with original_lock:
            thread = Thread(target=worker)
            thread.start()
            assert attempting.wait(5)
            clock[0] = after
        thread.join(5)
        assert not thread.is_alive()
        return result

    with app.app_context():
        ref, _ = retain_context(PREVIEW_SCOPE, "pending-preview")
        issuer = tokens.PublicTokenIssuer("token-lock-reissue", ttl_seconds=100)
        original, original_expiry = issuer.issue_with_expiry("value")
    monkeypatch.setattr(tokens, "_LOCK", ObservedLock())
    renewed = wait_across_clock(lambda: issuer.issue_with_expiry("value"), 1040.0, 1060.0)
    assert renewed["value"][0] != original
    assert original_expiry == 1100.0 and renewed["value"][1] == 1160.0

    intent = {"context_ref": ref, "normalized_input": {"preview_ref": ref},
              "guard": lambda: resolve_context(PREVIEW_SCOPE, ref, "stale_write")}
    changes = schema_conn.total_changes
    rejected = wait_across_clock(lambda: run(schema_conn, **intent), 1899.0, 1901.0)
    assert isinstance(rejected.get("error"), WorkbenchCommandRejected)
    assert rejected["error"].code == "stale_write" and rejected["error"].status == 409
    assert schema_conn.total_changes == changes
    assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 0
    assert WorkbenchCommandService(schema_conn).lookup(KEY) is None

    with app.app_context():
        fresh, _ = retain_context(PREVIEW_SCOPE, "pending-preview")
        intent.update(context_ref=fresh, normalized_input={"preview_ref": fresh},
                      guard=lambda: resolve_context(PREVIEW_SCOPE, fresh, "stale_write"))
        first = run(schema_conn, **intent)
        clock[0] = 2802.0
        with pytest.raises(WorkbenchCommandRejected, match="预检结果已过期"):
            intent["guard"]()
        assert run(schema_conn, **intent) == {**first, "replayed": True}
        assert schema_conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 1

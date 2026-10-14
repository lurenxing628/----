"""Ordinary command intent, nested domain transactions and uncertain commits."""


from datetime import date

import pytest

from core.models.content import same
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.process.op_type_service import OpTypeService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.write_context import issue_write_context, validate_write_context

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


def test_one_intent_replays_exact_result_before_expired_guard(schema_conn, monkeypatch):
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
    assert row["input_hash"] is None and row["input_json"] is not None
    with pytest.raises(WorkbenchCommandRejected) as changed:
        run(schema_conn, guard=expired, normalized_input={**INPUT, "name": "Another name"})
    assert changed.value.code == "request_key_conflict"
    # A real old hash-only receipt retains its result; missing intent stops before guard.
    schema_conn.execute("UPDATE WorkbenchCommandReceipts SET input_json=NULL,input_hash=? WHERE request_key=?",
                        ("a" * 64, KEY))
    schema_conn.commit()
    legacy = WorkbenchCommandService(schema_conn)
    assert legacy.lookup(KEY) == second
    before = schema_conn.total_changes
    with pytest.raises(WorkbenchCommandRejected) as missing:
        run(schema_conn, guard=expired)
    assert missing.value.code == "command_original_input_missing"
    assert schema_conn.total_changes == before
    # A malformed outer document is a stored-format error, not a missing intent.
    monkeypatch.setattr(legacy.repo, "fetchone", lambda _sql, _params: {"admission_json": "[]"})
    with pytest.raises(ValueError, match="已保存的试调受理资料结构不完整"):
        legacy.repo.input_content({"input_json": None, "action": "trial.create", "request_key": KEY})


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

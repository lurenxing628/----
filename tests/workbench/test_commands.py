"""Ordinary command intent, nested domain transactions and uncertain commits."""


import pytest

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandUncertain
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

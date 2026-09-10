"""The edit-context/command integration uses a bare Flask app and a fixture DB."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask

import web.public_token_registry as registry
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.process.op_type_service import OpTypeService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from web.routes.workbench.write_context import issue_write_context, validate_write_context


@pytest.fixture
def context_app(monkeypatch):
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(registry, "time", SimpleNamespace(time=lambda: clock["now"]))
    with Flask(__name__).app_context():
        yield clock


def test_repeated_issuance_reports_real_reused_expiry_without_growing_store(context_app):
    snapshot = {"revision": 7, "related": ["a", "b"]}
    first = issue_write_context("entity-ref", ["update", "delete"], snapshot)
    assert first["expires_at"] == datetime.fromtimestamp(context_app["now"] + 900).isoformat(timespec="seconds")
    context_app["now"] += 100
    for _ in range(30):
        again = issue_write_context("entity-ref", ["delete", "update", "update"], snapshot)
        assert again == first
    assert set(first) == {"write_token", "expires_at", "capabilities", "blocked_reasons"}
    assert snapshot["revision"] == 7
    validate_write_context(first["write_token"], "entity-ref", "update", snapshot)
    assert len(registry._scope_state("workbench-write-v1")["tokens"]) == 1


@pytest.mark.parametrize("subject,action,state", [
    ("another-ref", "update", {"revision": 1}),
    ("entity-ref", "delete", {"revision": 1}),
    ("entity-ref", "update", {"revision": 2}),
])
def test_wrong_object_action_or_revision_cannot_save(context_app, subject, action, state):
    context = issue_write_context("entity-ref", ["update"], {"revision": 1})
    with pytest.raises(WorkbenchCommandRejected) as error:
        validate_write_context(context["write_token"], subject, action, state)
    assert error.value.code == "stale_write" and error.value.committed is False


def test_expiry_and_restart_reject_without_issuing_a_replacement(context_app):
    context = issue_write_context("entity-ref", ["update"], 1)
    context_app["now"] += 901
    with pytest.raises(WorkbenchCommandRejected):
        validate_write_context(context["write_token"], "entity-ref", "update", 1)
    assert not registry._scope_state("workbench-write-v1")["tokens"]
    fresh = issue_write_context("entity-ref", ["update"], 1)
    with Flask("restarted-fixture").app_context():
        with pytest.raises(WorkbenchCommandRejected):
            validate_write_context(fresh["write_token"], "entity-ref", "update", 1)
        assert not registry._scope_state("workbench-write-v1")["tokens"]


@pytest.mark.parametrize("body", ['{"version":1,"source":"demo"}', '[]', '{bad', '{}'])
def test_malformed_or_demo_binding_never_authorizes(context_app, body):
    token = registry.issue_public_token("workbench-write-v1", body)
    with pytest.raises(WorkbenchCommandRejected):
        validate_write_context(token, "entity-ref", "update", {})


@pytest.mark.parametrize("subject,actions", [("", ["update"]), ("ref", []), ("ref", "update"), ("ref", [None])])
def test_invalid_issuance_context_is_rejected(context_app, subject, actions):
    with pytest.raises(ValueError):
        issue_write_context(subject, actions, {})


def test_guard_reads_current_db_and_committed_replay_survives_old_context_expiry(context_app, schema_conn):
    domain = OpTypeService(schema_conn)
    domain.create("OT-CONTEXT", "Before")
    identities = WorkbenchIdentityRepository(schema_conn)
    original = identities.find_active("op_type", "OT-CONTEXT")
    assert original is not None
    context = issue_write_context(original.ref, ["op_type.update"], {"revision": original.revision})
    seen = []

    def guard():
        assert schema_conn.in_transaction
        latest = identities.get(original.ref)
        validate_write_context(context["write_token"], original.ref, "op_type.update", {"revision": latest.revision})
        return latest

    def mutate(identity):
        seen.append("update")
        row = domain.update(identity.entity_key, name="After")
        return WorkbenchCommandOutcome("committed", {"ref": identity.ref, "name": row.name})

    command = WorkbenchCommandService(schema_conn)
    args = {"request_key": "guard-request-000001", "action": "op_type.update", "context_ref": original.ref,
            "normalized_input": {"name": "After"}, "guard": guard, "mutate": mutate}
    saved = command.execute(**args)
    assert saved["data"]["name"] == "After"
    with pytest.raises(WorkbenchCommandRejected):
        command.execute(**{**args, "request_key": "guard-request-000002"})
    context_app["now"] += 901
    assert command.execute(**args) == {**saved, "replayed": True}
    assert seen == ["update"]
    assert identities.get(original.ref).revision == original.revision + 1

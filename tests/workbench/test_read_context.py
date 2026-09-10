"""Read-scope tokens retain fingerprints, not large column selections."""

import json
from types import SimpleNamespace

import pytest
from flask import Flask

import web.public_token_registry as registry
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from web.routes.workbench.read_context import bind_read_snapshot

SCOPE = "workbench-read-v1"


@pytest.fixture
def context_clock(monkeypatch):
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(registry, "time", SimpleNamespace(time=lambda: clock["now"]))
    with Flask(__name__).app_context():
        yield clock


def test_large_column_selection_keeps_registry_payload_small(context_clock):
    scope = {"kind": "material", "column_filters": {"spec": {
        "mode": "include", "values": [format(index, "064x") for index in range(50000)]}}}
    result = bind_read_snapshot(scope, "facts")
    raw = registry.resolve_public_token(SCOPE, result["snapshot_ref"], message="missing fixture token", field="snapshot_ref")
    assert len(raw.encode("utf-8")) < 300
    payload = json.loads(raw)
    assert payload["version"] == 2 and "scope" not in payload
    assert bind_read_snapshot(scope, "facts", result["snapshot_ref"]) == result
    scope["column_filters"]["spec"]["values"].pop()
    with pytest.raises(WorkbenchCommandRejected) as failure:
        bind_read_snapshot(scope, "facts", result["snapshot_ref"])
    assert failure.value.code == "snapshot_stale"
    assert len(registry._scope_state(SCOPE)["tokens"]) == 1


def test_v1_live_scope_is_supported_without_issuing_replacement(context_clock):
    scope = {"kind": "material", "query": "old", "size": 20}
    payload = {"version": 1, "source": "production", "scope": scope,
               "fingerprint": "facts", "as_of": "2026-09-09T08:00:00"}
    token = registry.issue_public_token(SCOPE, canonical_json(payload), ttl_seconds=900)
    assert bind_read_snapshot(scope, "facts", token) == {"snapshot_ref": token, "as_of": payload["as_of"]}
    assert len(registry._scope_state(SCOPE)["tokens"]) == 1
    with pytest.raises(WorkbenchCommandRejected):
        bind_read_snapshot({**scope, "query": "other"}, "facts", token)


@pytest.mark.parametrize("changed", ["kind", "query", "size", "sort", "direction", "column_filters"])
def test_v2_rejects_any_changed_scope_dimension(context_clock, changed):
    scope = {"kind": "material", "query": "", "size": 20, "sort": "business_code", "direction": "asc",
             "column_filters": {"spec": {"mode": "include", "values": ["a" * 64]}}}
    token = bind_read_snapshot(scope, "facts")["snapshot_ref"]
    with pytest.raises(WorkbenchCommandRejected):
        bind_read_snapshot({**scope, changed: "changed"}, "facts", token)
    with pytest.raises(WorkbenchCommandRejected):
        bind_read_snapshot(scope, "changed-facts", token)


@pytest.mark.parametrize("body", ["[]", "{bad", "{}", '{"version":true,"source":"production"}',
                                '{"version":2,"source":"demo","scope_hash":"x"}',
                                '{"version":3,"source":"production","scope_hash":"x"}'])
def test_unknown_or_malformed_bindings_do_not_become_fresh_reads(context_clock, body):
    token = registry.issue_public_token(SCOPE, body)
    with pytest.raises(WorkbenchCommandRejected):
        bind_read_snapshot({}, "facts", token)


def test_expiry_and_restart_fail_without_automatic_new_scope(context_clock):
    token = bind_read_snapshot({}, "facts")["snapshot_ref"]
    context_clock["now"] += 901
    with pytest.raises(WorkbenchCommandRejected):
        bind_read_snapshot({}, "facts", token)
    token = bind_read_snapshot({}, "facts")["snapshot_ref"]
    with Flask("fresh-read-fixture").app_context():
        with pytest.raises(WorkbenchCommandRejected):
            bind_read_snapshot({}, "facts", token)
        assert not registry._scope_state(SCOPE)["tokens"]

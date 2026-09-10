"""Real command transactions, immutable previews and receipt-first recovery."""

import json
from copy import deepcopy

import pytest

from core.services.process.part_service import PartService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.process_collection_api_support import (
    BASE,
    COLLECTION,
    CREATE,
    LIST,
    collection_api_fixture,
    expire,
    rejected,
    seed_table_rows,
    success,
)
from web.routes.workbench.resource_action_context import EXTENSION

_fixture = collection_api_fixture
ACTIONS = ("create", "bulk-confirm")


def intent(api, action):
    return api.create_body() if action == "create" else api.delete_body()


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("change", ("unknown", "expired", "wrong_subject", "wrong_action"))
def test_write_tokens_are_bound_to_the_exact_subject_action_and_expiry(collection_api, action, change):
    api = collection_api
    body = intent(api, action)
    if change == "unknown":
        body["write_token"] = "x" * 32
    elif change == "expired":
        expire(api, "workbench-write-v1", body["write_token"])
    else:
        registry = api.client.application.extensions["aps_public_opaque_tokens"]
        entry = registry["workbench-write-v1"]["tokens"][body["write_token"]]
        binding = json.loads(entry["value"])
        if change == "wrong_subject":
            binding["subject_ref"] = "different-subject"
        else:
            binding["actions"] = ["process.hours_confirm"]
        # A real token with a different binding must also be rejected.
        from web.public_token_registry import issue_public_token
        with api.client.application.app_context():
            body["write_token"] = issue_public_token("workbench-write-v1", json.dumps(binding))
    before = api.snapshot()
    rejected(api.send(action, body), "stale_write")
    assert api.snapshot() == before


@pytest.mark.parametrize("change", ("expired", "missing_document", "unknown_ref", "other_preview"))
def test_delete_cannot_confirm_missing_or_swapped_server_preview(collection_api, change):
    api = collection_api
    body = api.delete_body()
    if change == "expired":
        expire(api, "workbench-process-action-preview-v1", body["input"]["preview_ref"])
    elif change == "missing_document":
        api.client.application.extensions[EXTENSION].clear()
    elif change == "unknown_ref":
        body["input"]["preview_ref"] = "x" * 32
    else:
        other = api.delete_body([api.ref(code="PROC-004")])
        body["input"]["preview_ref"] = other["input"]["preview_ref"]
    before = api.snapshot()
    rejected(api.send("bulk-confirm", body), "stale_write")
    assert api.snapshot() == before


@pytest.mark.parametrize("field,value", [("refs", []), ("scope", {}), ("rows", []), ("summary", {"rejected": 0}),
    ("can_confirm", True), ("commit_policy", "partial")])
def test_client_cannot_replace_retained_preview_facts(collection_api, field, value):
    api = collection_api
    body = api.delete_body()
    body["input"][field] = value
    before = api.snapshot()
    rejected(api.send("bulk-confirm", body), "invalid_input", 400)
    assert api.snapshot() == before


@pytest.mark.parametrize("sql", [
    "UPDATE Parts SET remark='edited' WHERE part_no='PROC-003'",
    "UPDATE PartOperations SET setup_hours=9 WHERE part_no='PROC-003'",
    "UPDATE PartOperations SET status='deleted' WHERE part_no='PROC-003'",
    "INSERT INTO Batches(batch_id,part_no,quantity,due_date) VALUES ('NEW-USE','PROC-003',1,'2026-10-01')",
    "UPDATE Parts SET private_collection_note=X'0102' WHERE part_no='PROC-003'",
])
def test_selected_facts_changed_after_preview_abort_all_deletes(collection_api, sql):
    api = collection_api
    api.execute("ALTER TABLE Parts ADD COLUMN private_collection_note BLOB")
    body = api.delete_body()
    api.execute(sql)
    before = api.snapshot()
    rejected(api.send("bulk-confirm", body), "stale_write")
    assert api.snapshot() == before


def test_delete_recreate_same_code_rejects_old_preview_and_does_not_touch_new_identity(collection_api):
    api = collection_api
    old_ref = api.ref(code="PROC-003")
    body = api.delete_body()
    api.execute("DELETE FROM Parts WHERE part_no='PROC-003'")
    api.execute("INSERT INTO Parts(part_no,part_name) VALUES ('PROC-003','replacement')")
    new_ref = api.ref(code="PROC-003")
    assert new_ref != old_ref
    before = api.snapshot()
    rejected(api.send("bulk-confirm", body), "stale_write")
    rejected(api.client.get(LIST + "/" + old_ref), "entity_not_found", 404)
    assert success(api.client.get(LIST + "/" + new_ref))["data"]["label"] == "replacement"
    assert api.snapshot() == before


@pytest.mark.parametrize("sql", ["UPDATE Parts SET remark='changed' WHERE part_no='PROC-002'",
    "UPDATE OpTypes SET name='Changed catalog' WHERE op_type_id='PROC-IN'",
    "INSERT INTO Parts(part_no,part_name) VALUES ('AFTER-CONTEXT','new row')"])
def test_create_rechecks_current_database_under_write_context(collection_api, sql):
    api = collection_api
    body = api.create_body()
    api.execute(sql)
    before = api.snapshot()
    rejected(api.send("create", body), "stale_write")
    assert api.snapshot() == before


def test_duplicate_create_is_domain_conflict_without_new_rows_or_receipt(collection_api):
    api = collection_api
    body = api.create_body({**CREATE, "business_code": " PROC-001 "})
    before = api.snapshot()
    rejected(api.send("create", body), "constraint_conflict")
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS)
def test_receipt_replay_survives_lost_contexts_but_changed_intent_conflicts(collection_api, action):
    api = collection_api
    body = intent(api, action)
    first = success(api.send(action, body))
    api.execute("UPDATE Parts SET remark='after commit' WHERE part_no='PROC-001'")
    api.client.application.extensions["aps_public_opaque_tokens"].clear()
    if EXTENSION in api.client.application.extensions:
        api.client.application.extensions[EXTENSION].clear()
    before = api.snapshot()
    body["write_token"] = "expired-or-lost"
    second = success(api.send(action, body))
    assert second == {**first, "replayed": True}
    assert success(api.client.get(BASE + "/commands/" + body["request_key"])) == second
    changed = deepcopy(body)
    changed["input"]["label" if action == "create" else "preview_ref"] = "changed-intent"
    rejected(api.send(action, changed), "request_key_conflict")
    assert api.snapshot() == before and len(api.rows("WorkbenchCommandReceipts")) == 1


def test_replayed_delete_does_not_delete_same_code_replacement(collection_api):
    api = collection_api
    old_ref = api.ref(code="PROC-002")
    body = api.delete_body([old_ref])
    first = success(api.send("bulk-confirm", body))
    created = success(api.send("create", api.create_body({"business_code": "PROC-002", "label": "replacement"})))
    assert created["data"]["entity_ref"] != old_ref
    before = api.snapshot()
    assert success(api.send("bulk-confirm", body)) == {**first, "replayed": True}
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("failure", ("business", "receipt"))
def test_mutation_or_receipt_failure_rolls_back_every_table_and_retry_has_one_receipt(collection_api, monkeypatch, action, failure):
    api = collection_api
    body = intent(api, action)
    owner, name = (WorkbenchCommandRepository, "insert") if failure == "receipt" else (
        PartService, "update" if action == "create" else "delete")
    original = getattr(owner, name)
    touched = []

    def fail_after(*args, **kwargs):
        result = original(*args, **kwargs)
        touched.append(True)
        if action == "create" or failure == "receipt" or len(touched) == 2:
            raise OSError("injected failure after real database mutation")
        return result

    before = api.snapshot()
    with monkeypatch.context() as patch:
        patch.setattr(owner, name, fail_after)
        error = rejected(api.send(action, body), "storage_failure", 500, committed="unknown")["error"]
    assert len(touched) == (2 if action == "bulk-confirm" and failure == "business" else 1)
    assert api.snapshot() == before
    assert error["request_key"] == body["request_key"]
    lookup = success(api.client.get(error["result_target"]))
    assert lookup["state"] == "not_recorded" and lookup["may_be_in_flight"] is True
    first = success(api.send(action, body))
    assert success(api.send(action, body)) == {**first, "replayed": True}
    assert len(api.rows("WorkbenchCommandReceipts")) == 1


def test_create_workflow_failure_rolls_back_part_identity_and_workflow(collection_api, monkeypatch):
    import core.services.workbench.process_part_actions as actions

    api = collection_api
    body = api.create_body()
    original = actions.start_workflow
    touched = []

    def broken(*args, **kwargs):
        original(*args, **kwargs)
        touched.append(True)
        raise RuntimeError("workflow failure after real insert")

    before = api.snapshot()
    with monkeypatch.context() as patch:
        patch.setattr(actions, "start_workflow", broken)
        rejected(api.send("create", body), "storage_failure", 500)
    assert touched == [True] and api.snapshot() == before
    success(api.send("create", body))


@pytest.mark.parametrize("action", ACTIONS)
def test_response_loss_after_commit_recovers_original_receipt_without_second_write(collection_api, monkeypatch, action):
    api = collection_api
    body = intent(api, action)
    original = WorkbenchCommandService.execute

    def lose_response(self, **kwargs):
        original(self, **kwargs)
        raise OSError("response lost after committed transaction")

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandService, "execute", lose_response)
        error = rejected(api.send(action, body), "storage_failure", 500, committed="unknown")["error"]
    before = api.snapshot()
    receipt = success(api.client.get(error["result_target"]))
    assert receipt["result"] == "committed" and receipt["replayed"] is True
    assert success(api.send(action, body)) == receipt
    assert api.snapshot() == before and len(api.rows("WorkbenchCommandReceipts")) == 1


@pytest.mark.parametrize("action,limit", [("create", 1024 ** 2), ("bulk-preview", 4 * 1024 ** 2), ("bulk-confirm", 4 * 1024 ** 2)])
def test_payload_limits_are_explicit_not_truncated(collection_api, action, limit):
    before = collection_api.snapshot()
    response = collection_api.client.post(COLLECTION + action, data=" " * (limit + 1), content_type="application/json")
    rejected(response, "capacity_exceeded", 413)
    assert collection_api.snapshot() == before


def test_full_explicit_collection_beyond_page_cap_is_deleted_once_in_order(collection_api):
    api = collection_api
    codes = seed_table_rows(api, 257)
    refs = [api.ref(code=code) for code in reversed(codes)]
    body = api.delete_body(refs, {"query": "not in view", "sort": []}, size=1)
    before = api.snapshot()
    result = success(api.send("bulk-confirm", body))
    assert result["data"]["deleted_count"] == 257
    assert [row["entity_ref"] for row in result["data"]["rows"]] == refs
    assert {row["part_no"] for row in api.rows("Parts")} == {"PROC-001", "PROC-002", "PROC-003", "PROC-004", "PROC-%_"}
    for table in ("Batches", "BatchOperations", "Schedule", "ExternalGroups", "WorkbenchProcessWorkflow"):
        assert api.snapshot()[1][table] == before[1][table]

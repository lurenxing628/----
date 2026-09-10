"""Atomic explicit-ref bulk deletion with complete, immutable preflight evidence."""

from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain, canonical_json
from core.services.material.material_service import MaterialService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.material_bulk import WorkbenchMaterialBulkService
from core.services.workbench.materials import WorkbenchMaterialService
from tests.workbench.identity_metadata_support import business_snapshot, table_rows
from tests.workbench.material_file_support import KEY, confirm_delete, measure, seed_many
from tests.workbench.material_support import identity_for, material_database, material_row, stored_state


@pytest.fixture
def selected(material_conn):
    service = MaterialService(material_conn)
    service.create("MAT2", "free 2")
    service.create("MAT3", "free 3")
    return [identity_for(material_conn, code).ref for code in ("MAT2", "MAT3")]


def test_preview_is_frozen_readonly_complete_and_includes_hidden_selection(material_conn, selected):
    service = WorkbenchMaterialBulkService(material_conn)
    refs = selected + [identity_for(material_conn).ref]
    before, changes = stored_state(material_conn), material_conn.total_changes
    preview = service.preview_delete(refs, scope={"query": "MAT2"})
    body = preview.as_dict()
    assert [row["entity_ref"] for row in body["rows"]] == refs
    assert [row["result"] for row in body["rows"]] == ["delete", "delete", "rejected"]
    assert body["rows"][2]["expected"]["requirements"][0]["available_qty"] == 4.25
    assert body["rows"][2]["errors"][0]["row"] == 3
    assert body["commit_policy"] == "atomic" and canonical_json(body) == preview.document
    body["rows"][0]["input"]["label"] = "detached mutation"
    assert preview.as_dict()["rows"][0]["input"] == {}
    with pytest.raises(FrozenInstanceError):
        preview.document = "modified"
    assert stored_state(material_conn) == before and material_conn.total_changes == changes
    assert not material_conn.in_transaction


@pytest.mark.parametrize("bad", [None, "MAT1", [], (), ["MAT1"], [True], [None], ["x" * 48]])
def test_invalid_or_implicit_selections_are_rejected_without_reads(material_conn, bad):
    before = stored_state(material_conn)
    with pytest.raises(ValidationError):
        WorkbenchMaterialBulkService(material_conn).preview_delete(bad, scope={})
    assert stored_state(material_conn) == before


def test_duplicate_ref_and_foreign_kind_never_delete(material_conn, selected):
    service = WorkbenchMaterialBulkService(material_conn)
    with pytest.raises(ValidationError, match="重复"):
        service.preview_delete([selected[0], selected[0]], scope={})
    machine_ref = material_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind = 'machine'").fetchone()[0]
    preview = service.preview_delete([machine_ref], scope={})
    assert preview.as_dict()["rows"][0]["errors"][0]["code"] == "entity_not_found"
    with pytest.raises(WorkbenchCommandRejected):
        confirm_delete(material_conn, preview, [machine_ref])


def test_success_uses_adapter_preserves_batch_facts_and_stable_receipt(material_conn, selected):
    service = WorkbenchMaterialBulkService(material_conn)
    preview = service.preview_delete(selected, scope={})
    before = business_snapshot(material_conn)
    with patch.object(WorkbenchMaterialService, "apply", autospec=True, side_effect=WorkbenchMaterialService.apply) as apply:
        result = confirm_delete(material_conn, preview, selected)
    assert apply.call_count == 2 and result["data"]["deleted_count"] == 2
    assert result["result"] == "committed"
    assert [row["entity_ref"] for row in result["data"]["rows"]] == selected
    assert all(set(row) == {"row", "result", "entity_ref", "business_code"} for row in result["data"]["rows"])
    after = business_snapshot(material_conn)
    assert {k: v for k, v in after.items() if k != "Materials"} == {k: v for k, v in before.items() if k != "Materials"}
    assert material_row(material_conn, "MAT2") is None and material_row(material_conn, "MAT3") is None


def test_reference_rejection_preflights_entire_selection_before_any_delete(material_conn, selected):
    refs = selected + [identity_for(material_conn).ref]
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(refs, scope={})
    before = stored_state(material_conn)
    with patch.object(WorkbenchMaterialService, "apply", side_effect=AssertionError("must preflight every row first")):
        with pytest.raises(WorkbenchCommandRejected) as error:
            confirm_delete(material_conn, preview, refs)
    assert error.value.code == "constraint_conflict" and stored_state(material_conn) == before


@pytest.mark.parametrize("change", ("update", "recreate", "reference", "hidden"))
def test_any_selected_fact_change_is_stale_and_keeps_earlier_rows(material_conn, selected, change):
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(selected, scope={})
    domain = MaterialService(material_conn)
    if change == "update":
        domain.update("MAT3", name="concurrent edit")
    elif change == "recreate":
        domain.delete("MAT3")
        domain.create("MAT3", "same code new instance")
    elif change == "reference":
        material_conn.execute("INSERT INTO BatchMaterials (batch_id, material_id, required_qty) VALUES ('B1', 'MAT3', 2)")
        material_conn.commit()
    else:
        material_conn.execute("UPDATE Materials SET created_at = '2001-01-01' WHERE material_id = 'MAT3'")
        material_conn.commit()
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        confirm_delete(material_conn, preview, selected)
    assert error.value.code == "stale_write" and stored_state(material_conn) == before


def test_reference_content_change_without_count_change_is_stale(material_conn, selected):
    refs = selected + [identity_for(material_conn).ref]
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(refs, scope={})
    material_conn.execute("UPDATE BatchMaterials SET available_qty = 19, ready_status = 'yes' WHERE material_id = 'MAT1'")
    material_conn.commit()
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        confirm_delete(material_conn, preview, refs)
    assert error.value.code == "stale_write" and stored_state(material_conn) == before


@pytest.mark.parametrize("change", ("order", "selection", "scope", "invalid", "preview"))
def test_confirm_rejects_changed_request_or_approved_preview(material_conn, selected, change):
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(selected, scope={})
    refs, scope = selected, {}
    if change == "order":
        refs = list(reversed(selected))
    elif change == "selection":
        refs = selected[:1]
    elif change == "scope":
        scope = {"query": "another filter"}
    elif change == "invalid":
        refs = ["MAT2"]
    else:
        data = preview.as_dict()
        data["rows"][0]["expected"]["material"]["name"] = "not approved"
        preview = replace(preview, document=canonical_json(data))
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        confirm_delete(material_conn, preview, refs, scope=scope)
    assert error.value.code == "stale_write" and stored_state(material_conn) == before


def test_no_outer_transaction_and_late_failure_cannot_leave_partial_batch(material_conn, selected):
    service = WorkbenchMaterialBulkService(material_conn)
    preview = service.preview_delete(selected, scope={})
    with pytest.raises(RuntimeError, match="外层"):
        service.confirm_delete(preview, selected, scope={})
    original = service.adapter.apply

    def fail_second(action, normalized, identity):
        result = original(action, normalized, identity)
        if identity.ref == selected[1]:
            raise RuntimeError("fixture domain failure after second delete")
        return result

    before = stored_state(material_conn)
    with patch.object(service.adapter, "apply", side_effect=fail_second):
        with TransactionManager(material_conn).transaction(begin_immediate=True):
            with pytest.raises(RuntimeError, match="fixture domain failure"):
                service.confirm_delete(preview, selected, scope={})
            assert stored_state(material_conn) == before
    assert stored_state(material_conn) == before


def test_receipt_failure_rolls_back_all_deletes_and_tombstones(material_conn, selected, monkeypatch):
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(selected, scope={})
    command = WorkbenchCommandService(material_conn)
    before = stored_state(material_conn)
    monkeypatch.setattr(command.repo, "insert", lambda **_: (_ for _ in ()).throw(OSError("fixture receipt failure")))
    with pytest.raises(WorkbenchCommandUncertain):
        confirm_delete(material_conn, preview, selected, command=command)
    assert stored_state(material_conn) == before


def test_deleted_batch_receipt_replays_before_expired_preview_guard(material_conn, selected):
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(selected, scope={})
    first = confirm_delete(material_conn, preview, selected)
    MaterialService(material_conn).create("MAT2", "recreated")
    before = stored_state(material_conn)
    second = confirm_delete(material_conn, preview, selected, guard=lambda: pytest.fail("committed intent must replay first"))
    assert second == {**first, "replayed": True}
    assert WorkbenchCommandService(material_conn).lookup(KEY) == second and stored_state(material_conn) == before


def test_10000_refs_preview_and_confirmation_are_complete(material_conn):
    seed_many(material_conn, 10000)
    refs = [row[0] for row in material_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind = 'material' AND entity_key LIKE 'BULK%' ORDER BY entity_key")]
    service = WorkbenchMaterialBulkService(material_conn)
    before = business_snapshot(material_conn)
    unselected = material_row(material_conn)
    preview = measure("bulk_preview", lambda: service.preview_delete(refs, scope={}), rows=10000)
    assert preview.as_dict()["summary"]["delete"] == 10000
    assert [row["entity_ref"] for row in preview.as_dict()["rows"]] == refs
    result = measure("bulk_confirm", lambda: confirm_delete(material_conn, preview, refs), rows=10000)
    assert result["data"]["deleted_count"] == 10000
    assert [row["entity_ref"] for row in result["data"]["rows"]] == refs
    assert len(table_rows(material_conn, "Materials")) == 1 and material_row(material_conn) == unselected
    after = business_snapshot(material_conn)
    assert {k: v for k, v in after.items() if k != "Materials"} == {k: v for k, v in before.items() if k != "Materials"}


@pytest.mark.parametrize("failure", ("last_delete", "receipt"))
def test_2501_deletes_roll_back_all_rows_revisions_and_receipt(material_conn, monkeypatch, failure):
    seed_many(material_conn, 2501)
    refs = [row[0] for row in material_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind = 'material' AND entity_key LIKE 'BULK%' ORDER BY entity_key")]
    preview = WorkbenchMaterialBulkService(material_conn).preview_delete(refs, scope={})
    command = WorkbenchCommandService(material_conn)
    before, seen = stored_state(material_conn), []
    original_apply, original_insert = WorkbenchMaterialService.apply, command.repo.insert

    def mutate(adapter, action, normalized, identity):
        outcome = original_apply(adapter, action, normalized, identity)
        seen.append(identity.ref)
        if len(seen) == len(refs) and failure == "last_delete":
            raise RuntimeError("fixture failure after delete 2501")
        return outcome

    def receipt(**kwargs):
        original_insert(**kwargs)
        raise OSError("fixture receipt failure after insert")

    monkeypatch.setattr(WorkbenchMaterialService, "apply", mutate)
    if failure == "receipt":
        monkeypatch.setattr(command.repo, "insert", receipt)
    with pytest.raises(WorkbenchCommandUncertain):
        confirm_delete(material_conn, preview, refs, command=command)
    assert seen == refs and stored_state(material_conn) == before

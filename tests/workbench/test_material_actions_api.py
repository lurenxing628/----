"""Material action HTTP contracts against new temporary Flask/SQLite databases."""

import csv
import json
from io import BytesIO, StringIO

import pytest
from werkzeug.datastructures import MultiDict

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.material_bulk import WorkbenchMaterialBulkService
from core.services.workbench.material_files import WorkbenchMaterialFileService
from core.services.workbench.materials import WorkbenchMaterialService
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.material_actions_api_support import (
    BASE,
    assert_failure,
    bulk_preview,
    check_download,
    command_body,
    confirm,
    database,
    download,
    expire_contexts,
    export_preview,
    import_preview,
    list_context,
    register_actions,
    seed,
    snapshot,
    upload,
    without_startup_logs,
)
from tests.workbench.material_actions_api_support import material_actions_client as _material_actions_client
from tests.workbench.material_file_support import file_bytes

material_actions_client = _material_actions_client


@pytest.mark.parametrize("operation", ("bulk", "import"))
@pytest.mark.parametrize("stored,local", (("2026-09-15 15:16:13", "2026-09-15 23:16:13"),
                                         ("2026-09-15 19:05:07", "2026-09-16 03:05:07"), (None, None)))
def test_preview_times_match_export_without_changing_original_facts(material_actions_client, operation, stored, local):
    client = material_actions_client
    refs = seed(client, 1)
    with database(client) as conn:
        conn.execute("UPDATE Materials SET created_at=?", (stored,))
        conn.commit()
    original = snapshot(client)
    preview = (bulk_preview(client, [refs["MAT00000"]]) if operation == "bulk"
               else import_preview(client, [["MAT00000", "改名"]]))
    row = preview["rows"][0]
    assert row["before"]["created_at"] == local
    assert row["after"] is None if operation == "bulk" else row["after"]["created_at"] == local
    assert "created_at" not in row["changes"]
    with client.application.app_context():
        retained = list(client.application.extensions["workbench_material_previews_v1"].values())
        assert len(retained) == 1
        canonical = retained[0].preview.document
        assert retained[0].preview.as_dict()["rows"][0]["expected"]["material"]["created_at"] == stored
        from web.routes.workbench.material_actions_context import public_row
        public_row(retained[0].preview.as_dict()["rows"][0])
        assert retained[0].preview.document == canonical
    downloaded = download(client, export_preview(client, "all"), "csv")
    assert downloaded.status_code == 200
    cells = list(csv.reader(StringIO(downloaded.data.decode("utf-8-sig"))))
    assert cells[1][cells[0].index("创建时间")] == ("'" + local if local is not None else "")
    assert snapshot(client) == original
    assert confirm(client, preview).status_code == 200
    if operation == "import":
        with database(client) as conn:
            saved = conn.execute("SELECT name,created_at FROM Materials WHERE material_id='MAT00000'").fetchone()
            assert tuple(saved) == ("改名", stored)


@pytest.mark.parametrize("operation", ("bulk", "import"))
def test_invalid_stored_preview_time_is_explicit_error_without_writes(material_actions_client, operation):
    client = material_actions_client
    refs = seed(client, 1)
    with database(client) as conn:
        conn.execute("UPDATE Materials SET created_at='invalid stored time'")
        conn.commit()
    before = snapshot(client)
    response = (client.post(BASE + "/entities/material/bulk-preview", json={"action": "delete",
                "refs": [refs["MAT00000"]], **list_context(client)}) if operation == "bulk"
                else upload(client, file_bytes([["MAT00000", "改名"]], "csv", headers=("物料编号", "名称"))))
    assert_failure(response, "storage_failure")
    assert response.status_code == 500 and snapshot(client) == before


def test_bulk_hidden_selection_cancel_and_atomic_confirmation(material_actions_client):
    client = material_actions_client
    refs = seed(client, 5)
    before = snapshot(client)
    preview = bulk_preview(client, [refs["MAT00004"], refs["MAT00001"]], {"query": "MAT00000"})
    assert preview["commit_policy"] == "atomic" and preview["can_confirm"]
    assert [row["business_code"] for row in preview["rows"]] == ["MAT00004", "MAT00001"]
    assert snapshot(client) == before  # Closing the preview needs no cancel write.
    result = confirm(client, preview)
    assert result.status_code == 200 and result.get_json()["data"]["deleted_count"] == 2
    with database(client) as conn:
        assert [row[0] for row in conn.execute("SELECT material_id FROM Materials ORDER BY material_id")] == ["MAT00000", "MAT00002", "MAT00003"]
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_real_file_upsert_preserves_hidden_columns_and_reports_no_internal_facts(material_actions_client, fmt):
    client = material_actions_client
    seed(client)
    with database(client) as conn:
        conn.execute("ALTER TABLE Materials ADD COLUMN private_legacy TEXT DEFAULT 'PRIVATE_VALUE'")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1)")
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty) VALUES ('B','MAT00000',5)")
        conn.commit()
    before = snapshot(client)
    preview = import_preview(client, [["MAT00000", "修改", r"\N"], ["000007", "=literal", "D50"]], fmt,
                             headers=("物料编号", "名称", "规格"))
    assert preview["summary"]["new"] == preview["summary"]["update"] == 1
    assert preview["rows"][0]["reference_count"] == 1 and preview["rows"][0]["requires_confirmation"]
    assert preview["rows"][0]["changes"] == {"label": {"before": "Material 0", "after": "修改"}, "spec": {"before": "D25", "after": None}}
    text = json.dumps(preview)
    for private in ("PRIVATE_VALUE", "private_legacy", '"expected"', '"entity_key"', '"revision"', '"bm_id"', '"identity_history"'):
        assert private not in text
    assert snapshot(client) == before
    response = confirm(client, preview)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert len(response.get_json()["data"]["rows"]) == 2
    with database(client) as conn:
        original = dict(conn.execute("SELECT * FROM Materials WHERE material_id='MAT00000'").fetchone())
        assert original["name"] == "修改" and original["spec"] is None
        assert original["unit"] == "kg" and original["remark"] == "keep" and original["private_legacy"] == "PRIVATE_VALUE"
        assert conn.execute("SELECT required_qty FROM BatchMaterials").fetchone()[0] == 5


@pytest.mark.parametrize("operation", ("bulk", "import"))
@pytest.mark.parametrize("change", ("update", "recreate", "hidden", "reference"))
def test_stale_full_facts_never_write_partial_batch(material_actions_client, operation, change):
    client = material_actions_client
    refs = seed(client)
    with database(client) as conn:
        conn.execute("ALTER TABLE Materials ADD COLUMN legacy_note TEXT DEFAULT 'original'")
        conn.commit()
    preview = (bulk_preview(client, list(refs.values())) if operation == "bulk" else
               import_preview(client, [["NEW", "New"], ["MAT00000", "Changed"]]))
    with database(client) as conn:
        if change == "recreate":
            conn.execute("DELETE FROM Materials WHERE material_id='MAT00000'")
            conn.execute("INSERT INTO Materials(material_id,name) VALUES ('MAT00000','Rebuilt')")
        elif change == "reference":
            conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P','Part')")
            conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1)")
            conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty) VALUES ('B','MAT00000',5)")
        else:
            field = "legacy_note" if change == "hidden" else "remark"
            conn.execute("UPDATE Materials SET " + field + "='concurrent' WHERE material_id='MAT00000'")
        conn.commit()
    before = snapshot(client)
    assert_failure(confirm(client, preview), "stale_write")
    assert snapshot(client) == before


@pytest.mark.parametrize("operation", ("bulk", "import"))
@pytest.mark.parametrize("lost_context", ("expired", "restart"))
def test_receipt_first_replay_survives_expired_or_lost_short_tokens(material_actions_client, operation, lost_context):
    client = material_actions_client
    refs = seed(client)
    preview = (bulk_preview(client, list(refs.values())) if operation == "bulk" else
               import_preview(client, [["NEW", "New"]]))
    first = confirm(client, preview).get_json()
    assert first["result"] == "committed" and not first["replayed"]
    before = snapshot(client)
    if lost_context == "expired":
        expire_contexts(client)
    else:
        from app import create_app
        client = register_actions(create_app())
        restarted = snapshot(client)
        assert without_startup_logs(restarted) == without_startup_logs(before)
        before = restarted  # Startup records plugin loading; replay itself must write nothing.
    replay = confirm(client, preview)
    assert replay.status_code == 200 and replay.get_json() == {**first, "replayed": True}
    assert_failure(confirm(client, preview, key="material-actions-new-key-0001"), "stale_write")
    assert snapshot(client) == before


def test_same_request_different_preview_and_wrong_action_are_conflicts(material_actions_client):
    client = material_actions_client
    refs = seed(client)
    first = import_preview(client, [["NEW", "New"]])
    second = bulk_preview(client, [refs["MAT00000"]])
    assert confirm(client, first).status_code == 200
    assert_failure(confirm(client, second), "request_key_conflict")
    body = command_body(first, "wrong-action-key-00001")
    response = client.post(BASE + "/entities/material/bulk-confirm", json=body)
    assert_failure(response, "stale_write")


def test_write_context_cannot_be_swapped_between_previews(material_actions_client):
    client = material_actions_client
    first = import_preview(client, [["A", "A"]])
    second = import_preview(client, [["B", "B"]])
    body = command_body(first)
    body["write_token"] = second["write_context"]["write_token"]
    before = snapshot(client)
    assert_failure(confirm(client, first, body=body), "stale_write")
    assert snapshot(client) == before


@pytest.mark.parametrize("field,value", (("refs", []), ("scope", {}), ("snapshot", {}), ("file", "fake"),
                                          ("preview_hash", "fake"), ("source", "demo")))
def test_confirm_rejects_browser_authored_facts(material_actions_client, field, value):
    client = material_actions_client
    preview = import_preview(client, [["A", "A"]])
    body = command_body(preview)
    body["input"][field] = value
    before = snapshot(client)
    assert_failure(confirm(client, preview, body=body), "invalid_input")
    assert snapshot(client) == before


@pytest.mark.parametrize("operation", ("bulk", "import"))
def test_rejected_preview_cannot_be_forced_to_commit(material_actions_client, operation):
    client = material_actions_client
    refs = seed(client)
    preview = (bulk_preview(client, [refs["MAT00000"], "f" * 48]) if operation == "bulk" else
               import_preview(client, [["NEW", "New"], ["", "bad"]]))
    assert not preview["can_confirm"] and preview["summary"]["rejected"] == 1
    assert not preview["write_context"]["capabilities"][preview["operation"]]
    before = snapshot(client)
    assert_failure(confirm(client, preview), "constraint_conflict")
    assert snapshot(client) == before


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("selection", ("all", "filtered", "selected"))
def test_download_full_scopes_above_2000_not_visible_page(material_actions_client, fmt, selection):
    client = material_actions_client
    refs = seed(client, 5003)
    scope = {"query": "MAT", "status": "active", "sort": "label", "direction": "desc"}
    selected = list(refs.values())[::-1][:2501] if selection == "selected" else None
    before = snapshot(client)
    approved = export_preview(client, selection, scope=scope, refs=selected)
    with database(client) as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM Materials ORDER BY material_id")]
    if selection == "filtered":
        rows = sorted((row for row in rows if row["status"] == "active"), key=lambda row: row["name"], reverse=True)
    elif selection == "selected":
        rows = rows[::-1][:2501]
    assert approved["data"]["row_count"] == len(rows) > 2000
    response = download(client, approved, fmt)
    check_download(response, rows, fmt)
    assert response.headers["X-Workbench-Snapshot-Ref"] == approved["meta"]["snapshot_ref"]
    assert snapshot(client) == before


def test_empty_selection_is_empty_not_all_and_templates_have_no_demo_rows(material_actions_client):
    client = material_actions_client
    seed(client)
    before = snapshot(client)
    approved = export_preview(client, "selected", refs=[])
    assert approved["data"]["row_count"] == 0
    for fmt in ("csv", "xlsx"):
        response = download(client, approved, fmt)
        check_download(response, [], fmt)
        template = client.get(BASE + "/templates/material", query_string={"format": fmt})
        assert template.status_code == 200 and int(template.headers["X-Workbench-Row-Count"]) == 0
        preview = upload(client, template.data, fmt)
        assert preview.status_code == 200 and preview.get_json()["data"]["rows"] == []
    assert snapshot(client) == before


@pytest.mark.parametrize("change", ("update", "recreate", "expired"))
def test_export_cannot_silently_refresh_approved_data(material_actions_client, change):
    client = material_actions_client
    refs = seed(client)
    approved = export_preview(client, "selected", refs=[refs["MAT00000"]])
    if change == "expired":
        expire_contexts(client)
    else:
        with database(client) as conn:
            if change == "recreate":
                conn.execute("DELETE FROM Materials WHERE material_id='MAT00000'")
                conn.execute("INSERT INTO Materials(material_id,name) VALUES ('MAT00000','Rebuilt')")
            else:
                conn.execute("UPDATE Materials SET name='Changed' WHERE material_id='MAT00000'")
            conn.commit()
    before = snapshot(client)
    assert_failure(download(client, approved, "csv"), "snapshot_stale")
    assert snapshot(client) == before


def test_preview_cannot_spoof_existing_list_scope_or_expand_selected_refs(material_actions_client):
    client = material_actions_client
    refs = seed(client)
    context = list_context(client, {"query": "MAT00000"})
    before = snapshot(client)
    for update in ({"scope": {}}, {"page_size": 200}):
        response = client.post(BASE + "/exports/material/preview", json={"selection": "filtered", **context, **update})
        assert_failure(response, "snapshot_stale")
    for selection, ref in (("all", []), ("selected", ["MAT00000"]), ("selected", [refs["MAT00000"]] * 2)):
        response = client.post(BASE + "/exports/material/preview", json={"selection": selection, **context, "refs": ref})
        assert_failure(response, "invalid_input")
    approved = export_preview(client, "selected", refs=[refs["MAT00000"]])
    response = client.get(BASE + "/exports/material", query_string={"export_ref": approved["data"]["export_ref"], "format": "csv", "scope": "all"})
    assert_failure(response, "invalid_input")
    assert snapshot(client) == before


def test_2501_bulk_deletes_all_and_late_failure_rolls_back_every_row(material_actions_client, monkeypatch):
    client = material_actions_client
    refs = seed(client, 2501)
    preview = bulk_preview(client, list(refs.values()))
    assert preview["summary"]["delete"] == 2501
    before = snapshot(client)
    original = WorkbenchMaterialService.apply
    seen = []

    def fail_last(self, action, payload, identity=None):
        result = original(self, action, payload, identity)
        seen.append(identity.ref)
        if len(seen) == 2501:
            raise WorkbenchCommandRejected("constraint_conflict", "fixture late conflict")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchMaterialService, "apply", fail_last)
        assert_failure(confirm(client, preview), "constraint_conflict")
    assert len(seen) == 2501 and snapshot(client) == before
    response = confirm(client, preview)
    assert response.status_code == 200 and response.get_json()["data"]["deleted_count"] == 2501
    with database(client) as conn:
        assert conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_import_2000_limit_does_not_truncate_and_download_roundtrip_is_unchanged(material_actions_client, fmt):
    client = material_actions_client
    before = snapshot(client)
    content = file_bytes([[f"NEW{n:05d}", "New"] for n in range(2001)], fmt, headers=("物料编号", "名称"))
    assert_failure(upload(client, content, fmt), "invalid_input")
    assert snapshot(client) == before
    preview = import_preview(client, [[f"NEW{n:05d}", "New"] for n in range(2000)], fmt)
    result = confirm(client, preview)
    assert result.status_code == 200 and len(result.get_json()["data"]["rows"]) == 2000
    approved = export_preview(client, "all")
    response = download(client, approved, fmt)
    repeated = upload(client, response.data, fmt)
    assert repeated.status_code == 200 and repeated.get_json()["data"]["summary"]["unchanged"] == 2000
    result = confirm(client, repeated.get_json()["data"], key="roundtrip-request-0001")
    assert result.status_code == 200 and result.get_json()["result"] == "unchanged"


@pytest.mark.parametrize("operation", ("bulk", "import"))
def test_receipt_storage_failure_rolls_back_and_returns_unknown_lookup_target(material_actions_client, monkeypatch, operation):
    client = material_actions_client
    refs = seed(client)
    preview = bulk_preview(client, list(refs.values())) if operation == "bulk" else import_preview(client, [["NEW", "New"]])
    before = snapshot(client)

    def broken(*args, **kwargs):
        raise OSError("PRIVATE_STORAGE_DETAIL")

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandRepository, "insert", broken)
        response = confirm(client, preview)
    failure = assert_failure(response, "storage_failure", committed="unknown")
    assert "PRIVATE_STORAGE_DETAIL" not in response.get_data(as_text=True)
    assert snapshot(client) == before
    missing = client.get(failure["error"]["result_target"]).get_json()
    assert missing["state"] == "not_recorded" and missing["may_be_in_flight"]
    saved = confirm(client, preview)
    assert saved.status_code == 200
    assert client.get(failure["error"]["result_target"]).get_json() == {**saved.get_json(), "replayed": True}


def test_preview_failures_have_committed_false_and_never_expose_raw_exception(material_actions_client, monkeypatch):
    client = material_actions_client
    refs = seed(client)
    context = list_context(client)
    before = snapshot(client)

    def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE_READ_DETAIL")

    monkeypatch.setattr(WorkbenchMaterialBulkService, "preview_delete", broken)
    monkeypatch.setattr(WorkbenchMaterialFileService, "preview_import", broken)
    for response in (client.post(BASE + "/entities/material/bulk-preview", json={"action": "delete", "refs": list(refs.values()), **context}),
                     upload(client, b"business_code,label\nA,A")):
        assert_failure(response, "storage_failure")
        assert "PRIVATE_READ_DETAIL" not in response.get_data(as_text=True)
    assert snapshot(client) == before


def test_strict_json_multipart_and_download_validation(material_actions_client):
    client = material_actions_client
    before = snapshot(client)
    bodies = ('{"scope":{},"scope":{"query":"x"}}', '[1,2]', 'null', '{bad')
    for body in bodies:
        assert_failure(client.post(BASE + "/entities/material/bulk-preview", data=body, content_type="application/json"), "invalid_input")
    for fields in ({"scope": "{}"}, {"refs": "[]"}, {"mode": "replace"}, {"format": "xls"}):
        assert_failure(upload(client, b"business_code,label\nA,A", **fields), "invalid_input")
    duplicate = MultiDict([("file", (BytesIO(b"x"), "a.csv")), ("format", "csv"), ("format", "xlsx"), ("mode", "upsert")])
    assert_failure(client.post(BASE + "/imports/material/preview", data=duplicate, content_type="multipart/form-data"), "invalid_input")
    for content, fmt in ((b"not-zip", "xlsx"), (b"\xff", "csv"), (b"", "csv")):
        assert_failure(upload(client, content, fmt), "invalid_input")
    for query in ({"format": "xls"}, {"format": "csv", "path": "/private"}, [("format", "csv"), ("format", "xlsx")]):
        assert_failure(client.get(BASE + "/templates/material", query_string=query), "invalid_input")
    assert snapshot(client) == before


def test_same_count_requirement_mutation_and_absent_create_delete_are_stale(material_actions_client):
    client = material_actions_client
    seed(client)
    with database(client) as conn:
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1)")
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty) VALUES ('B','MAT00000',5)")
        conn.commit()
    first = import_preview(client, [["MAT00000", "Changed"]])
    absent = import_preview(client, [["NEW", "New"]])
    with database(client) as conn:
        conn.execute("UPDATE BatchMaterials SET required_qty=6")
        conn.execute("INSERT INTO Materials(material_id,name) VALUES ('NEW','Transient')")
        conn.execute("DELETE FROM Materials WHERE material_id='NEW'")
        conn.commit()
    before = snapshot(client)
    for preview in (first, absent):
        assert_failure(confirm(client, preview), "stale_write")
    assert snapshot(client) == before


def test_reference_protection_is_visible_in_bulk_preview(material_actions_client):
    client = material_actions_client
    refs = seed(client)
    with database(client) as conn:
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1)")
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty) VALUES ('B','MAT00000',5)")
        conn.commit()
    before = snapshot(client)
    preview = bulk_preview(client, [refs["MAT00001"], refs["MAT00000"]])
    assert preview["rows"][1]["reference_count"] == 1
    assert preview["rows"][1]["errors"][0]["code"] == "constraint_conflict"
    assert_failure(confirm(client, preview), "constraint_conflict")
    assert snapshot(client) == before


def test_concurrent_same_key_http_requests_commit_once(material_actions_client):
    from concurrent.futures import ThreadPoolExecutor

    client = material_actions_client
    preview = import_preview(client, [["A", "A"], ["B", "B"]])

    def submit(_):
        with client.application.test_client() as connection:
            response = confirm(connection, preview)
            assert response.status_code == 200, response.get_data(as_text=True)
            return response.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(result["replayed"] for result in results) == [False, True]
    assert results[0]["receipt_ref"] == results[1]["receipt_ref"]
    with database(client) as conn:
        assert conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1


def test_preview_registry_contains_only_small_binding_not_file_or_snapshot(material_actions_client):
    from web import public_token_registry
    from web.routes.workbench.material_actions_context import PREVIEW_SCOPE
    from web.routes.workbench.material_actions_previews import _EXTENSION

    client = material_actions_client
    content = file_bytes([[f"NEW{n:05d}", "Material name"] for n in range(2000)], "csv", headers=("物料编号", "名称"))
    first = upload(client, content).get_json()["data"]
    repeated = upload(client, content).get_json()["data"]
    assert first["preview_ref"] == repeated["preview_ref"]
    with client.application.app_context():
        entry = public_token_registry._scope_state(PREVIEW_SCOPE)["tokens"][first["preview_ref"]]
        binding = json.loads(entry["value"])
        assert set(binding) == {"version", "source", "preview_key"}
        assert len(entry["value"]) < 200 < len(content)
        store = client.application.extensions[_EXTENSION]
        assert len(store) == 1
        assert store[binding["preview_key"]].content == content
        assert len(store[binding["preview_key"]].preview.as_dict()["rows"]) == 2000


def test_expired_private_preview_is_reclaimed_without_changing_public_contract(material_actions_client, monkeypatch):
    from web.routes.workbench import material_actions_previews as previews

    client = material_actions_client
    first = import_preview(client, [["A", "A"]])
    now = previews.time.time()
    monkeypatch.setattr(previews.time, "time", lambda: now + 901)
    assert_failure(confirm(client, first), "stale_write")
    second = import_preview(client, [["B", "B"]])
    store = client.application.extensions[previews._EXTENSION]
    assert len(store) == 1
    assert next(iter(store.values())).preview.as_dict()["rows"][0]["business_code"] == "B"
    assert confirm(client, second).status_code == 200


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_upload_uses_existing_configured_file_limit_including_exact_boundary(material_actions_client, monkeypatch, fmt):
    client = material_actions_client
    assert client.application.config["EXCEL_MAX_UPLOAD_BYTES"] == 16 * 1024 * 1024
    content = file_bytes([["A", "A"]], fmt, headers=("物料编号", "名称"))
    before = snapshot(client)
    monkeypatch.setitem(client.application.config, "EXCEL_MAX_UPLOAD_BYTES", len(content) - 1)
    oversized = upload(client, content, fmt)
    assert oversized.status_code == 413
    assert_failure(oversized, "invalid_input")
    assert snapshot(client) == before
    monkeypatch.setitem(client.application.config, "EXCEL_MAX_UPLOAD_BYTES", len(content))
    accepted = upload(client, content, fmt)
    assert accepted.status_code == 200 and accepted.get_json()["data"]["can_confirm"]
    assert snapshot(client) == before

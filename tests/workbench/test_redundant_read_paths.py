"""Real HTTP reads reuse checked rows and import sources without whole-collection scans."""

from io import BytesIO

import pytest

from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from core.services.workbench.material.service import WorkbenchMaterialService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from tests.workbench.material_actions_api_support import seed
from tests.workbench.material_file_support import file_bytes as material_file_bytes
from tests.workbench.resource_file_support import file_bytes as resource_file_bytes
from tests.workbench.system_maintenance_support import system_api as _system_api_fixture  # noqa: F401


def _unexpected_reload(*args, **kwargs):
    raise AssertionError("This read already owns the required facts")


def test_material_list_and_detail_sign_contexts_from_the_loaded_rows(app_client, monkeypatch):
    references = seed(app_client, count=2)
    monkeypatch.setattr(WorkbenchMaterialService, "snapshot", _unexpected_reload)
    listed = app_client.get("/api/workbench/v1/entities/material")
    assert listed.status_code == 200, listed.get_data(as_text=True)
    entities = listed.get_json()["data"]["entities"]
    assert {row["ref"] for row in entities} == set(references.values())
    for row in entities:
        assert row["write_context"]["capabilities"]["material.update"] is True
    detail = app_client.get("/api/workbench/v1/entities/material/" + entities[0]["ref"])
    assert detail.status_code == 200, detail.get_data(as_text=True)
    assert detail.get_json()["data"]["write_context"]["write_token"]


@pytest.mark.parametrize("kind", ["material", "operator"])
def test_file_preview_uses_its_immutable_reference_instead_of_collection_fingerprint(app_client, monkeypatch, kind):
    monkeypatch.setattr(WorkbenchMaterialQueryService, "state_fingerprint", _unexpected_reload)
    monkeypatch.setattr(WorkbenchResourceQueryService, "state_fingerprint", _unexpected_reload)
    if kind == "material":
        content = material_file_bytes([["MAT-NEW", "New material"]], "csv", ["物料编号", "名称"])
    else:
        content = resource_file_bytes([["OP-NEW", "New operator", "active"]], "csv", ["business_code", "label", "status"])
    response = app_client.post("/api/workbench/v1/imports/" + kind + "/preview", data={
        "file": (BytesIO(content), "input.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["data"]["can_confirm"] is True
    assert body["data"]["preview_ref"] and body["meta"]["snapshot_ref"]


@pytest.mark.parametrize("kind", ["material", "operator"])
def test_http_confirmation_reuses_parsed_source(app_client, monkeypatch, kind):
    from core.services.workbench.material import files as material_files
    from core.services.workbench.resource import files as resource_files

    module, name = ((material_files, "read_material_file") if kind == "material" else
                    (resource_files, "read_resource_file"))
    original = getattr(module, name)
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    content = (material_file_bytes([["MAT-ONCE", "Once"]], "csv", ["物料编号", "名称"]) if kind == "material" else
               resource_file_bytes([["OP-ONCE", "Once", "active"]], "csv", ["business_code", "label", "status"]))
    response = app_client.post("/api/workbench/v1/imports/" + kind + "/preview", data={
        "file": (BytesIO(content), "input.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    preview = response.get_json()["data"]
    saved = app_client.post("/api/workbench/v1/imports/" + kind + "/confirm", json={
        "request_key": "parsed-source-once-0001", "write_token": preview["write_context"]["write_token"],
        "input": {"preview_ref": preview["preview_ref"]}})
    assert saved.status_code == 200, saved.get_data(as_text=True)
    assert saved.get_json()["result"] == "committed"
    assert len(calls) == 1


def test_backup_collection_uses_one_journal_capture_and_keeps_pending_block(system_api, monkeypatch):
    from core.services.workbench.facts.system_journal import SystemMaintenanceJournal

    system_api.journal().begin("pending-journal-0001", "restore", {})
    original = SystemMaintenanceJournal.records
    calls = []

    def counted(self, *, names=None):
        calls.append(1)
        return original(self, names=names)

    monkeypatch.setattr(SystemMaintenanceJournal, "records", counted)
    response = system_api.read("/backups")
    capabilities = response["data"]["capabilities"]
    assert capabilities["create"] is False and capabilities["delete"] is False
    assert capabilities["blocked_reason"]
    assert len(calls) == 1

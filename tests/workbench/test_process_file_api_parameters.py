"""No client facts, implicit scope changes, duplicate fields or partial reads."""

from io import BytesIO

import pytest
from flask import g
from werkzeug.datastructures import MultiDict

from core.models.workbench_process_file import IMPORT_BYTE_LIMIT
from tests.workbench.process_file_api_support import BASE, file_api_fixture, node_contract
from tests.workbench.process_file_codec_support import file_bytes
from tests.workbench.process_stage_api_support import rejected


@pytest.mark.parametrize("change", [
    {"format": "pdf"}, {"format": None}, {"selection": "page"}, {"selection": []},
    {"scope": None}, {"scope": {"page": 1}}, {"scope": {"size": 20}}, {"scope": {"unknown": 1}},
    {"page_size": True}, {"page_size": 0}, {"page_size": 201}, {"page_size": "2"},
    {"refs": []}, {"refs": None}, {"target_ref": None}, {"unknown": True}, {"snapshot_ref": ""},
])
def test_export_rejects_invalid_parameters(file_api, change):
    body, _ = file_api.export_body()
    before = file_api.snapshot()
    response = file_api.file_post("route", "export-preview", {**body, **change})
    assert response.status_code in (400, 409, 422), response.get_json()
    assert response.get_json()["committed"] is False
    assert file_api.snapshot() == before


@pytest.mark.parametrize("mode", ["wrong-list", "wrong-detail", "detail-scope", "detail-refs", "detail-all", "page-size", "sort", "query"])
def test_export_requires_original_context(file_api, mode):
    target = file_api.ref()
    body, _ = file_api.export_body(selection="explicit", refs=[target], target=target)
    listed, _ = file_api.export_body()
    if mode == "wrong-list":
        body["snapshot_ref"] = listed["snapshot_ref"]
    elif mode == "wrong-detail":
        body = {**listed, "snapshot_ref": body["snapshot_ref"]}
    elif mode == "detail-scope":
        body["scope"] = {"query": "PROC"}
    elif mode == "detail-refs":
        body["refs"] = [file_api.ref(code="PROC-002")]
    elif mode == "detail-all":
        body["selection"] = "all"
        del body["refs"]
    else:
        body = listed
        if mode == "page-size":
            body["page_size"] = 3
        else:
            body["scope"] = {mode: "label" if mode == "sort" else "PROC"}
    response = file_api.file_post("route", "export-preview", body)
    assert response.status_code in (400, 409), response.get_json()
    assert response.get_json()["committed"] is False


@pytest.mark.parametrize("params", [{"format": "xlsx"}, {"selection": "all"}, {"refs": "x"}, {"scope": "{}"}])
def test_download_cannot_reinterpret_preflight(file_api, params):
    _, preview, _ = file_api.export("route")
    rejected(file_api.download("route", preview["data"]["export_ref"], **params), "invalid_input", 400)
    rejected(file_api.download("hours", preview["data"]["export_ref"]), "snapshot_stale")
    rejected(file_api.client.get(BASE + "/process-files/route/export", query_string=MultiDict([
        ("export_ref", preview["data"]["export_ref"]), ("export_ref", preview["data"]["export_ref"])])), "invalid_input", 400)


@pytest.mark.parametrize("endpoint", ["export-preview", "confirm"])
@pytest.mark.parametrize("content", ['[]', '{"format":"csv","format":"xlsx"}', '{"input":{"rows":1,"rows":2}}', 'null', '{'])
def test_duplicate_or_nonobject_json_is_rejected(file_api, endpoint, content):
    before = file_api.snapshot()
    response = file_api.client.post(BASE + "/process-files/route/" + endpoint, data=content, content_type="application/json")
    rejected(response, "invalid_input", 400)
    assert file_api.snapshot() == before


@pytest.mark.parametrize("field", ["rows", "facts", "content", "target_ref", "format", "mode", "file_sha256"])
def test_confirm_does_not_accept_browser_row_facts(file_api, field):
    preview = file_api.preview_rows("route", [{"business_code": "PROC-002", "label": "changed"}])
    body = file_api.file_body(preview)
    body["input"][field] = []
    before = file_api.snapshot()
    rejected(file_api.file_post("route", "confirm", body), "invalid_input", 400)
    assert file_api.snapshot() == before


@pytest.mark.parametrize("error", ["missing-file", "duplicate-file", "duplicate-format", "unknown", "bad-mode", "query"])
def test_multipart_exact_fields(file_api, error):
    content = b"business_code\r\nPROC-002\r\n"
    data = MultiDict()
    data.add("format", "csv")
    data.add("mode", "upsert")
    if error != "missing-file":
        data.add("file", (BytesIO(content), "input.csv"))
    if error == "duplicate-file":
        data.add("file", (BytesIO(content), "again.csv"))
    elif error == "duplicate-format":
        data.add("format", "csv")
    elif error == "unknown":
        data.add("rows", "[]")
    elif error == "bad-mode":
        data["mode"] = "replace"
    before = file_api.snapshot()
    response = file_api.client.post(BASE + "/process-files/route/preview" + ("?x=1" if error == "query" else ""),
                                    data=data, content_type="multipart/form-data")
    rejected(response, "invalid_input", 400)
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_row_limit_rejects_entire_file(file_api, kind, fmt):
    columns = ["business_code"] if kind == "route" else ["business_code", "sequence"]
    values = [[f"PART-{n:04d}"] + ([1] if kind == "hours" else []) for n in range(2001)]
    content = file_bytes(columns, values, fmt)
    before = file_api.snapshot()
    rejected(file_api.upload(kind, content, fmt), "invalid_input", 422)
    assert file_api.snapshot() == before


@pytest.mark.parametrize("configured", [None, 128])
def test_upload_size_limit_is_atomic(file_api, configured):
    if configured is not None:
        file_api.client.application.config["EXCEL_MAX_UPLOAD_BYTES"] = configured
    limit = configured or IMPORT_BYTE_LIMIT
    before = file_api.snapshot()
    rejected(file_api.upload("route", b"x" * (limit + 1)), "invalid_input", 413)
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
def test_reads_and_preview_work_on_query_only_connection(file_api, kind):
    if kind == "hours":
        file_api.prepare()
    before = file_api.snapshot()
    statements = []

    def query_only():
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(statements.append)

    file_api.client.application.before_request_funcs[None].append(query_only)
    rows = [{"business_code": "PROC-002", "label": "preview only"}] if kind == "route" else [
        {"business_code": "PROC-001", "sequence": 10, "unit_hours": 2}]
    preview = file_api.preview_rows(kind, rows)
    node_contract("preview", preview, kind)
    file_api.export(kind, selection="explicit", refs=[file_api.ref()])
    template = file_api.client.get(BASE + "/process-files/" + kind + "/template?format=csv")
    assert template.status_code == 200
    assert file_api.snapshot() == before
    assert not [sql for sql in statements if sql.lstrip().split(" ")[0].upper() in
                {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE"}]

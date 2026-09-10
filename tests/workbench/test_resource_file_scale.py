"""Import-only 2000-row boundary; complete 10000-row exports and deletions."""

import pytest

from core.errors import ValidationError
from core.services.workbench.resource_bulk import WorkbenchResourceBulkService
from core.services.workbench.resource_files import WorkbenchResourceFileService
from tests.workbench.test_resource_file_support import (
    KINDS,
    confirm,
    decode,
    exported,
    file_bytes,
    measure,
    raw,
    scope,
    seed_many,
)


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("kind", KINDS)
def test_import_2000_allowed_2001_rejected_without_writes(schema_conn, fmt, kind):
    headers = ["business_code", "label", "remark" if kind == "op_type" else "status"]
    rows = [[f"I{i:05d}", f"import {i}", "note" if kind == "op_type" else "active"] for i in range(2001)]
    if kind == "supplier":
        headers.append("default_days")
        rows = [row + [2.5] for row in rows]
    service = WorkbenchResourceFileService(schema_conn, kind)
    selected_scope = scope("internal" if kind == "op_type" else None)
    changes = schema_conn.total_changes
    with pytest.raises(ValidationError, match="2000"):
        service.preview_import(file_bytes(rows, fmt, headers), file_format=fmt, scope=selected_scope)
    assert schema_conn.total_changes == changes
    content = file_bytes(rows[:2000], fmt, headers)
    preview = service.preview_import(content, file_format=fmt, scope=selected_scope)
    assert preview.as_dict()["summary"]["new"] == 2000
    result = confirm(schema_conn, kind, preview, content, fmt)
    assert len(result["data"]["rows"]) == 2000 and raw(schema_conn, kind, "I01999") is not None


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("kind", KINDS)
def test_10000_export_bytes_complete_and_page_size_independent(schema_conn, fmt, kind):
    refs = seed_many(schema_conn, kind)
    category = "internal" if kind == "op_type" else None
    before = schema_conn.total_changes
    download = measure(kind + "_export_" + fmt, lambda: exported(schema_conn, kind, fmt, category=category, query="FILE"))
    assert download.row_count == 10000
    _, values = decode(download, fmt)
    assert len(values) == 10000 and values[0][0] == "FILE00000" and values[-1][0] == "FILE09999"
    assert schema_conn.total_changes == before
    selected = exported(schema_conn, kind, "csv", category=category, selected_refs=[refs[-1], refs[0]], query="NOT-MATCHING")
    assert [row[0] for row in decode(selected, "csv")[1]] == ["FILE09999", "FILE00000"]


@pytest.mark.parametrize("kind", KINDS)
def test_10000_bulk_delete_complete_atomic_domain_path(schema_conn, kind):
    refs = seed_many(schema_conn, kind)
    service = WorkbenchResourceBulkService(schema_conn, kind)
    preview = measure(kind + "_bulk_preview", lambda: service.preview_delete(refs, scope=scope("internal" if kind == "op_type" else None)))
    assert preview.as_dict()["summary"]["delete"] == 10000
    result = measure(kind + "_bulk_confirm", lambda: confirm(schema_conn, kind, preview))
    assert result["data"]["deleted_count"] == 10000
    assert [row["entity_ref"] for row in result["data"]["rows"]] == refs
    assert raw(schema_conn, kind, "FILE09999") is None

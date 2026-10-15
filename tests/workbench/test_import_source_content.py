"""Original source identities and old report replay use retained content."""

from copy import deepcopy

import pytest

from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_field_report_source import PreparedFieldReportSource
from core.models.workbench_resource_file_source import PreparedImportSource
from core.services.workbench.execution.field_report_files import FieldReportFileService


def test_prepared_import_retains_original_bytes_and_confirmed_document():
    content = b"original-file\x00\xff"
    request = {"format": "csv", "mode": "upsert", "scope": {}}
    decoded = [{"value": True}]
    notices = [{"details": ["extra sheet"]}]
    source = PreparedImportSource.build("material.import", request, decoded, notices, content=content)
    assert source._rows is decoded and source._notices is notices
    checked = source.request_for("material.import", "csv", "upsert", {})
    preview = AtomicActionPreview.build("material.import", checked, [{"result": "new"}], source=source)
    assert source.content == content
    assert checked["actual_source_ref"] == source.source_ref
    assert "file_sha256" not in checked
    assert PreparedImportSource.confirmation(preview, content) is source
    assert PreparedImportSource.confirmation(preview, source) is source
    with pytest.raises(WorkbenchCommandRejected) as failure:
        PreparedImportSource.confirmation(preview, content + b"changed")
    assert failure.value.code == "stale_write"
    rows, parsed_notices = source.parsed()
    rows[0]["value"] = 1
    parsed_notices[0]["details"].append("consumer note")
    assert source.parsed()[0][0]["value"] is True
    assert source.parsed()[1] == [{"details": ["extra sheet"]}]
    intent = preview.intent()
    assert intent["preview_document"] == preview.document
    assert content.decode("latin-1") not in intent["preview_document"]
    assert "preview_hash" not in intent


def _report_row():
    return {"row": 2, "values": {"actual_start": "2026-10-01T08:00:00", "actual_end": "2026-10-01T09:00:00",
            "completed_quantity": 1, "effective_processing_hours": 1.0, "remark": "original",
            "machine_label": "", "operator_label": "", "report_no": ""}}


def test_field_source_number_is_stable_and_reuses_one_saved_old_report():
    service = FieldReportFileService.__new__(FieldReportFileService)
    task = {"task_ref": "a" * 48, "execution": {"reports": []}}
    row = _report_row()
    resources = {"codes": {}, "labels": {}}
    source = PreparedFieldReportSource.build(b"original", [row])
    first = service._row_item(row, task, resources, source.source_ref)
    assert first == service._row_item(source.parsed()[0], task, resources, source.source_ref)
    assert first["payload"]["report_no"] == "BG-X-" + source.source_ref + "-2"
    old = deepcopy(first["payload"])
    old["report_no"] = "BG-X-" + "b" * 32 + "-2"
    task["execution"]["reports"] = [old]
    next_source = PreparedFieldReportSource.build(b"original", [row])
    recovered = service._row_item(row, task, resources, next_source.source_ref)
    assert recovered["payload"]["report_no"] == old["report_no"]
    supplied = deepcopy(row)
    supplied["values"]["report_no"] = "user-report-number"
    assert service._row_item(supplied, task, resources, next_source.source_ref)["payload"]["report_no"] == "user-report-number"


def test_field_source_requires_original_number_for_ambiguous_old_reports():
    service = FieldReportFileService.__new__(FieldReportFileService)
    row = _report_row()
    payload = {key: value for key, value in row["values"].items() if key not in ("machine_label", "operator_label", "report_no")}
    old = dict(payload, source="excel", report_no="BG-X-" + "b" * 32 + "-2")
    other = dict(old, report_no="BG-X-" + "c" * 32 + "-2")
    task = {"task_ref": "a" * 48, "execution": {"reports": [old, other]}}
    with pytest.raises(WorkbenchCommandRejected) as failure:
        service._row_item(row, task, {"codes": {}, "labels": {}}, "d" * 32)
    assert failure.value.code == "invalid_input"

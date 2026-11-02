"""Retained source facts own decoded rows and their source number; old report replay reuses saved numbers."""

from copy import deepcopy

import pytest

from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_field_report_source import PreparedFieldReportSource
from core.models.workbench_resource_file_source import PreparedImportSource
from core.services.workbench.execution.field_report_files import FieldReportFileService, report_index


def test_prepared_import_retains_parsed_facts():
    request = {"format": "csv", "mode": "upsert", "scope": {}}
    decoded = [{"value": True}]
    notices = [{"details": ["extra sheet"]}]
    source = PreparedImportSource.build(request, decoded, notices)
    rows, kept = source.parsed()
    assert rows is decoded and kept is notices
    checked = source.request()
    preview = AtomicActionPreview.build("material.import", checked, [{"result": "new"}], source=source)
    assert "file_sha256" not in checked
    assert preview.source is source


def _report_row():
    return {"row": 2, "values": {"actual_start": "2026-10-01T08:00:00", "actual_end": "2026-10-01T09:00:00",
            "completed_quantity": 1, "effective_processing_hours": 1.0, "remark": "original",
            "machine_label": "", "operator_label": "", "report_no": ""}, "errors": []}


def test_field_source_number_is_stable_and_reuses_one_saved_old_report():
    service = FieldReportFileService.__new__(FieldReportFileService)
    task = {"task_ref": "a" * 48, "execution": {"reports": []}}
    row = _report_row()
    resources = {"codes": {}, "labels": {}}
    source = PreparedFieldReportSource.build([row])
    proposal, retry = source.parsed()[0], source.parsed()[0]
    proposal["errors"].append({"row": 2, "message": "proposal-only"})
    assert proposal is not retry and retry["errors"] == [] and source.parsed()[0]["errors"] == []
    reports = report_index(task["execution"]["reports"])
    first = service._row_item(row, task["task_ref"], reports, resources, source.source_ref)
    assert first == service._row_item(source.parsed()[0], task["task_ref"], reports, resources, source.source_ref)
    assert first["payload"]["report_no"] == "BG-X-" + source.source_ref + "-2"
    old = deepcopy(first["payload"])
    old["report_no"] = "BG-X-" + "b" * 32 + "-2"
    task["execution"]["reports"] = [old]
    next_source = PreparedFieldReportSource.build([row])
    reports = report_index(task["execution"]["reports"])
    recovered = service._row_item(row, task["task_ref"], reports, resources, next_source.source_ref)
    assert recovered["payload"]["report_no"] == old["report_no"]
    supplied = deepcopy(row)
    supplied["values"]["report_no"] = "user-report-number"
    assert service._row_item(supplied, task["task_ref"], reports, resources,
                             next_source.source_ref)["payload"]["report_no"] == "user-report-number"


def test_field_source_requires_original_number_for_ambiguous_old_reports():
    service = FieldReportFileService.__new__(FieldReportFileService)
    row = _report_row()
    payload = {key: value for key, value in row["values"].items() if key not in ("machine_label", "operator_label", "report_no")}
    old = dict(payload, source="excel", report_no="BG-X-" + "b" * 32 + "-2")
    other = dict(old, report_no="BG-X-" + "c" * 32 + "-2")
    task = {"task_ref": "a" * 48, "execution": {"reports": [old, other]}}
    with pytest.raises(WorkbenchCommandRejected) as failure:
        service._row_item(row, task["task_ref"], report_index(task["execution"]["reports"]),
                          {"codes": {}, "labels": {}}, "d" * 32)
    assert failure.value.code == "invalid_input"

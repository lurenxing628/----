"""Real spawned XLSX writers preserve native files and propagate terminal failures."""

import io
import os
from concurrent.futures.process import BrokenProcessPool
from copy import deepcopy

import pytest
from openpyxl import load_workbook

from core.models.workbench_action_values import FileDownload
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.decision_file_export import write_decision_xlsx
from core.services.workbench.history.export import read_history_export, write_history_export
from core.services.workbench.run.decision_export import read_decision_export, write_run_decision_export
from tests.workbench.decision_history_support import four_source_case


@pytest.fixture(scope="module")
def materialized_exports(tmp_path_factory):
    """Use the existing small four-source archive; only materialized values leave it."""
    with four_source_case(tmp_path_factory.mktemp("decision-export-process")) as case:
        refs = case.history_refs
        run, _scope, _state = read_decision_export(case.conn, refs["run_ref"], "overview",
            selected_candidate_ref=refs["candidate_ref"])
        history, _scope, _state = read_history_export(case.conn, {
            "timeline": "official", "selected_entry_ref": "adoption:" + refs["trial_receipt_ref"],
            "reference_run_ref": refs["run_ref"],
            "metric_keys": ["expected_operation_count", "makespan_hours", "machine_utilization_ratio"]})
    snapshot = {"snapshot_ref": "s" * 32, "as_of": "2026-10-17T12:00:00"}
    return {"run": (run, snapshot, "overview"), "history": (history, snapshot, "all")}


def workbook_values_and_types(content):
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
    try:
        return [(sheet.title, [tuple((cell.value, type(cell.value), cell.data_type) for cell in row)
                               for row in sheet.iter_rows()]) for sheet in workbook.worksheets]
    finally:
        workbook.close()


@pytest.mark.parametrize("kind", ["run", "history"])
def test_spawned_xlsx_matches_direct_writer_values_types_and_metadata(materialized_exports, kind):
    source, snapshot, section = materialized_exports[kind]
    data = deepcopy(source)
    label = "=原方案001"
    if kind == "run":
        data["candidates"][0]["label"] = label
        direct = write_run_decision_export(data, snapshot, "xlsx", section)
    else:
        data["entries"][0]["label"] = label
        direct = write_history_export(data, snapshot, "xlsx", section)
    spawned = write_decision_xlsx(kind, data, snapshot, section)
    assert isinstance(spawned, FileDownload)
    assert (spawned.filename, spawned.mime_type, spawned.row_count) == (direct.filename, direct.mime_type, direct.row_count)
    expected, actual = workbook_values_and_types(direct.content), workbook_values_and_types(spawned.content)
    assert actual == expected
    assert any(value == label and value_type is str and cell_type == "s"
               for _title, rows in actual for row in rows for value, value_type, cell_type in row)


def test_spawned_xlsx_restores_writer_rejection_code_message_and_status(materialized_exports):
    source, snapshot, section = materialized_exports["history"]
    data = deepcopy(source)
    data["entries"][0]["label"] = "超" * 32768
    with pytest.raises(WorkbenchCommandRejected) as direct:
        write_history_export(data, snapshot, "xlsx", section)
    with pytest.raises(WorkbenchCommandRejected) as spawned:
        write_decision_xlsx("history", data, snapshot, section)
    expected = direct.value
    assert expected.code == "export_format_limit" and expected.status == 422
    assert (spawned.value.code, str(spawned.value), spawned.value.status, spawned.value.operation_refs) == (
        expected.code, str(expected), expected.status, expected.operation_refs)
    assert spawned.value.committed is expected.committed is False


class ExitDuringWorkerUnpickle:
    def __reduce__(self):
        return os._exit, (7,)


def test_spawned_xlsx_reports_worker_exit_as_broken_process_pool():
    # The parent pickles this normally; only child deserialization exits.
    with pytest.raises(BrokenProcessPool):
        write_decision_xlsx("history", {"exit_in_worker": ExitDuringWorkerUnpickle()},
                            {"snapshot_ref": "s" * 32, "as_of": "2026-10-17T12:00:00"}, "all")

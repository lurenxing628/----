"""现行导出文字防止公式注入与超长静默截断。"""

import io
import os
import tempfile
import zipfile

import openpyxl
import pytest
from openpyxl.worksheet._writer import ALL_TEMP_FILES, WorksheetWriter

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.excel_templates import XLSX_MAX_CELL_CHARS, sanitize_export_cell
from core.services.report.exporters.xlsx import (
    export_downtime_impact_xlsx,
    export_execution_review_xlsx,
    export_overdue_xlsx,
    export_utilization_xlsx,
)


def test_export_cells_escape_formula_like_strings() -> None:
    """导出到 Excel 的文字里，四个会被当公式起头的字符必须先加单引号。

    原来这条挂在 build_xlsx_bytes 上，那个构建器 2026-09-21 随旧模板清单一起退役了；
    防注入本身没退役——工时校准导出、工作台报表导出、报表 xlsx 导出三处生产代码都
    直接用 sanitize_export_cell，所以契约改挂在它身上。
    """
    assert sanitize_export_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_export_cell("+SUM(1,1)") == "'+SUM(1,1)"
    assert sanitize_export_cell("-1") == "'-1"
    assert sanitize_export_cell("@A1") == "'@A1"
    assert sanitize_export_cell("正常文字") == "正常文字"
    assert sanitize_export_cell(123) == 123
    # 控制字符会让 openpyxl 写出打不开的文件，一并剔掉；制表和换行保留。
    assert sanitize_export_cell("甲\x00乙\x07") == "甲乙"
    assert sanitize_export_cell("甲\t乙\n丙") == "甲\t乙\n丙"


@pytest.mark.parametrize("write_only", [False, True])
@pytest.mark.parametrize("case_kind", ["plain_overlong", "escaped_overlong"])
def test_native_report_xlsx_exporters_reject_overlong_cells_instead_of_truncating(
    write_only: bool,
    case_kind: str,
) -> None:
    overlong_cell = "x" * (XLSX_MAX_CELL_CHARS + 1) if case_kind == "plain_overlong" else "=" + "x" * XLSX_MAX_CELL_CHARS
    overdue_item = {
        "bucket_label": "已超期",
        "batch_id": "B1",
        "part_no": "P1",
        "part_name": overlong_cell,
        "quantity": 1,
        "due_date": "2026-10-01",
        "finish_time": "2026-10-02 10:00",
        "as_of_time": "2026-10-02 10:00",
        "delay_days": 1,
        "delay_hours": 10.0,
    }
    utilization_machine = {
        "machine_id": "M1",
        "machine_name": overlong_cell,
        "hours": 8.0,
        "task_count": 1,
        "capacity_hours": 8.0,
        "utilization": 1.0,
        "summed_load_hours": 8.0,
        "overlap_hours": 0.0,
        "outside_calendar_hours": 0.0,
        "metric_version": "v1",
        "reason": None,
    }
    downtime_machine = {
        "machine_id": "M1",
        "machine_name": overlong_cell,
        "downtime_hours": 2.0,
        "downtime_count": 1,
        "schedule_overlap_hours": 1.0,
        "schedule_overlap_count": 1,
    }
    review_row = {
        "batch_id_label": "B1",
        "operation_label": overlong_cell,
        "planned_start_time_label": "2026-10-01 08:00",
        "actual_start_time_label": "2026-10-01 08:00",
        "start_deviation_label": "0",
        "planned_end_time_label": "2026-10-01 10:00",
        "actual_end_time_label": "2026-10-01 10:00",
        "end_deviation_label": "0",
        "planned_resource_label": "M1",
        "actual_resource_label": "M1",
        "feedback_status_label": "已完工",
    }

    for call in (
        lambda: export_overdue_xlsx([overdue_item], summary_rows=[["计划编号", "P1"]], write_only=write_only),
        lambda: export_utilization_xlsx([utilization_machine], [], summary_rows=[["计划编号", "P1"]], write_only=write_only),
        lambda: export_downtime_impact_xlsx([downtime_machine], summary_rows=[["计划编号", "P1"]], write_only=write_only),
        lambda: export_execution_review_xlsx([review_row], summary_rows=[["计划编号", "P1"]], write_only=write_only),
        lambda: export_overdue_xlsx([], summary_rows=[["计划编号", overlong_cell]], write_only=write_only),
    ):
        with pytest.raises(WorkbenchCommandRejected) as exc_info:
            call()
        assert exc_info.value.code == "export_too_large"
        assert exc_info.value.status == 413


@pytest.mark.parametrize("write_only", [False, True])
def test_summary_identity_labels_preserve_raw_formula_prefix_and_strip_control_chars(write_only: bool) -> None:
    stream = export_overdue_xlsx(
        [],
        summary_rows=[
            ["计划编号", "=plan\x00-01"],
            ["数据版本编号", "+snap\x07-02"],
            ["筛选范围", "=not-an-identity"],
        ],
        write_only=write_only,
    )
    wb = openpyxl.load_workbook(io.BytesIO(stream.read()), read_only=True, data_only=False)
    try:
        rows = list(wb["查询摘要"].iter_rows(values_only=True))
    finally:
        wb.close()
    assert rows[1] == ("计划编号", "=plan-01")
    assert rows[2] == ("数据版本编号", "+snap-02")
    assert rows[3] == ("筛选范围", "'=not-an-identity")


def _openpyxl_temp_files() -> set:
    temp_dir = tempfile.gettempdir()
    return {
        os.path.join(temp_dir, name)
        for name in os.listdir(temp_dir)
        if name.startswith("openpyxl.")
    }


def test_write_only_xlsx_rejection_cleans_up_openpyxl_temp_files() -> None:
    overlong_cell = "x" * (XLSX_MAX_CELL_CHARS + 1)
    overdue_item = {
        "bucket_label": "已超期",
        "batch_id": "B1",
        "part_no": "P1",
        "part_name": overlong_cell,
        "quantity": 1,
        "due_date": "2026-10-01",
        "finish_time": "2026-10-02 10:00",
        "as_of_time": "2026-10-02 10:00",
        "delay_days": 1,
        "delay_hours": 10.0,
    }
    before_files = _openpyxl_temp_files()
    before_tracked = set(ALL_TEMP_FILES)

    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        export_overdue_xlsx([overdue_item], summary_rows=[["计划编号", "P1"]], write_only=True)

    assert exc_info.value.code == "export_too_large"
    assert _openpyxl_temp_files() - before_files == set()
    assert set(ALL_TEMP_FILES) - before_tracked == set()


def test_write_only_xlsx_save_oserror_is_not_masked_by_cleanup_and_leaves_no_temp_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overdue_item = {
        "bucket_label": "已超期",
        "batch_id": "B1",
        "part_no": "P1",
        "part_name": "轴承座",
        "quantity": 1,
        "due_date": "2026-10-01",
        "finish_time": "2026-10-02 10:00",
        "as_of_time": "2026-10-02 10:00",
        "delay_days": 1,
        "delay_hours": 10.0,
    }

    def fail_archive_write(self, filename, arcname=None, compress_type=None, compresslevel=None):
        raise OSError("simulated disk full")

    monkeypatch.setattr(zipfile.ZipFile, "write", fail_archive_write)
    before_files = _openpyxl_temp_files()
    before_tracked = set(ALL_TEMP_FILES)

    with pytest.raises(OSError, match="simulated disk full"):
        export_overdue_xlsx([overdue_item], summary_rows=[["计划编号", "P1"]], write_only=True)

    assert _openpyxl_temp_files() - before_files == set()
    assert set(ALL_TEMP_FILES) - before_tracked == set()


def test_write_only_xlsx_first_sheet_cleanup_failure_neither_masks_rejection_nor_skips_later_sheets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlong_cell = "x" * (XLSX_MAX_CELL_CHARS + 1)
    overdue_item = {
        "bucket_label": "已超期",
        "batch_id": "B1",
        "part_no": "P1",
        "part_name": overlong_cell,
        "quantity": 1,
        "due_date": "2026-10-01",
        "finish_time": "2026-10-02 10:00",
        "as_of_time": "2026-10-02 10:00",
        "delay_days": 1,
        "delay_hours": 10.0,
    }
    orig_cleanup = WorksheetWriter.cleanup
    cleanup_writers = []

    def flaky_cleanup(self: WorksheetWriter) -> None:
        cleanup_writers.append(self)
        if len(cleanup_writers) == 1:
            raise PermissionError("simulated first sheet cleanup lock")
        orig_cleanup(self)

    monkeypatch.setattr(WorksheetWriter, "cleanup", flaky_cleanup)
    before_files = _openpyxl_temp_files()
    before_tracked = set(ALL_TEMP_FILES)
    try:
        with pytest.raises(WorkbenchCommandRejected) as exc_info:
            export_overdue_xlsx([overdue_item], summary_rows=[["计划编号", "P1"]], write_only=True)

        assert exc_info.value.code == "export_too_large"
        assert exc_info.value.status == 413
        assert len(cleanup_writers) == 2
        second_sheet_temp = cleanup_writers[1].out
        assert not os.path.exists(second_sheet_temp)
        assert second_sheet_temp not in ALL_TEMP_FILES
    finally:
        for writer in cleanup_writers:
            if os.path.exists(writer.out):
                orig_cleanup(writer)

    assert _openpyxl_temp_files() - before_files == set()
    assert set(ALL_TEMP_FILES) - before_tracked == set()


def test_write_only_xlsx_writer_close_oserror_still_cleans_up_temp_files_and_preserves_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlong_cell = "x" * (XLSX_MAX_CELL_CHARS + 1)
    overdue_item = {
        "bucket_label": "已超期",
        "batch_id": "B1",
        "part_no": "P1",
        "part_name": overlong_cell,
        "quantity": 1,
        "due_date": "2026-10-01",
        "finish_time": "2026-10-02 10:00",
        "as_of_time": "2026-10-02 10:00",
        "delay_days": 1,
        "delay_hours": 10.0,
    }
    orig_close = WorksheetWriter.close
    closed_writers = []

    def fail_close_on_xml_flush(self: WorksheetWriter) -> None:
        closed_writers.append(self)
        orig_close(self)
        raise OSError("simulated disk full on XML flush")

    monkeypatch.setattr(WorksheetWriter, "close", fail_close_on_xml_flush)
    before_files = _openpyxl_temp_files()
    before_tracked = set(ALL_TEMP_FILES)

    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        export_overdue_xlsx([overdue_item], summary_rows=[["计划编号", "P1"]], write_only=True)

    assert exc_info.value.code == "export_too_large"
    assert exc_info.value.status == 413
    assert len(closed_writers) == 2
    for writer in closed_writers:
        assert not os.path.exists(writer.out)
        assert writer.out not in ALL_TEMP_FILES
    assert _openpyxl_temp_files() - before_files == set()
    assert set(ALL_TEMP_FILES) - before_tracked == set()

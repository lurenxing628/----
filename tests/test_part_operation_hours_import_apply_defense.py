from __future__ import annotations

import sqlite3

from core.services.common.excel_service import ImportPreviewRow, RowStatus
from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService


def _pr(data, *, status: RowStatus = RowStatus.UPDATE, row_num: int = 2) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def test_parse_write_row_accepts_integer_float_string_forms() -> None:
    parsed, err = PartOperationHoursExcelImportService._parse_write_row(
        _pr({"图号": "P001", "工序": 5.0, "换型时间(h)": 1.0, "单件工时(h)": 0.25})
    )
    assert err is None
    assert parsed == ("P001", 5, 1.0, 0.25)

    parsed, err = PartOperationHoursExcelImportService._parse_write_row(
        _pr({"图号": "P001", "工序": "5.0", "换型时间(h)": "1.0", "单件工时(h)": "0.25"})
    )
    assert err is None
    assert parsed == ("P001", 5, 1.0, 0.25)

    parsed, err = PartOperationHoursExcelImportService._parse_write_row(_pr({"图号": "P001", "工序": "5e0"}))
    assert parsed is None
    assert err is not None


def test_apply_preview_rows_turns_nan_inf_into_row_errors() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        svc = PartOperationHoursExcelImportService(conn)
        preview_rows = [
            _pr({"图号": "P001", "工序": 1, "换型时间(h)": float("nan"), "单件工时(h)": 0.1}, row_num=2),
            _pr({"图号": "P001", "工序": 2, "换型时间(h)": 0.2, "单件工时(h)": float("inf")}, row_num=3),
            _pr({"图号": "P001", "工序": 3, "换型时间(h)": "abc", "单件工时(h)": "0.1"}, row_num=4),
        ]
        stats = svc.apply_preview_rows(preview_rows)
        assert int(stats.get("total_rows", 0)) == 3, stats
        assert int(stats.get("new_count", 0)) == 0, stats
        assert int(stats.get("update_count", 0)) == 0, stats
        assert int(stats.get("skip_count", 0)) == 0, stats
        assert int(stats.get("error_count", 0)) == 3, stats

        errors_sample = stats.get("errors_sample") or []
        assert len(errors_sample) >= 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


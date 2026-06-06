"""回归测试：守护 PartOperationHoursExcelImportService.apply_preview_rows 的统计口径——UNCHANGED/SKIP 计入 skip_count、ERROR 计入 error_count，四类计数之和等于 total_rows；errors_sample 保留 source_row_num/source_sheet_name/message 等定位字段。"""

def test_part_operation_hours_service_stats_gate(mem_conn) -> None:
    from core.services.common.excel_service import ImportPreviewRow, RowStatus
    from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService

    conn = mem_conn
    try:
        svc = PartOperationHoursExcelImportService(conn)
        preview_rows = [
            ImportPreviewRow(row_num=2, status=RowStatus.UNCHANGED, data={"图号": "P001", "工序": 1}, message="无变更"),
            ImportPreviewRow(row_num=3, status=RowStatus.SKIP, data={"图号": "P001", "工序": 2}, message="跳过"),
            ImportPreviewRow(
                row_num=4,
                source_row_num=9,
                source_sheet_name="工时导入",
                status=RowStatus.ERROR,
                data={"图号": "", "工序": None},
                message="bad row",
            ),
        ]

        stats = svc.apply_preview_rows(preview_rows)
        assert int(stats.get("total_rows", 0)) == 3, stats
        assert int(stats.get("new_count", 0)) == 0, stats
        assert int(stats.get("update_count", 0)) == 0, stats
        assert int(stats.get("skip_count", 0)) == 2, stats
        assert int(stats.get("error_count", 0)) == 1, stats
        assert (
            int(stats.get("new_count", 0))
            + int(stats.get("update_count", 0))
            + int(stats.get("skip_count", 0))
            + int(stats.get("error_count", 0))
            == int(stats.get("total_rows", 0))
        ), stats

        errors_sample = list(stats.get("errors_sample") or [])
        assert len(errors_sample) == 1, stats
        sample = errors_sample[0]
        assert sample.get("row") == 9, sample
        assert sample.get("source_row_num") == 9, sample
        assert sample.get("source_sheet_name") == "工时导入", sample
        assert sample.get("message") == "bad row", sample

    finally:
        try:
            conn.close()
        except Exception:
            pass


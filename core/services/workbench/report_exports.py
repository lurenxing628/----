"""Download the entire snapshot cohort, using the existing safe XLSX renderer."""

from __future__ import annotations

import csv
import io

import openpyxl
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.common.excel_templates import _sanitize_export_cell
from core.services.report.exporters.xlsx import _append_write_only_row
from core.services.report.report_engine import ReportExport


def _value(value):
    if value is None:
        return "未知"
    if isinstance(value, dict) or isinstance(value, list) and any(isinstance(item, (dict, list)) for item in value):
        return canonical_json(value)
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    if isinstance(value, bool):
        return "是" if value else "否"
    return value


def metadata(data, snapshot):
    return [["数据来源", data["provenance"]], ["计划", data["plan"]["display_name"]],
            ["计划引用", data["plan"]["plan_ref"]], ["数据截至", snapshot["as_of"]],
            ["范围快照", snapshot["snapshot_ref"]], ["筛选范围", canonical_json(data["scope"])],
            ["数据缺口", "；".join(data["data_gaps"])]]


def ensure_export_size(engine, count):
    decision = engine._build_export_decision(count)
    if decision.mode == "reject_need_async":
        raise WorkbenchCommandRejected("export_too_large", "当前结果超出既有导出上限，请缩小筛选范围。", 413)
    return decision


def _export_values(columns, rows, format_name):
    values = [[_value(row.get(column["key"])) for column in columns] for row in rows]
    if format_name == "xlsx" and any(isinstance(value, str) and len(value) > 32767 for row in values for value in row):
        raise WorkbenchCommandRejected("export_too_large", "完整修订历史或原始资料超过 XLSX 单元格上限，请使用 CSV；未截断数据。", 413)
    return values


def _append_xlsx_metadata(sheet, data, snapshot):
    for label, value in metadata(data, snapshot):
        if label not in ("计划引用", "范围快照"):
            _append_write_only_row(sheet, [label, value])
            continue
        # References must round-trip exactly without ever becoming formulas.
        cells = [WriteOnlyCell(sheet, value=label), WriteOnlyCell(sheet, value=value)]
        cells[1].data_type = "s"
        for cell in cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        sheet.append(cells)


def export_table(engine, data, rows, snapshot, format_name):
    if format_name not in ("csv", "xlsx"):
        raise WorkbenchCommandRejected("invalid_input", "只支持 CSV 或 XLSX 导出。", 400)
    if not rows:
        raise WorkbenchCommandRejected("empty_export", "当前范围没有可导出的结果。", 422)
    decision = ensure_export_size(engine, len(rows))
    columns = data["columns"]
    values = _export_values(columns, rows, format_name)
    filename = "workbench-" + data["topic"] + "-" + snapshot["as_of"].replace(":", "")
    if format_name == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow([column["label"] for column in columns] + ["数据截至", "范围快照", "筛选范围", "数据来源", "数据缺口"])
        for row in values:
            writer.writerow([_sanitize_export_cell(value) for value in row + [snapshot["as_of"], snapshot["snapshot_ref"], canonical_json(data["scope"]), data["provenance"], "；".join(data["data_gaps"])]])
        return ReportExport(filename + ".csv", "text/csv;charset=utf-8", io.BytesIO(output.getvalue().encode("utf-8-sig")), estimated_rows=len(rows))
    workbook = openpyxl.Workbook(write_only=True)
    output = io.BytesIO()
    try:
        sheet = workbook.create_sheet("范围与口径")
        _append_xlsx_metadata(sheet, data, snapshot)
        for key, value in data["summary"].items():
            _append_write_only_row(sheet, [key, _value(value)])
        sheet = workbook.create_sheet("范围全部结果")
        _append_write_only_row(sheet, [column["label"] for column in columns], is_header=True)
        for row in values:
            _append_write_only_row(sheet, row)
        workbook.save(output)
        output.seek(0)
    finally:
        workbook.close()
    return ReportExport(filename + ".xlsx", engine.XLSX_CONTENT_TYPE, output, mode=decision.mode, estimated_rows=len(rows))

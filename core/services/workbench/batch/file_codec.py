"""Bytes-only first-sheet XLSX, explicit formulas rejection and typed output text."""

from io import BytesIO

from core.errors import ValidationError
from core.models.workbench_batch_file import (
    FILE_HEADERS,
    HEADERS,
    MAX_BYTES,
    MAX_ROWS,
    READONLY_HEADERS,
    table_descriptor,
)
from core.models.workbench_table_descriptor import cell_notes, extra_sheet_notice
from core.services.common.excel_instruction_sheet import add_enum_dropdowns, append_instruction_sheet
from core.services.workbench.facts.file_source import FileReadMessages, source_rows
from core.services.workbench.facts.file_writer import ILLEGAL

# 这里原本拿旧模板清单（excel_template_defaults）交叉校验一遍表头。那份清单 2026-09-21
# 随旧资料转换一起退役了，而表头本来就同源：表描述的列标签直接取自 HEADERS
# （core/models/workbench_batch_file.py 的 table_descriptor），用户下载到的模板由表描述现生成，
# 再比一次旧清单只是在校验一份没人再用的数据。

_READ_MESSAGES = FileReadMessages(
    csv_encoding="",
    csv_format="",
    xlsx_empty="Excel没有数据工作表。",
    xlsx_read="XLSX文件读取失败，请核对文件格式。",
    xlsx_cell="不能导入公式或错误单元格，请提供实际值。",
)


def _file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


def read_batch_file(content):
    if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
        raise ValidationError("请选择不超过10MB的有效批次XLSX文件。", field="file")
    state = {"sheets": 1}
    source = source_rows(content, "xlsx", state, error=_file_error, messages=_READ_MESSAGES)
    try:
        header = next(source, None)
        headers = header[1] if header is not None else []
        while headers and headers[-1] is None:
            headers.pop()
        reference_columns = [col for col in headers if col in READONLY_HEADERS]
        if (header is not None and header[2]) or len(headers) != len(set(headers)) or "批次号" not in headers or set(headers) - set(HEADERS + READONLY_HEADERS):
            raise ValidationError("表头必须包含批次号，其余请使用模板中的列名，不能有重复列或未知列。", field="headers")
        rows = []
        for line, values, cell_errors in source:
            if not cell_errors and all(v is None for v in values):
                continue
            if len(rows) == MAX_ROWS:
                raise ValidationError("一次最多导入 5000 行；这次一行都没有写入。", field="file")
            rows.append(_read_data_row(line, values, cell_errors, headers))
        # 多表提示与其余 11 张表同一句话，见 core/models/workbench_table_descriptor.py。
        warnings = extra_sheet_notice(state["sheets"])
        if "状态" in reference_columns:
            warnings.append({"code": "reference_column_ignored", "message": "文件中的“状态”仅供参考，不导入；已有批次保留当前状态，新批次从待排开始。"})
        if READONLY_HEADERS[1] in reference_columns:
            warnings.append({"code": "reference_column_ignored", "message": "文件中的“当前有效齐套（只读）”仅供参考，不导入；“维护齐套标记”保留原维护值，不会被有效齐套覆盖。"})
        return rows, warnings
    finally:
        source.close()


def _read_data_row(line, values, cell_errors, headers):
    errors = []
    if any(index < len(headers) and headers[index] in HEADERS for index in cell_errors):
        errors.append("不能导入公式或错误单元格，请提供实际值。")
    if any(v is not None for v in values[len(headers):]) or any(index >= len(headers) for index in cell_errors):
        errors.append("数据行里有表头之外的多余列。")
    parsed = {key: values[index] if index < len(values) else None for index, key in enumerate(headers) if key in HEADERS}
    return {"row": line, "values": parsed, "errors": errors}


def write_batch_file(rows):
    import openpyxl
    from openpyxl.cell.cell import TYPE_STRING
    from openpyxl.comments import Comment
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    if len(rows) > MAX_ROWS:
        raise ValidationError("单次导出超过5000行，请缩小范围。", field="scope")
    descriptor = table_descriptor()
    notes = cell_notes(descriptor)
    workbook = openpyxl.Workbook()
    sheet = workbook.worksheets[0]
    sheet.title = descriptor["sheet_name"]
    sheet.freeze_panes = "A2"
    headers = FILE_HEADERS
    sheet.append(headers)
    for index, _header in enumerate(headers, 1):
        cell = sheet.cell(1, index)
        cell.font = Font(bold=True)
        if index <= len(notes):
            cell.comment = Comment(notes[index - 1], "APS")
        sheet.column_dimensions[get_column_letter(index)].width = (22 if index < 3 else 16) if index != 8 else 36
    for number, row in enumerate(rows, 2):
        for index, value in enumerate(row, 1):
            if isinstance(value, str) and (ILLEGAL.search(value) or len(value) > 32767):
                raise ValidationError("这段文字里有 Excel 放不了的字符，或者太长；系统没有删除或截断内容。", field="file")
            cell = sheet.cell(number, index, value)
            if isinstance(value, str):
                cell.data_type = TYPE_STRING
                cell.number_format = "@"
    sheet.auto_filter.ref = "A1:" + get_column_letter(len(headers)) + str(max(1, len(rows) + 1))
    add_enum_dropdowns(sheet, descriptor, len(rows), write_only=False)
    append_instruction_sheet(workbook, descriptor)
    try:
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
    finally:
        workbook.close()

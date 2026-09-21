"""严格解析 CSV/XLSX。空格子表示不修改，转义空值表示明确清除。规则与资源文件家族逐条对齐。"""

import csv
import re
from io import BytesIO, StringIO

import openpyxl

from core.errors import ValidationError
from core.models.workbench_relation_file import (
    IMPORT_ROW_LIMIT,
    REQUIRED,
    file_columns,
    public_columns,
    relation_kind,
)
from core.models.workbench_table_descriptor import extra_sheet_notice

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


def _source_rows(content, fmt, state):
    if fmt == "csv":
        reader = None
        try:
            reader = csv.reader(StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
            while True:
                number = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    return
                yield number, row, {}
        except (UnicodeDecodeError, csv.Error) as exc:
            raise file_error("这个 CSV 不是 UTF-8 编码，或者引号不成对，一行都没有导入。请另存为 UTF-8 编码后重新上传。",
                             reader.line_num if reader else 1) from exc
    else:
        wb = None
        try:
            wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
            if not wb.worksheets:
                raise file_error("这个 XLSX 里没有工作表，没有导入。请确认文件完整后重新上传。")
            # 只读第一张表，其余忽略；模板和导出文件本身就带一张「填写说明」。
            state["sheets"] = len(wb.worksheets)
            ws = wb.worksheets[0]
            ws.reset_dimensions()
            for number, cells in enumerate(ws.iter_rows(), 1):
                errors = {i: "这个格子是公式或者显示为错误值，没有导入。请改成纯文本后重新上传。"
                          for i, cell in enumerate(cells) if cell.data_type in ("f", "e")}
                yield number, [cell.value for cell in cells], errors
        except ValidationError:
            raise
        except Exception as exc:
            raise file_error("这个 XLSX 打不开，没有导入。请确认文件完整后重新上传。") from exc
        finally:
            if wb is not None:
                wb.close()


def _headers(kind, values):
    names = {column["label"]: column["key"] for column in public_columns(kind)}
    names.update({key: key for key in file_columns(kind)})
    fields = []
    for value in values:
        if type(value) is not str or value not in names:
            raise file_error("表头里有认不出的列或者空列，没有导入。请照模板里的列名填写。", field="headers")
        fields.append(names[value])
    missing = [key for key in REQUIRED[kind] if key not in fields]
    if missing or len(fields) != len(set(fields)):
        raise file_error("表头必须有工号和设备编号这两列，而且不能有重复的列（中文名和英文名指同一列也算重复），"
                         "没有导入。请照模板改好后重新上传。", field="headers")
    return fields


def _decode(value, fmt):
    if type(value) is str:
        if fmt == "csv" and value.startswith("'"):
            value = value[1:]
        if value == r"\N":
            return None
        if value.startswith("\\\\"):
            value = value[1:]
    return value


def _parse(number, values, errors, fields, fmt):
    parsed, issues = {}, []
    if len(values) > len(fields) and any(v is not None and v != "" for v in values[len(fields):]):
        issues.append({"row": number, "field": "columns", "code": "invalid_input",
                       "message": "这一行的列数比表头多，多出来的内容没有导入。请删掉多余的列。"})
    for index, field in enumerate(fields):
        value = values[index] if index < len(values) else None
        try:
            if index in errors:
                raise ValidationError(errors[index], field=field)
            if value is not None and value != "":
                parsed[field] = _decode(value, fmt)
        except ValidationError as exc:
            issues.append({"row": number, "field": field, "code": "invalid_input", "message": exc.message})
    return {"row": number, "values": parsed, "errors": issues}


def read_relation_file(kind, content, fmt):
    relation_kind(kind)
    if type(content) is not bytes or fmt not in ("csv", "xlsx"):
        raise file_error("只能导入 CSV 或 XLSX 文件，没有导入。请重新选择文件。")
    state = {"sheets": 1}
    source = _source_rows(content, fmt, state)
    try:
        header = next(source, None)
        if header is None or header[2]:
            raise file_error("文件第一行不是表头，没有导入。请照模板补上表头行。", field="headers")
        fields = _headers(kind, header[1])
        rows = []
        for number, values, errors in source:
            if not errors and all(value is None or value == "" for value in values):
                continue
            if len(rows) == IMPORT_ROW_LIMIT:
                raise file_error("一次最多导入 2000 行，这个文件超了，一行都没有导入。请拆成几个小文件分次上传。", number)
            rows.append(_parse(number, values, errors, fields, fmt))
        return rows, extra_sheet_notice(state["sheets"])
    finally:
        source.close()

"""Strict CSV/XLSX decoding; blank cells omit, escaped nulls remain explicit."""

import csv
import json
import re
from io import BytesIO, StringIO

import openpyxl

from core.errors import ValidationError
from core.models.workbench_resource_file import (
    IMPORT_ROW_LIMIT,
    JSON_FIELDS,
    MULTI_CODES,
    NUMERIC_FIELDS,
    file_columns,
    public_columns,
)

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


def _source_rows(content, fmt):
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
            raise file_error("CSV必须是有效UTF-8，不能猜编码或修补引号。", reader.line_num if reader else 1) from exc
    else:
        wb = None
        try:
            wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
            if len(wb.sheetnames) != 1 or len(wb.worksheets) != 1:
                raise file_error("文件只能包含一张数据工作表，不能忽略其他表。")
            ws = wb.worksheets[0]
            ws.reset_dimensions()
            for number, cells in enumerate(ws.iter_rows(), 1):
                errors = {i: "不接受公式或Excel错误单元格。" for i, cell in enumerate(cells) if cell.data_type in ("f", "e")}
                yield number, [cell.value for cell in cells], errors
        except ValidationError:
            raise
        except Exception as exc:
            raise file_error("XLSX读取失败，请核对文件字节。") from exc
        finally:
            if wb is not None:
                wb.close()


def _headers(kind, values):
    names = {column["label"]: column["key"] for column in public_columns(kind)}
    names.update({key: key for key in file_columns(kind)})
    fields = []
    for value in values:
        if type(value) is not str or value not in names:
            raise file_error("表头含未知字段或空列。", field="headers")
        fields.append(names[value])
    if "business_code" not in fields or len(fields) != len(set(fields)):
        raise file_error("表头必须包含编号且不得重复（含中英文同义列）。", field="headers")
    return fields


def _decode(value, field, fmt):
    if type(value) is str:
        if fmt == "csv" and value.startswith("'"):
            value = value[1:]
        if value == r"\N":
            return None
        if value.startswith("\\\\"):
            value = value[1:]
    if field in JSON_FIELDS:
        value = _decode_json(value, field)
    if field in NUMERIC_FIELDS and fmt == "csv":
        if type(value) is not str or NUMBER.fullmatch(value) is None:
            raise ValidationError("数值不能混入单位、布尔值或分组逗号。", field=field)
        value = float(value)
    return value


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _decode_json(value, field):
    if type(value) is not str:
        raise ValidationError("该单元格必须明确填写JSON文本。", field=field)
    try:
        value = json.loads(value, object_pairs_hook=_unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, TypeError) as exc:
        raise ValidationError("该单元格必须是有效且无重复键的JSON，不猜逗号分隔。", field=field) from exc
    if field in MULTI_CODES:
        if type(value) is not list or any(type(code) is not str for code in value):
            raise ValidationError("多值必须是JSON字符串数组。", field=field)
        if len(value) != len(set(value)):
            raise ValidationError("编号数组不能重复。", field=field)
    return value


def _parse(number, values, errors, fields, fmt):
    parsed, issues = {}, []
    if len(values) > len(fields) and any(v is not None and v != "" for v in values[len(fields):]):
        issues.append({"row": number, "field": "columns", "code": "invalid_input", "message": "数据行包含未声明的多余列。"})
    for index, field in enumerate(fields):
        value = values[index] if index < len(values) else None
        try:
            if index in errors:
                raise ValidationError(errors[index], field=field)
            if value is not None and value != "":
                parsed[field] = _decode(value, field, fmt)
        except ValidationError as exc:
            issues.append({"row": number, "field": field, "code": "invalid_input", "message": exc.message})
    return {"row": number, "values": parsed, "errors": issues}


def read_resource_file(kind, content, fmt):
    if type(content) is not bytes or fmt not in ("csv", "xlsx"):
        raise file_error("必须提供CSV/XLSX原始字节。")
    source = _source_rows(content, fmt)
    try:
        header = next(source, None)
        if header is None or header[2]:
            raise file_error("文件缺少有效表头。", field="headers")
        fields = _headers(kind, header[1])
        rows = []
        for number, values, errors in source:
            if not errors and all(value is None or value == "" for value in values):
                continue
            if len(rows) == IMPORT_ROW_LIMIT:
                raise file_error("单次最多导入2000行，未截断或写入前半部分。", number)
            rows.append(_parse(number, values, errors, fields, fmt))
        return rows
    finally:
        source.close()

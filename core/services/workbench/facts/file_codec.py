"""Strict CSV/XLSX decoding; blank cells omit, escaped nulls remain explicit."""

import re

from core.errors import ValidationError
from core.models.workbench_resource_file import (
    ENUM_CODES,
    ENUM_LABELS,
    IMPORT_ROW_LIMIT,
    MULTI_CODES,
    NUMERIC_FIELDS,
    PAGE_STATUS_LABELS,
    READONLY,
    column_label,
    public_columns,
    status_words,
)
from core.models.workbench_table_descriptor import extra_sheet_notice
from core.services.workbench.facts.file_source import source_rows

from .file_lists import decode_code_list

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


def _headers(kind, values):
    """表头只认导出和模板写出的中文列名。"""
    names = {column["label"]: column["key"] for column in public_columns(kind)}
    fields = []
    for value in values:
        if type(value) is not str or value not in names:
            raise file_error("表头里有认不出的列或者空列，没有导入。请照模板里的列名填写。", field="headers")
        fields.append(names[value])
    if "business_code" not in fields or len(fields) != len(set(fields)):
        raise file_error("表头必须有编号这一列，而且不能有重复的列，没有导入。请照模板改好后重新上传。", field="headers")
    return fields


def _enum_labels(kind, field):
    """导出写出的中文标签；状态另认页面上的叫法（填写说明里写明了），不认英文代号。"""
    labels = {ENUM_LABELS[field][code]: code for code in ENUM_CODES[kind][field]}
    if field == "status":
        labels.update(PAGE_STATUS_LABELS.get(kind, {}))
    return labels


def _decode_enum(kind, value, field):
    labels = _enum_labels(kind, field)
    if type(value) is not str or value not in labels:
        words = status_words(kind) if field == "status" else "或".join(ENUM_LABELS[field][code] for code in ENUM_CODES[kind][field])
        raise ValidationError("「" + column_label(kind, field) + "」这一列只能填" + words
                              + "，这一行没有导入。请照下拉选项填写。", field=field)
    return labels[value]


def _decode(kind, value, field, fmt):
    if type(value) is str:
        if fmt == "csv" and value.startswith("'"):
            value = value[1:]
            if value == "":
                return value
        if value == r"\N":
            return None
        if value.startswith("\\\\"):
            value = value[1:]
        if not value.strip():
            raise ValidationError("这一格只填了空格。留空表示保持原样，要清除请填 \\N。", field=field)
    if field in MULTI_CODES:
        value = decode_code_list(value, field)
    elif field in ENUM_CODES[kind]:
        value = _decode_enum(kind, value, field)
    # 导出的 XLSX 把数字写成文本格（保住全部有效数字），所以 XLSX 里的文本数字和 CSV 一样按数字读。
    if field in NUMERIC_FIELDS and (fmt == "csv" or type(value) is str):
        if type(value) is not str or NUMBER.fullmatch(value) is None:
            raise ValidationError("这个格子只能填数字，不能带单位、是或否、千分位逗号，没有导入。请改成纯数字。", field=field)
        value = float(value)
    return value


def _parse(kind, number, values, errors, fields, fmt, readonly):
    parsed, issues = {}, []
    if len(values) > len(fields) and any(v is not None and v != "" for v in values[len(fields):]):
        issues.append({"row": number, "field": "columns", "code": "invalid_input", "message": "这一行的列数比表头多，多出来的内容没有导入。请删掉多余的列。"})
    for index, field in enumerate(fields):
        value = values[index] if index < len(values) else None
        try:
            if field in readonly:
                if value is not None and value != "":
                    parsed[field] = value
                continue
            if index in errors:
                raise ValidationError(errors[index], field=field)
            if value is not None and value != "":
                # 只读列不参与解析：它们的值根本不会被导入，却因为 NUMERIC_FIELDS 等
                # 是按列名而不是按表分的，跟着可填列一起被校验——导出的「原技能明细（只读）」
                # 在 Excel 里被重排一下，回导整行就被拒。
                # 但键必须留下：file_input._declares_empty_skills 靠 skills_declared 这个键
                # 在不在，区分「导出回导、空技能列表保持不变」和「明确声明没有技能」。
                value = _decode(kind, value, field, fmt)
                # CSV 的防公式前缀剥掉后只剩空串，也按空格子省略；None 仍是显式清除。
                if value != "":
                    parsed[field] = value
        except ValidationError as exc:
            issues.append({"row": number, "field": field, "code": "invalid_input", "message": exc.message})
    return {"row": number, "values": parsed, "errors": issues}


def read_resource_file(kind, content, fmt):
    if type(content) is not bytes or fmt not in ("csv", "xlsx"):
        raise file_error("只能导入 CSV 或 XLSX 文件，没有导入。请重新选择文件。")
    state = {"sheets": 1}
    source = source_rows(content, fmt, state, error=file_error)
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
            rows.append(_parse(kind, number, values, errors, fields, fmt, READONLY[kind]))
        return rows, extra_sheet_notice(state["sheets"])
    finally:
        source.close()

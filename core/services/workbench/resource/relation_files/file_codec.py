"""严格解析 CSV/XLSX。空格子表示不修改，转义空值表示明确清除。规则与资源文件家族逐条对齐。"""



from core.errors import ValidationError
from core.models.workbench_relation_file import (
    IMPORT_ROW_LIMIT,
    REQUIRED,
    file_columns,
    public_columns,
    relation_kind,
)
from core.models.workbench_table_descriptor import extra_sheet_notice
from core.services.workbench.facts.file_source import source_rows


def file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


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
            rows.append(_parse(number, values, errors, fields, fmt))
        return rows, extra_sheet_notice(state["sheets"])
    finally:
        source.close()

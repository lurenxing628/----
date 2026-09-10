"""Pure bytes codec, with no DB, process parsing, preview or write authority.

decode_process_file(kind, content, fmt) -> list of
{row: source line (CSV physical start line / XLSX row), values: sparse canonical
mapping, errors: [{row, field, code, message}]}. File/header/limit failures raise
ValidationError with details.row. All duplicate-key occurrences are diagnosed.
Never partially apply this list: the caller must reject a batch with any errors.

encode_process_file(kind, rows, fmt) -> ProcessFileDownload. Rows is a one-pass
iterable of canonical mappings, not decoded row envelopes; [] emits headers only.
No import cap applies to exports. Missing keys and empty strings emit blanks;
None emits \\N. Literal leading backslashes are doubled. CSV prefixes every
nonempty cell with one reversible apostrophe. XLSX explicitly types text,
including decimal numbers to preserve precision. Source exports use Chinese.
Hours/days decode to finite floats; sequence/group bounds to exact positive
int64 (text digits or safe XLSX integers). Null legality and group/source/name
assertions belong to the domain; this codec never fills absent fields.
"""

from core.errors import ValidationError
from core.models.workbench_process_file import (
    IMPORT_ROW_LIMIT,
    INSTRUCTIONS,
    LABELS,
    REQUIRED,
    TEMPLATE_VERSION,
    check_format,
    file_columns,
    file_error,
    public_columns,
)
from core.services.workbench.process_file_reader import check_bytes, csv_rows, xlsx_rows
from core.services.workbench.process_file_values import decode_value, numeric_diagnostic
from core.services.workbench.process_file_writer import write_csv, write_xlsx

__all__ = ["decode_process_file", "encode_process_file", "public_columns", "file_columns", "TEMPLATE_VERSION", "INSTRUCTIONS"]


def _headers(kind, values):
    names = {LABELS[field]: field for field in file_columns(kind)}
    names.update({field: field for field in file_columns(kind)})
    fields = []
    for value in values:
        if type(value) is not str or value not in names:
            raise file_error("表头含未知字段或空列，只能使用已定义的工艺字段。", field="headers")
        fields.append(names[value])
    if len(set(fields)) != len(fields):
        raise file_error("表头包含重复字段（含中英文同义列）。", field="headers")
    for field in REQUIRED[kind]:
        if field not in fields:
            raise file_error("表头缺少" + LABELS[field] + "列。", field="headers")
    return fields


def _issue(row, field, message, code="invalid_input"):
    row["errors"].append({"row": row["row"], "field": field, "code": code, "message": message})


def _parse_row(kind, number, values, cell_errors, fields, file_format):
    row = {"row": number, "values": {}, "errors": []}
    if len(values) > len(fields):
        _issue(row, "columns", "数据行包含未声明的多余列，不能忽略。")
    for index, field in enumerate(fields):
        value = values[index] if index < len(values) else None
        if index in cell_errors:
            _issue(row, field, cell_errors[index])
        elif value is not None and value != "":
            try:
                parsed = decode_value(value, field, number, file_format)
                row["values"][field] = parsed
                message = numeric_diagnostic(field, parsed)
                if message:
                    _issue(row, field, message)
            except ValidationError as exc:
                _issue(row, field, exc.message)
    for field in REQUIRED[kind]:
        value = row["values"].get(field)
        if (value is None or type(value) is str and not value.strip()) and not any(e["field"] == field for e in row["errors"]):
            _issue(row, field, LABELS[field] + "不能为空，不能忽略空记录。")
    return row


def _duplicates(kind, rows):
    occurrences = {}
    for row in rows:
        key = tuple(row["values"].get(field) for field in REQUIRED[kind])
        if any(value is None or type(value) is str and not value.strip() for value in key):
            continue
        occurrences.setdefault(key, []).append(row)
    for repeated in occurrences.values():
        if len(repeated) > 1:
            first = repeated[0]["row"]
            for row in repeated:
                _issue(row, REQUIRED[kind][-1], "同一图号" + ("和工序" if kind == "hours" else "")
                       + "在文件中重复，首次出现在第 " + str(first) + " 行。", "duplicate_entry")


def decode_process_file(kind, content, fmt):
    file_columns(kind)
    check_format(fmt)
    check_bytes(content, fmt)
    source = csv_rows(content) if fmt == "csv" else xlsx_rows(content)
    try:
        header = next(source, None)
        if header is None or header[2]:
            raise file_error("文件缺少有效表头。", field="headers")
        fields = _headers(kind, header[1])
        rows = []
        for number, values, errors in source:
            if len(rows) == IMPORT_ROW_LIMIT:
                raise file_error("单次最多导入 2000 行，未截断或导入前半部分。", number)
            rows.append(_parse_row(kind, number, values, errors, fields, fmt))
        _duplicates(kind, rows)
        return rows
    finally:
        source.close()


def encode_process_file(kind, rows, fmt):
    file_columns(kind)
    check_format(fmt)
    return write_csv(kind, rows) if fmt == "csv" else write_xlsx(kind, rows)

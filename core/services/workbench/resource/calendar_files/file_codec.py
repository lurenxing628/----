"""严格解析日历文件。空格子表示不修改，转义空值表示明确清除。

文本日期与批次导入采用相同的年月日格式。Excel 原生 datetime 的既有政策不同：
日历只接受午夜，批次导入取日期部分；这里保留日历的拒绝规则，不静默截去时间。
"""

import re
from datetime import date, datetime, time

from core.errors import ValidationError
from core.models.workbench_calendar_file import (
    IMPORT_ROW_LIMIT,
    REQUIRED,
    calendar_kind,
    file_columns,
    public_columns,
)
from core.models.workbench_table_descriptor import extra_sheet_notice
from core.services.workbench.facts.file_source import source_rows

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
DATE_TEXT = re.compile(r"([0-9]{4})[/-]([0-9]{1,2})[/-]([0-9]{1,2})\Z")


def file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


def read_date(value, field="date"):
    """接受文本日期与 Excel 日期格子；带时间的文本一律拒绝，不做截断。"""
    if type(value) is datetime:
        if value.time() != time(0, 0):
            raise ValidationError("日期里不能带时间，请只填年月日。", field=field)
        return value.date().isoformat()
    if type(value) is date:
        return value.isoformat()
    if type(value) is not str:
        raise ValidationError("日期必须填成 2026-10-01 这样的年月日。", field=field)
    text = value.strip()
    if "T" in text or " " in text:
        raise ValidationError("日期里不能带时间，请只填年月日。", field=field)
    matched = DATE_TEXT.match(text)
    if matched is None:
        raise ValidationError("日期必须填成 2026-10-01 或 2026/10/1 这样的年月日。", field=field)
    try:
        return date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3))).isoformat()
    except ValueError as exc:
        raise ValidationError("这个日期不存在，请核对年月日。", field=field) from exc


def read_clock(value, field="clock"):
    """接受文本时刻与 Excel 时间格子，与 read_date 对称。

    原来时刻列直接调界面输入模型 operator_clock（只收 str），而同一份文件里日期列走
    read_date（接受原生日期格子），同一个 codec 里两套标准：用户把班次起止填成 Excel
    的时间格式，文件就被拒，而他在界面上看到的是 08:00。

    这里只做归一，归一完仍交 operator_clock 做最终校验——界面输入模型不为文件格式让步。
    秒和微秒非零一律拒绝，不做截断（"分钟到分为止"是既有合同）；带日期的格子也拒绝，
    悄悄丢掉用户填的日期属于静默改值。
    """
    if type(value) is datetime:
        raise ValidationError("这一格里带了日期，班次起止只填时刻，比如 08:00。", field=field)
    if type(value) is time:
        if value.second or value.microsecond:
            raise ValidationError("时刻只到分钟，请把秒去掉。", field=field)
        return f"{value.hour:02d}:{value.minute:02d}"
    if type(value) is str:
        return value.strip()
    raise ValidationError("时刻必须填成 08:00 这样的 24 小时制，分钟到分为止。", field=field)


def read_number(value, field):
    if type(value) is bool:
        raise ValidationError("这一项必须填数字。", field=field)
    if type(value) in (int, float):
        return float(value)
    if type(value) is str and NUMBER.match(value.strip()) is not None:
        return float(value.strip())
    raise ValidationError("这一项必须填数字。", field=field)


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
        raise file_error("表头必须有日期这一列，而且不能有重复的列（中文名和英文名指同一列也算重复），"
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


def read_calendar_file(kind, content, fmt):
    calendar_kind(kind)
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
                raise file_error("一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行，这个文件超了，一行都没有导入。"
                                 "请拆成几个小文件分次上传。", number)
            rows.append(_parse(number, values, errors, fields, fmt))
        return rows, extra_sheet_notice(state["sheets"])
    finally:
        source.close()

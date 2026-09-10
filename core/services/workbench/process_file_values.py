"""Cell types and reversible resource-file escaping; never infer process facts."""

import math
import re
from decimal import Decimal
from typing import cast

from core.models.workbench_process_file import (
    INT64_MAX,
    INTEGER_FIELDS,
    LABELS,
    NUMBER_FIELDS,
    SOURCE_LABELS,
    SOURCE_VALUES,
    XLSX_EXACT_INTEGER_MAX,
    file_error,
)
from core.services.workbench.resource_file_codec import NUMBER

_INTEGER = re.compile(r"[0-9]+\Z")
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
XLSX_MAX_CELL_CHARACTERS = 32767


def _integer(value, field, number, file_format):
    if type(value) is str:
        if _INTEGER.fullmatch(value) is None:
            raise file_error(LABELS[field] + "必须填写正整数，不接受小数、科学记数法或单位。", number, field)
        digits = value.lstrip("0")
        if len(digits) > 19:
            raise file_error(LABELS[field] + "超过 64 位整数范围。", number, field)
        value = int(digits or "0")
    elif type(value) not in (int, float) or type(value) is float and (not math.isfinite(value) or value != int(value)):
        raise file_error(LABELS[field] + "必须是正整数，不能混入布尔值。", number, field)
    elif file_format == "xlsx" and value > XLSX_EXACT_INTEGER_MAX:
        raise file_error(LABELS[field] + "超过 Excel 数值精确范围，请在原始文件中使用文本数字；未猜测原值。", number, field)
    if not 1 <= value <= INT64_MAX:
        raise file_error(LABELS[field] + "必须在 1 到 9223372036854775807 之间。", number, field)
    return int(value)


def _number(value, field, number):
    if type(value) is str:
        valid = NUMBER.fullmatch(value) is not None
    else:
        valid = type(value) in (int, float)
    try:
        result = float(value) if valid else float("nan")
    except (ValueError, OverflowError):
        result = float("nan")
    if not math.isfinite(result):
        raise file_error(LABELS[field] + "必须是有限数值，不能混入布尔值、单位、公式或分组逗号。", number, field)
    if result == 0 and type(value) is str and not Decimal(value).is_zero():
        raise file_error(LABELS[field] + "过小，不能精确表示为非零数值；未转换成零。", number, field)
    return result


def typed_value(value, field, number, file_format):
    if value is None:
        return None
    if field in INTEGER_FIELDS:
        return _integer(value, field, number, file_format)
    if field in NUMBER_FIELDS:
        return _number(value, field, number)
    if type(value) is not str:
        raise file_error(LABELS[field] + "必须是文本，不能猜测数字或日期原文。", number, field)
    _check_text(value, field, number, file_format)
    if field == "source":
        if value not in SOURCE_VALUES:
            raise file_error("归属只能填写自制或外协。", number, field)
        return SOURCE_VALUES[value]
    return value


def decode_value(value, field, number, file_format):
    if type(value) is str:
        if file_format == "csv" and value.startswith("'"):
            value = value[1:]
        if value == r"\N":
            return None
        if value.startswith("\\\\"):
            value = value[1:]
    return typed_value(value, field, number, file_format)


def numeric_diagnostic(field, value):
    if value is None or field not in NUMBER_FIELDS:
        return None
    if field in ("setup_hours", "unit_hours") and value < 0:
        return LABELS[field] + "不能为负数，未改成零。"
    if field in ("external_days", "group_total_days") and value <= 0:
        return LABELS[field] + "必须为正数，未自动补周期。"
    return None


def _check_text(value, field, number, file_format):
    if file_format == "xlsx" and (_ILLEGAL_XML.search(value) or len(value) > XLSX_MAX_CELL_CHARACTERS):
        raise file_error("文字含 XLSX 不支持的字符或超过单元格 32767 字符容量，未截断。", number, field)
    if file_format == "csv":
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise file_error("文字不能完整编码为 UTF-8，未替换原文。", number, field) from exc
        if "\x00" in value:
            raise file_error("CSV 工具链不支持 NUL 字符，未删除原文。", number, field)


def export_value(value, field, number, file_format) -> str:
    if value is None:
        return r"\N"
    # Exported numbers are textual decimal values: openpyxl's numeric writer
    # rounds floats and large integers. Text preserves their exact input value.
    normalized = typed_value(value, field, number, "csv")
    if field in INTEGER_FIELDS or field in NUMBER_FIELDS:
        text = str(normalized)
    else:
        text = cast(str, normalized)
        if field == "source":
            text = SOURCE_LABELS[text]
        elif text.startswith("\\"):
            text = "\\" + text
    _check_text(text, field, number, file_format)
    return text

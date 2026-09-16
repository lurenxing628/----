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
            raise file_error(LABELS[field] + "的数字太大，超出可用范围。请填小一些的整数。", number, field)
        value = int(digits or "0")
    elif type(value) not in (int, float) or type(value) is float and (not math.isfinite(value) or value != int(value)):
        raise file_error(LABELS[field] + "必须是正整数，不能填 TRUE 或 FALSE。", number, field)
    elif file_format == "xlsx" and value > XLSX_EXACT_INTEGER_MAX:
        raise file_error(LABELS[field] + "超出 Excel 能精确表示的范围，系统不猜原值。请把这个格子改成文本格式再填。", number, field)
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
        raise file_error(LABELS[field] + "必须是有限数字，不能填 TRUE、FALSE、单位、公式或带千分位逗号。", number, field)
    if result == 0 and type(value) is str and not Decimal(value).is_zero():
        raise file_error(LABELS[field] + "的数值精度超出支持范围，请调整数值。", number, field)
    return result


def typed_value(value, field, number, file_format):
    if value is None:
        return None
    if field in INTEGER_FIELDS:
        return _integer(value, field, number, file_format)
    if field in NUMBER_FIELDS:
        return _number(value, field, number)
    if type(value) is not str:
        raise file_error(LABELS[field] + "必须填文本，系统不猜你写的是数字还是日期。请把这个格子改成文本格式再填。", number, field)
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
        return LABELS[field] + "不能填负数。"
    if field in ("external_days", "group_total_days") and value <= 0:
        return LABELS[field] + "必须填正数。"
    return None


def _check_text(value, field, number, file_format):
    if file_format == "xlsx" and (_ILLEGAL_XML.search(value) or len(value) > XLSX_MAX_CELL_CHARACTERS):
        raise file_error("这段文字含 XLSX 不支持的字符，或者超过单元格 32767 字上限。请缩短后重新导入。", number, field)
    if file_format == "csv":
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise file_error("这段文字存不成 UTF-8。请改掉特殊字符后重新导入。", number, field) from exc
        if "\x00" in value:
            raise file_error("这段文字含 CSV 不支持的空字符。请改掉后重新导入。", number, field)


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

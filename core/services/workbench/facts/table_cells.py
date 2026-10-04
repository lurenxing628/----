"""One canonical business-cell representation for facets, equality and ordering."""

import math
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint


def text_value(value):
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


@dataclass(frozen=True)
class TableCell:
    key: str
    label: str
    order: tuple


def text_cell(value, *, missing="未知"):
    if value is None:
        return TableCell(input_fingerprint({"type": "text", "value": None}), missing, (0, ""))
    value = text_value(value)
    return TableCell(input_fingerprint({"type": "text", "value": value}), value or "（空白）", (1, value))


def number_text(value):
    """页面和导出文件共用的数字写法：能原样还原的最短十进制，7 不写成 7.0，也不用 1e-07 这种科学计数法。"""
    if type(value) is int:
        return str(value)
    return format(Decimal(repr(value)).normalize(), "f")


def number_cell(value, unit="", *, missing="未知"):
    if value is None:
        return TableCell(input_fingerprint({"type": "number", "value": None}), missing, (0, 0))
    if type(value) not in (int, float) or not math.isfinite(value):
        raise WorkbenchCommandRejected("storage_failure", "这个格子里存的数字不合法，没有显示成 0。请到资料总览核对后重试。", 500)
    number = number_text(value)
    unit = text_value(unit) if unit else ""
    return TableCell(input_fingerprint({"type": "number", "value": number, "unit": unit}),
                     number + (" " + unit if unit else ""), (1, value))


def relation_cell(labels):
    values = sorted(text_value(label) for label in labels)
    return TableCell(input_fingerprint({"type": "relations", "value": values}), "、".join(values) or "未选", (1, tuple(values)))


def status_cell(kind, status):
    labels = {"active": "启用", "inactive": "停用", "maintain": "停机", "leave": "请假", "pending_review": "待复核"}
    labels["active"] = {"machine": "可用", "operator": "在岗"}.get(kind, "启用")
    # All unidentified old values have the same visible business status, without rewriting them.
    label = labels.get(status, "旧状态 / 原因未知")
    return text_cell(label)

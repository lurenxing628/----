"""One canonical business-cell representation for facets, equality and ordering."""

from dataclasses import dataclass, replace
from decimal import Decimal

from core.models.enums import RESOURCE_STATUS_RANKS
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_status import table_status_label
from core.shared.strict_json import canonical_json
from core.shared.strict_parse import is_exact_finite_number
from core.shared.text_keys import text_key


@dataclass(frozen=True)
class TableCell:
    key: str
    label: str
    order: tuple


def text_cell(value, *, missing="未知"):
    if value is None:
        return TableCell(canonical_json({"type": "text", "value": None}), missing, (0, ""))
    value = text_key(value)
    return TableCell(canonical_json({"type": "text", "value": value}), value or "（空白）", (1, value))


def number_text(value):
    """页面和导出文件共用的数字写法：能原样还原的最短十进制，7 不写成 7.0，也不用 1e-07 这种科学计数法。"""
    if type(value) is int:
        return str(value)
    return format(Decimal(repr(value)).normalize(), "f")


def number_cell(value, unit="", *, missing="未知"):
    if value is None:
        return TableCell(canonical_json({"type": "number", "value": None}), missing, (0, 0))
    if not is_exact_finite_number(value):
        raise WorkbenchCommandRejected("storage_failure", "这个格子里存的数字不合法，没有显示成 0。请到资料总览核对后重试。", 500)
    number = number_text(value)
    unit = text_key(unit) if unit else ""
    return TableCell(canonical_json({"type": "number", "value": number, "unit": unit}),
                     number + (" " + unit if unit else ""), (1, value))


def relation_cell(labels):
    values = sorted(text_key(label) for label in labels)
    return TableCell(canonical_json({"type": "relations", "value": values}), "、".join(values) or "未选", (1, tuple(values)))


def status_cell(kind, status):
    """Same text key and label as the status word; ordered by the shared business rank, like the SQL pages."""
    return replace(text_cell(table_status_label(kind, status)), order=(1, RESOURCE_STATUS_RANKS[status]))

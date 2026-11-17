"""Shared column contracts for the six resource-table views, not catalogs."""

from dataclasses import dataclass
from typing import Literal

from core.models.workbench_command import WorkbenchCommandRejected

TABLE_KINDS = ("material", "op_type", "machine", "operator", "supplier")
MAX_FACET_KEYS = 50000
_BASE = ("business_code", "label")
_COLUMNS = {
    "material": _BASE + ("spec", "stock_qty", "status"),
    "machine": _BASE + ("op_type_ref", "group_ref", "status"),
    "operator": _BASE + ("skill_refs", "shift_profile_ref", "status"),
    "supplier": _BASE + ("op_type_refs", "default_days", "status"),
}


@dataclass(frozen=True)
class SqlOrder:
    """分页 SQL 按这条存储字段排序：文本经 ``aps_text_sort_key``（与文本格同一归一化），数字按原值，状态按业务序号。

    只说明排序能力。整格筛选按格子 key 判定（数字格的 key 带单位，“7 公斤”和“7 件”同序不同值），
    不在 SQL 里做；列定义见 ``core.services.workbench.facts.table_columns``。
    """

    field: str
    kind: Literal["text", "number", "status"]


def table_columns(kind, category=None):
    if kind == "op_type":
        extra = {"internal": ("available_machines", "available_operators"), "external": ("default_merge_mode",)}
        return _BASE + (extra.get(category, ()) if category is not None else ()) + ("remark",)
    return _COLUMNS.get(kind, ())


def table_sorts(kind, category=None):
    """能排序的列：本视图的全部表格列，外加编号、名称和状态（工种没有状态列，按状态排时全部平手、按编号）。"""
    return tuple(dict.fromkeys(_BASE + ("status",) + table_columns(kind, category)))


def normalize_table_column_filters(value, allowed, *, invalid_column_message="列筛选的列或归属不正确，请重新选择。"):
    if type(value) is not dict or len(value) > 20:
        raise WorkbenchCommandRejected("invalid_input", "列筛选最多 20 列。", 400)
    result = {}
    for column, condition in value.items():
        if column not in allowed or type(condition) is not dict or set(condition) != {"mode", "values"}:
            raise WorkbenchCommandRejected("invalid_input", invalid_column_message, 400)
        values = condition["values"]
        if condition["mode"] not in ("include", "exclude") or type(values) is not list or len(values) > MAX_FACET_KEYS:
            raise WorkbenchCommandRejected("invalid_input", "列筛选方式不对，每列最多 50000 个值。", 400)
        if any(type(key) is not str or not key for key in values) or len(set(values)) != len(values):
            raise WorkbenchCommandRejected("invalid_input", "筛选值不对或有重复，请重新选择筛选条件。", 400)
        result[column] = {"mode": condition["mode"], "values": sorted(values)}
    return {column: result[column] for column in sorted(result)}


def normalize_column_filters(value, kind, category=None):
    return normalize_table_column_filters(value, table_columns(kind, category))


def toolbar_scope(query):
    return {"kind": query.kind, "query": query.query, "status": query.status,
            **({"category": query.category} if query.kind != "material" else {})}


def validate_facet_request(query, column, search, number, size):
    if column not in table_columns(query.kind, query.category):
        raise WorkbenchCommandRejected("invalid_input", "该视图不支持此业务列，请核对工种归属。", 400)
    if type(search) is not str or len(search) > 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值搜索最多200字。", 400)
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值页码或条数不正确，每页最多200条。", 400)

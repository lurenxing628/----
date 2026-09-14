"""Shared column contracts for the six resource-table views, not catalogs."""

import re

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


def table_columns(kind, category=None):
    if kind == "op_type":
        extra = {"internal": ("available_machines", "available_operators"), "external": ("default_merge_mode",)}
        return _BASE + (extra.get(category, ()) if category is not None else ()) + ("remark",)
    return _COLUMNS.get(kind, ())


def normalize_column_filters(value, kind, category=None):
    if type(value) is not dict or len(value) > 20:
        raise WorkbenchCommandRejected("invalid_input", "列筛选最多 20 列。", 400)
    allowed = table_columns(kind, category)
    result = {}
    for column, condition in value.items():
        if column not in allowed or type(condition) is not dict or set(condition) != {"mode", "values"}:
            raise WorkbenchCommandRejected("invalid_input", "列筛选的列或归属不正确，请重新选择。", 400)
        values = condition["values"]
        if condition["mode"] not in ("include", "exclude") or type(values) is not list or len(values) > MAX_FACET_KEYS:
            raise WorkbenchCommandRejected("invalid_input", "列筛选方式不对，每列最多 50000 个值。", 400)
        if any(type(key) is not str or re.fullmatch(r"[0-9a-f]{64}", key) is None for key in values) or len(set(values)) != len(values):
            raise WorkbenchCommandRejected("invalid_input", "筛选值不对或有重复，请重新选择筛选条件。", 400)
        result[column] = {"mode": condition["mode"], "values": sorted(values)}
    return {column: result[column] for column in sorted(result)}


def table_query_required(query):
    kind = getattr(query, "kind", "material")
    legacy = ("business_code", "label", "stock_qty", "status") if kind == "material" else ("business_code", "label", "status", "default_days")
    return bool(query.column_filters) or query.sort not in legacy


def toolbar_scope(query):
    return {"kind": getattr(query, "kind", "material"), "query": query.query, "status": query.status,
            **({"category": query.category} if hasattr(query, "category") else {})}


def validate_facet_request(query, column, search, number, size):
    if column not in table_columns(getattr(query, "kind", "material"), getattr(query, "category", None)):
        raise WorkbenchCommandRejected("invalid_input", "该视图不支持此业务列，请核对工种归属。", 400)
    if type(search) is not str or len(search) > 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值搜索最多200字。", 400)
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 200:
        raise WorkbenchCommandRejected("invalid_input", "筛选值页码或条数不正确，每页最多200条。", 400)

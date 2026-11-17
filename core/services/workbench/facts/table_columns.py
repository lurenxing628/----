"""资源与物料表格的列定义，只此一份：每列怎样造整格（筛选身份、显示、内存排序），以及分页 SQL 能否按它排序。

格子索引的列枚举和分页走 SQL 还是走格子索引，都由这里推出。哪些列能筛选、能排序是请求契约，
见 ``core.models.workbench_resource_table_query``；这里按那份列名给出每列的做法。

``cell(row)`` 收一行读视图：物料是 ``MaterialRow``，资源是 ``resource.table_facts.ResourceTableRow``，
都带存储行 ``raw``；资源行另给对外状态和关系、能力、合并方式的取值。本模块不读库。
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from core.models.workbench_resource_table_query import SqlOrder, table_sorts

from .table_cells import TableCell, number_cell, relation_cell, status_cell, text_cell

_STATUS_ORDER = SqlOrder("status", "status")


@dataclass(frozen=True)
class TableColumn:
    """``sql_order`` 只表示 SQL 排序能力；为 None 时这一列只能在格子索引里排。整格筛选总在格子索引上做。"""

    name: str
    cell: Callable[[Any], TableCell]
    sql_order: Optional[SqlOrder] = None


def _text(name, field):
    return TableColumn(name, lambda row: text_cell(row.raw[field]), SqlOrder(field, "text"))


def _status(kind):
    return TableColumn("status", lambda row: status_cell(kind, row.status), _STATUS_ORDER)


def _relation(name):
    return TableColumn(name, lambda row: relation_cell(row.relation_names(name)))


def _resource(kind, key, *columns):
    return (_text("business_code", key), _text("label", "name"), *columns, _status(kind))


_COLUMNS: Dict[str, Tuple[TableColumn, ...]] = {
    "material": (
        _text("business_code", "material_id"), _text("label", "name"), _text("spec", "spec"),
        TableColumn("stock_qty", lambda row: number_cell(row.stock, row.raw["unit"]), SqlOrder("stock_qty", "number")),
        TableColumn("status", lambda row: status_cell("material", row.raw["status"]), _STATUS_ORDER),
    ),
    "machine": _resource("machine", "machine_id", _relation("op_type_ref"), _relation("group_ref")),
    "operator": _resource("operator", "operator_id", _relation("skill_refs"), _relation("shift_profile_ref")),
    "supplier": _resource("supplier", "supplier_id", _relation("op_type_refs"), TableColumn(
        "default_days", lambda row: number_cell(row.raw["default_days"], "天"), SqlOrder("default_days", "number"))),
    "machine_group": _resource("machine_group", "group_id"),
    "shift_profile": _resource("shift_profile", "profile_id"),
    "op_type": (
        _text("business_code", "op_type_id"), _text("label", "name"), _text("remark", "remark"),
        # 工种没有启停状态：按状态排序时全部平手，按编号排。
        TableColumn("status", lambda row: text_cell(None), _STATUS_ORDER),
        TableColumn("available_machines", lambda row: number_cell(row.availability("machines"), "台", missing="暂无数据")),
        TableColumn("available_operators", lambda row: number_cell(row.availability("operators"), "人", missing="暂无数据")),
        TableColumn("default_merge_mode", lambda row: text_cell(row.merge_mode_label(), missing="未设置")),
    ),
}
_BY_NAME = {kind: {column.name: column for column in columns} for kind, columns in _COLUMNS.items()}


def index_columns(kind, category=None) -> Tuple[TableColumn, ...]:
    """格子索引要造的列：这个视图能筛选和能排序的全部列。"""
    return tuple(_BY_NAME[kind][name] for name in table_sorts(kind, category))


def sql_order(query) -> Optional[SqlOrder]:
    """本次分页用到的列都有 SQL 键时返回排序列的 SQL 键，否则 None（走格子索引）。

    列筛选按整格 key 判定（数字格带单位），没有 SQL 筛选键，所以带列筛选一律走格子索引。
    """
    if query.column_filters:
        return None
    return _BY_NAME[query.kind][query.sort].sql_order

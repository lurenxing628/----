"""SQL 业务排序：枚举表达式映射成 ``core.models.enums`` 里的业务序号；表格分页按列定义给出的排序字段排。"""

from typing import Mapping

from core.models.enums import RESOURCE_STATUS_RANKS
from core.models.workbench_resource_table_query import SqlOrder


def rank_sql(expression: str, ranks: Mapping[str, int]) -> str:
    """``expression`` 由仓储常量拼出，``ranks`` 取 enums 的 ``*_RANKS``；SQL 与 Python 排序用同一份序号。"""
    return "CASE (" + expression + ")" + "".join(f" WHEN '{value}' THEN {rank}" for value, rank in ranks.items()) + " END"


def order_by(order: SqlOrder, direction: str, *, alias: str, status: str, code: str) -> str:
    """表格分页的 ORDER BY：``order`` 来自列定义，``status`` 是本表对外状态的 SQL 写法，``code`` 是原始业务码列。

    平手一律按原始业务码升序，与格子索引（先按编号排、再按格子稳定排序）同序；
    文本归一化后同键的两条编号（如 ``A 1`` 与 ``A  1``）也靠它分出先后。
    """
    if order.kind == "status":
        term = rank_sql(status, RESOURCE_STATUS_RANKS)
    elif order.kind == "text":
        term = f"aps_text_sort_key({alias}.{order.field})"
    else:
        term = f"{alias}.{order.field}"
    return f"{term} {direction.upper()}, {code} ASC"

"""工作台 12 张可导入表的统一目录。

按用户说明书顺序汇集各导入表模块的 `table_descriptor`（与模板及导出文件的「填写说明」同源），
供 `tools.generate_table_docs` 生成和校验列说明与总览表；新增可导入表时在此登记。
"""

from typing import Any, Callable, Dict, List, Tuple

from core.models import (
    workbench_batch_file,
    workbench_calendar_file,
    workbench_field_report_file,
    workbench_material_file,
    workbench_process_file,
    workbench_relation_file,
    workbench_resource_file,
)

#: 表编号 → 取这张表描述的办法。顺序就是用户文档里介绍这些表的顺序。
_CATALOG: Tuple[Tuple[str, Callable[[], Dict[str, Any]]], ...] = (
    ("op_type", lambda: workbench_resource_file.table_descriptor("op_type")),
    ("supplier", lambda: workbench_resource_file.table_descriptor("supplier")),
    ("route", lambda: workbench_process_file.table_descriptor("route")),
    ("hours", lambda: workbench_process_file.table_descriptor("hours")),
    ("operator", lambda: workbench_resource_file.table_descriptor("operator")),
    ("machine", lambda: workbench_resource_file.table_descriptor("machine")),
    ("operator_machine", lambda: workbench_relation_file.table_descriptor("operator_machine")),
    ("material", workbench_material_file.table_descriptor),
    ("work_calendar", lambda: workbench_calendar_file.table_descriptor("work_calendar")),
    ("operator_calendar", lambda: workbench_calendar_file.table_descriptor("operator_calendar")),
    ("batch", workbench_batch_file.table_descriptor),
    ("field_report", workbench_field_report_file.table_descriptor),
)


def table_descriptor(table_id: str) -> Dict[str, Any]:
    for known, build in _CATALOG:
        if known == table_id:
            return build()
    raise KeyError("没有登记这张表：" + str(table_id))


def all_descriptors() -> List[Dict[str, Any]]:
    """按用户文档里的介绍顺序返回全部表描述。"""
    return [build() for _, build in _CATALOG]

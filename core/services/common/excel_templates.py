"""导出到 Excel 的单元格净化。

这个模块原来还管两件事：启动期往 templates_excel/ 生成旧模板（2026-09 退役，12 张业务表
的模板改由工作台按表描述现生成），以及给旧资料转换子系统写 XLSX（build_xlsx_bytes +
get_template_definition，2026-09-21 随 core/services/process/unit_excel 一起退役）。

剩下的只有 sanitize_export_cell，它有四个生产用户：排产实际导出、校准导出、报表导出、
报表 xlsx 导出。做两件事——把会被 Excel 当公式起头的字符转义掉，把控制字符剔掉
（openpyxl 写进去会让文件打不开）。
"""

from __future__ import annotations

from typing import Any


def sanitize_export_cell(value: Any) -> Any:
    if isinstance(value, str):
        value = "".join(ch for ch in value if ord(ch) >= 32 or ch in "\t\n\r")
        if value and value[0] in ("=", "+", "-", "@"):
            return "'" + value
    return value


# 四个生产用户 import 的都是这个带下划线的旧名字，保留别名，不在退役这一轮顺手改调用点。
_sanitize_export_cell = sanitize_export_cell

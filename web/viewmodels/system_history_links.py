"""排产历史页行级工作台链接装配（fusion-handrolled-links-adoption）。

每个历史版本行给 5 条 WorkbenchLink（设备甘特/人员甘特/周计划/资源排班/优化分析），
替代模板里只带 version 的手拼 url_for——目标页中 gantt/week_plan/resource_dispatch
要求日期范围，缺了会被合同禁用并给原因。

纯数据变换层（架构适应度：viewmodel 禁 IO）：span 读取由路由层负责
（system_history.py 的 _load_history_span_dates，dashboard _load_plan_time_span
同款先例），本函数只吃读好的 span/span_error 构造链接。
行级历史是正式排产记录，方案身份固定 adopted（与目标页缺省解析一致，
`_plan_role_links` 先例同款轻量 context，不做全量身份解析）。
span_error 非空时进 context 的 plan_time_span_load_error，由合同把该行
日期必填链接禁用并明示——单行坏历史不炸整页，也不静默装好。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_workbench_links import ROLE_ADOPTED, build_workbench_link, build_workbench_plan_context


def build_history_version_links(
    version: Any,
    *,
    span: Optional[Dict[str, Any]],
    span_error: str = "",
) -> List[Dict[str, Any]]:
    """单个历史版本的 5 条行级链接；version 非法时返回空列表（行不渲染链接）。

    span 是 get_plan_time_span_dates 的返回（含 start_date/end_date 日期口径），
    None 表示无计划行（失败/模拟运行）——日期必填链接由合同禁用。
    """
    try:
        version_int = int(version)
    except (TypeError, ValueError):
        return []
    if version_int <= 0:
        return []

    context = build_workbench_plan_context(
        version=version_int,
        plan_role=ROLE_ADOPTED,
        date_from=(span or {}).get("start_date"),
        date_to=(span or {}).get("end_date"),
    )
    if span_error:
        context["plan_time_span_load_error"] = span_error
    return [
        build_workbench_link(context, "gantt", label="设备甘特图", view="machine"),
        build_workbench_link(context, "gantt", label="人员甘特图", view="operator"),
        build_workbench_link(context, "week_plan", label="周计划"),
        build_workbench_link(context, "resource_dispatch", label="资源排班"),
        build_workbench_link(context, "analysis", label="优化分析"),
    ]

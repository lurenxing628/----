"""WorkbenchLink 目标 query 规格与禁注入键表（从 scheduler_workbench_link_query 拆出，纯数据单点定义）。

仅含**内部专用**常量（外部 import 为 0）：execution_review / context-free 目标的 extra_params 禁注入
键集、context-free 目标集、各目标的 query 装配规格 _TARGET_QUERY_SPECS。query 装配逻辑仍在
scheduler_workbench_link_query.py，从本模块 import 消费——拆分仅「只搬不改行为」降文件体量，无行为变更。
"""

from __future__ import annotations

from typing import Any, Dict

_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS = {
    "plan_role",
    "requested_plan_role",
    "effective_plan_role",
    "scenario_id",
    "plan_context_token",
    "is_preview",
    "is_scenario_preview",
    "is_comparison",
    "is_superseded_by_newer_version",
    "can_dispatch",
    "can_write_feedback",
}

# history/batch_detail 的 query 合同（version 可选+back_to / 仅 back_to）不可被
# extra_params 绕过——版本/批次/日期/period/资源/视图/方案身份维度键一律拒绝
# （execution_review 先例同款；version/view/gantt_resource 同属工作台上下文维度）
_CONTEXT_FREE_TARGET_FORBIDDEN_EXTRA_PARAMS = _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS | {
    "version",
    "view",
    "batch_id",
    "gantt_batch",
    "gantt_resource",
    "query_date",
    "period_preset",
    "date_from",
    "date_to",
    "start_date",
    "end_date",
    "week_start",
    "resource_type",
    "resource_id",
    "scope_type",
    "scope_id",
    "machine_id",
    "operator_id",
    "team_id",
    # 内部身份一律不得经 extra_params 注入 context-free 目标 URL（页面禁外显内部身份硬纪律）——
    # 否则 dashboard/history/batch_detail/batches 等可被注成 /scheduler/?op_id=... 外显内部 ID
    "op_id",
    "schedule_id",
    "candidate_id",
    "source_table",
}
_CONTEXT_FREE_TARGETS = {"history", "batch_detail", "batches"}

_TARGET_QUERY_SPECS: Dict[str, Dict[str, Any]] = {
    "dashboard": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    # 执行排产页：context-free，不带任何工作台上下文维度（仿 history/batch_detail 全 none）
    "batches": {
        "plan_style": "none",
        "date_style": "none",
        "batch_position": "none",
        "resource_style": "none",
    },
    "analysis": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "gantt": {
        "plan_style": "standard",
        "date_style": "start_end",
        "batch_position": "before_resource",
        "batch_param": "gantt_batch",
        "resource_style": "gantt_filter",
        "include_gantt_view": True,
    },
    "week_plan": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
        "include_week_start": True,
    },
    "resource_dispatch": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "after_resource",
        "resource_style": "scope",
        "default_resource_type": "operator",
        "period_preset": "custom",
    },
    "overdue_report": {
        "plan_style": "standard",
        "date_style": "none",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "delay_diagnosis": {
        "plan_style": "standard",
        "date_style": "none",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "utilization_report": {
        "plan_style": "standard",
        "date_style": "start_end",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "downtime_report": {
        "plan_style": "standard",
        "date_style": "start_end",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "execution_review": {
        "plan_style": "execution_review",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    "reports_index": {
        "plan_style": "standard",
        "date_style": "date_from_to",
        "batch_position": "before_resource",
        "resource_style": "resource",
    },
    # 历史页：version 是可选筛选（无方案身份概念），不带日期/批次/资源/period
    "history": {
        "plan_style": "version_only",
        "date_style": "none",
        "batch_position": "none",
        "resource_style": "none",
    },
    # 批次详情：batch_id 走路径占位（batch_in_path），query 只剩 back_to
    "batch_detail": {
        "plan_style": "none",
        "date_style": "none",
        "batch_position": "none",
        "resource_style": "none",
        "batch_in_path": True,
    },
}

__all__ = [
    "_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS",
    "_CONTEXT_FREE_TARGET_FORBIDDEN_EXTRA_PARAMS",
    "_CONTEXT_FREE_TARGETS",
    "_TARGET_QUERY_SPECS",
]

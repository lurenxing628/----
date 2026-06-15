from __future__ import annotations

from typing import Any

SCHEDULE_INPUT_FIELD_LABELS = {
    "default_days": "供应商默认周期",
    "due_date": "交期",
    "ext_days": "外协周期",
    "ext_group_total_days": "合并外协周期",
    "setup_hours": "换型时间",
    "unit_hours": "单件工时",
}

CONFIG_FIELD_LABELS = {
    "algo_mode": "计算模式",
    "auto_assign_enabled": "未指定设备或人员时，系统自动分配",
    "auto_assign_persist": "保存系统补齐的设备和人员",
    "dispatch_mode": "派工方式",
    "dispatch_rule": "智能派工策略",
    "due_weight": "交期权重",
    "enforce_ready_default": "默认启用齐套检查",
    "freeze_window_days": "锁定天数",
    "freeze_window_enabled": "锁定近期排程",
    "graph_analysis_mode": "工序图分析",
    "graph_block_on_cycle": "工序关系互相卡住时停止排产",
    "graph_candidate_weight_count": "重点工序方案档数",
    "graph_critical_weight": "重点工序提前权重",
    "graph_debug_export": "导出工序关系分析文件",
    "graph_impact_weight": "后续影响权重",
    "graph_overdue_tolerance_count": "允许多超期批次数",
    "graph_selection_policy": "正式方案选择方式",
    "graph_tardiness_tolerance_ratio": "允许多拖期比例",
    "holiday_default_efficiency": "假期工作效率",
    "objective": "优化目标",
    "ortools_enabled": "深度优化",
    "ortools_time_limit_seconds": "深度优化尝试时间",
    "prefer_primary_skill": "优先推荐主操/高技能人员",
    "priority_weight": "优先级权重",
    "ready_weight": "齐套权重",
    "sort_strategy": "排产策略",
    "time_budget_seconds": "找更好排法先试多久",
    "run_time_budget_seconds": "这次找更好排法先试多久",
}

GENERAL_FIELD_LABELS = {
    "batch_id": "批次号",
    "batch_ids": "批次",
    "affected_machine_id": "影响设备",
    "affected_operator_id": "影响人员",
    "created_by": "反馈人",
    "date_range": "日期范围",
    "end_date": "结束日期",
    "event_time": "反馈时间",
    "effective_plan_role": "实际使用的方案",
    "expected_state_revision": "页面状态",
    "handling_status": "处理状态",
    "idempotency_key": "重复提交标记",
    "impact_minutes": "预计影响时间",
    "machine_id": "设备",
    "operator_id": "人员",
    "op_id": "工序编号",
    "period_preset": "日期范围",
    "plan_context": "计划上下文",
    "plan_identity": "计划上下文",
    "plan_role": "方案",
    "query_date": "查询日期",
    "quantity_done": "完成数量",
    "quantity_scrapped": "报废数量",
    "reason_code": "原因",
    "remark": "情况说明",
    "requested_plan_role": "当前方案",
    "scenario_id": "模拟预览",
    "schedule_id": "排程记录",
    "schedule_version": "排程版本",
    "severity": "严重程度",
    "source_table": "计划来源",
    "scope_type": "范围类型",
    "start_date": "开始日期",
    "start_dt": "开始时间",
    "suggest_reschedule": "是否建议重新排程",
    "time_range": "开始或结束时间",
    "version": "版本",
}


def user_field_label(field: Any, default: str = "") -> str:
    key = str(field or "").strip()
    if not key:
        return str(default or "").strip()
    for mapping in (SCHEDULE_INPUT_FIELD_LABELS, CONFIG_FIELD_LABELS, GENERAL_FIELD_LABELS):
        label = mapping.get(key)
        if label:
            return label
    return str(default or "").strip()


def display_field_label(field: Any, fallback: str = "字段") -> str:
    label = user_field_label(field)
    return label or str(fallback or "字段")


__all__ = [
    "CONFIG_FIELD_LABELS",
    "GENERAL_FIELD_LABELS",
    "SCHEDULE_INPUT_FIELD_LABELS",
    "display_field_label",
    "user_field_label",
]

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.models.operation_log_labels import ACTION_LABELS as _ACTION_LABELS
from core.models.operation_log_labels import MODULE_LABELS as _MODULE_LABELS
from core.models.operation_log_labels import operation_log_label as _label
from core.models.operation_log_public_projection import public_operation_log_error_message

from .ui_presenters import UiEmptyState, UiToggleRow, checked_attr

_LOG_LEVEL_LABELS = {
    "INFO": "信息",
    "WARN": "警告",
    "WARNING": "警告",
    "ERROR": "错误",
}

_TARGET_TYPE_LABELS = {
    "backup": "备份",
    "batch": "批次",
    "batch_material": "批次物料",
    "calendar": "工作日历",
    "machine": "设备",
    "material": "物料",
    "operation_log": "操作日志",
    "operator": "人员",
    "operator_calendar": "人员日历",
    "operator_machine": "人员设备关系",
    "op_type": "工种",
    "part_operation": "零件工序",
    "part_operation_hours": "零件工序工时",
    "part_route": "工艺路线",
    "plugin": "扩展功能",
    "resource_dispatch": "资源派工",
    "runtime": "运行环境",
    "schedule": "排程",
    "supplier": "供应商",
    "week_plan": "周计划",
}


@dataclass(frozen=True)
class SystemLogsPageState:
    cleanup_toggle: UiToggleRow
    empty_state: UiEmptyState


class OperationLogViewRowContractError(ValueError):
    """操作日志行无法转换成页面展示数据。"""


def _settings_value(settings: Any, key: str) -> Any:
    if isinstance(settings, dict):
        return settings[key]
    return getattr(settings, key)


def build_system_logs_page_view_model(settings: Any) -> SystemLogsPageState:
    return SystemLogsPageState(
        cleanup_toggle=UiToggleRow(
            id="logAutoCleanupEnabled",
            name="auto_log_cleanup_enabled",
            title="自动清理",
            desc="按保留天数清理旧日志；系统会在有人操作页面且到达间隔后执行。",
            checked_attr=checked_attr(_settings_value(settings, "auto_log_cleanup_enabled") == "yes"),
        ),
        empty_state=UiEmptyState(
            title="暂无记录",
            desc="当前筛选条件下没有找到操作日志，可以放宽时间、模块或级别后再查询。",
        ),
    )


def _resolve_label_or_code(value: Any, labels: Dict[str, str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in labels:
        return text
    for code, label in labels.items():
        if text == label:
            return code
    return text


def resolve_operation_log_module_filter(value: Any) -> str:
    return _resolve_label_or_code(value, _MODULE_LABELS)


def resolve_operation_log_action_filter(value: Any) -> str:
    return _resolve_label_or_code(value, _ACTION_LABELS)


def _parse_detail_obj(detail_raw: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    if detail_raw is None:
        return "empty", None
    s = str(detail_raw).strip()
    if not s:
        return "empty", None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return "invalid_json", None
    if not isinstance(obj, dict):
        return "non_object", None
    return "ok", obj


def build_operation_log_view_rows(items: List[Any]) -> List[Dict[str, Any]]:
    """
    将 OperationLog model 列表转为模板可直接渲染的 dict rows：
    - 尝试把 detail 里的结构化排查信息展开成 detail_obj
    - 解析失败或不是结构化内容时，detail_obj=None，模板只提示维护人员到日志中排查，不直接展示 detail 原文
    """
    out: List[Dict[str, Any]] = []
    for it in items or []:
        try:
            d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else {})
        except Exception as exc:
            raise OperationLogViewRowContractError("操作日志行无法转换为页面展示数据") from exc
        d["log_level_label"] = _label(d.get("log_level"), _LOG_LEVEL_LABELS, "其他等级")
        d["module_label"] = _label(d.get("module"), _MODULE_LABELS, "其他模块")
        d["action_label"] = _label(d.get("action"), _ACTION_LABELS, "其他操作")
        d["target_type_label"] = _label(d.get("target_type"), _TARGET_TYPE_LABELS, "其他对象")
        d["error_message_public"] = public_operation_log_error_message(d.get("error_message"))
        detail_parse_state, detail_obj = _parse_detail_obj(d.get("detail"))
        d["detail_parse_state"] = detail_parse_state
        d["detail_obj"] = detail_obj
        out.append(d)
    return out

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

_LOG_LEVEL_LABELS = {
    "INFO": "信息",
    "WARN": "警告",
    "WARNING": "警告",
    "ERROR": "错误",
}

_MODULE_LABELS = {
    "equipment": "设备管理",
    "excel_demo": "Excel 演示",
    "material": "物料管理",
    "personnel": "人员管理",
    "plugins": "插件管理",
    "process": "工艺管理",
    "scheduler": "排产管理",
    "system": "系统管理",
}

_ACTION_LABELS = {
    "backup": "备份",
    "backup_delete": "删除备份",
    "batch_material_add": "添加批次物料",
    "batch_material_delete": "删除批次物料",
    "batch_material_update": "更新批次物料",
    "cleanup": "清理",
    "create": "新增",
    "delete": "删除",
    "export": "导出",
    "import": "导入",
    "logs_cleanup": "清理日志",
    "logs_delete": "删除日志",
    "restore": "恢复",
    "schedule": "排产",
    "simulate": "模拟排产",
    "toggle": "切换状态",
    "update": "更新",
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
    "plugin": "插件",
    "resource_dispatch": "资源派工",
    "runtime": "运行环境",
    "schedule": "排程",
    "supplier": "供应商",
    "week_plan": "周计划",
}


def _label(value: Any, labels: Dict[str, str], fallback: str) -> str:
    key = str(value or "").strip()
    if not key:
        return "-"
    return labels.get(key, fallback)


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


def _safe_load_detail_obj(detail_raw: Any) -> Optional[Dict[str, Any]]:
    if detail_raw is None:
        return None
    s = str(detail_raw).strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def build_operation_log_view_rows(items: List[Any]) -> List[Dict[str, Any]]:
    """
    将 OperationLog model 列表转为模板可直接渲染的 dict rows：
    - 展开 detail JSON 为 detail_obj（仅 dict 才展开）
    - 解析失败/非 dict → detail_obj=None（模板会回退显示 detail 原文）
    """
    out: List[Dict[str, Any]] = []
    for it in items or []:
        try:
            d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else {})
        except Exception:
            d = {}
        d["log_level_label"] = _label(d.get("log_level"), _LOG_LEVEL_LABELS, "其他")
        d["module_label"] = _label(d.get("module"), _MODULE_LABELS, "其他模块")
        d["action_label"] = _label(d.get("action"), _ACTION_LABELS, "其他操作")
        d["target_type_label"] = _label(d.get("target_type"), _TARGET_TYPE_LABELS, "其他对象")
        d["detail_obj"] = _safe_load_detail_obj(d.get("detail"))
        out.append(d)
    return out

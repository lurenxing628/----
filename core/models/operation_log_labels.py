"""Shared operation-log display labels without changing stored audit codes."""

from typing import Any, Dict

MODULE_LABELS = {
    "equipment": "设备管理",
    "excel_demo": "Excel 演示",
    "material": "物料管理",
    "personnel": "人员管理",
    "plugins": "扩展功能管理",
    "process": "工艺管理",
    "scheduler": "排产管理",
    "system": "系统管理",
}

ACTION_LABELS = {
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


def operation_log_label(value: Any, labels: Dict[str, str], fallback: str) -> str:
    key = str(value or "").strip()
    if not key:
        return "-"
    if key in labels:
        return labels[key]
    return f"{fallback}（{key}）"


def operation_log_summary(module: Any, action: Any) -> str:
    module_label = operation_log_label(module, MODULE_LABELS, "其他模块")
    action_label = operation_log_label(action, ACTION_LABELS, "其他操作")
    return f"{module_label} · {action_label}"

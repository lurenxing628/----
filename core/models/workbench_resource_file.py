"""Versioned file columns. Read-only columns assert facts, never write them."""

import hashlib
from dataclasses import dataclass

from core.errors import ValidationError
from core.models.workbench_resource_action import action_kind, resource_scope

IMPORT_ROW_LIMIT = 2000
TEMPLATE_VERSION = 1
WRITABLE = {
    "op_type": ("business_code", "label", "category", "default_merge_mode", "remark"),
    "machine": ("business_code", "label", "status", "op_type_code", "group_code"),
    "operator": ("business_code", "label", "status", "skill_codes", "shift_profile_code"),
    "supplier": ("business_code", "label", "status", "default_days", "op_type_codes"),
}
READONLY = {
    "op_type": ("default_hours", "created_at"),
    "machine": ("category", "remark", "legacy_status", "team_code", "machine_authorizations", "created_at", "updated_at"),
    "operator": ("remark", "legacy_status", "inactive_reason", "team_code", "skills_declared", "skill_details",
                 "machine_authorizations", "created_at", "updated_at"),
    "supplier": ("remark", "legacy_status", "inactive_reason", "legacy_op_type_code", "explicit_op_type_codes", "created_at"),
}
LABELS = {
    "business_code": "编号", "label": "名称", "status": "状态", "category": "归属或设备类别",
    "default_merge_mode": "外协周期策略", "remark": "备注", "op_type_code": "自制工种编号",
    "group_code": "设备组编号", "skill_codes": "技能工种编号数组", "shift_profile_code": "班次编号",
    "default_days": "默认周期", "op_type_codes": "外协工种编号数组", "default_hours": "原默认工时（只读）",
    "legacy_status": "原始状态（只读）", "inactive_reason": "停用原因（只读）", "team_code": "原班组编号（只读）",
    "skills_declared": "技能已声明（只读）", "skill_details": "原技能明细（只读）",
    "machine_authorizations": "原设备授权（只读）", "legacy_op_type_code": "原单工种编号（只读）",
    "explicit_op_type_codes": "显式工种编号数组（只读）", "created_at": "创建时间（只读）", "updated_at": "更新时间（只读）",
}
MULTI_CODES = {"skill_codes", "op_type_codes", "explicit_op_type_codes"}
JSON_FIELDS = MULTI_CODES | {"skill_details", "machine_authorizations", "skills_declared"}
NUMERIC_FIELDS = {"default_days", "default_hours"}
NULLABLE = {"remark", "default_merge_mode", "op_type_code", "group_code", "shift_profile_code"}
RELATIONS = {
    "machine": {"op_type_code": ("op_type_ref", "op_type", "internal"), "group_code": ("group_ref", "machine_group", None)},
    "operator": {"skill_codes": ("skill_refs", "op_type", "internal"), "shift_profile_code": ("shift_profile_ref", "shift_profile", None)},
    "supplier": {"op_type_codes": ("op_type_refs", "op_type", "external")},
    "op_type": {},
}
INSTRUCTIONS = ("编号必须为文本；缺列/空单元格不修改；\\N仅清允许字段，数组用[]明确清空。"
                "多值必须是JSON字符串数组，例如[\"OT1\",\"OT2\"]，不接受逗号猜分。"
                "只读列仅核对原事实；技能不会授予设备权限。CSV文字有一层可逆单引号，文字起始反斜线双写。")


def file_columns(kind):
    action_kind(kind)
    return WRITABLE[kind] + READONLY[kind]


def public_columns(kind):
    result = []
    for key in file_columns(kind):
        label = ("归属" if kind == "op_type" else "设备类别") if key == "category" else LABELS[key]
        if key in READONLY[kind] and "只读" not in label:
            label += "（只读）"
        result.append({"key": key, "label": label})
    return result


def import_request(kind, content, file_format, mode, scope):
    if type(content) is not bytes or type(file_format) is not str or file_format not in ("csv", "xlsx"):
        raise ValidationError("必须提供CSV/XLSX原始文件字节。", field="file")
    if type(mode) is not str or mode != "upsert":
        raise ValidationError("只支持按编号增量导入，不支持替换。", field="mode")
    scope = resource_scope(kind, scope)
    if scope["query"] or scope["status"] is not None or scope.get("column_filters"):
        raise ValidationError("导入按文件编号操作，不接受搜索或状态筛选。", field="scope")
    if kind == "op_type" and scope["category"] not in ("internal", "external"):
        raise ValidationError("工种导入必须明确自制或外协归属。", field="category")
    return {"file_sha256": hashlib.sha256(content).hexdigest(), "format": file_format, "mode": mode, "scope": scope}


@dataclass(frozen=True)
class ResourceFileDownload:
    filename: str
    mime_type: str
    content: bytes
    row_count: int

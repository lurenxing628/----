"""Versioned file columns. Read-only columns are reference data, never written."""

import hashlib
from dataclasses import dataclass

from core.errors import ValidationError
from core.models.workbench_resource_action import action_kind, resource_scope
from core.models.workbench_table_descriptor import (
    DEFAULT_IMPORT_BYTE_LIMIT,
    UPSERT_ONLY,
    instructions_text,
)

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


REQUIRED = {kind: ("business_code",) for kind in WRITABLE}
#: 文件里的状态与归属一律写英文代号，和界面上的中文标签不是一回事，下拉也只能给代号。
ENUMS = {
    "op_type": {"category": ("internal", "external"), "default_merge_mode": ("separate", "merged")},
    "machine": {"status": ("active", "maintain", "inactive")},
    "operator": {"status": ("active", "leave", "inactive")},
    "supplier": {"status": ("active", "pending_review", "inactive")},
}
DISPLAY_NAMES = {"op_type": "工种", "machine": "设备", "operator": "人员", "supplier": "供应商"}
SHEET_NAME = "资源"
_VALUE_HINTS = {
    "business_code": "这一类资料的编号，例如 M001；不填就不知道改哪一条",
    "label": "名称；新增时必须填，已有的留空保持原样",
    "status": "只填代号：active 可用 / maintain 停机 / leave 请假 / pending_review 待复核 / inactive 停用",
    "category": "只填代号：internal 自制 / external 外协",
    "default_merge_mode": "只填代号：separate 分开 / merged 合并；要清除请填 \\N（大写）",
    "remark": "随便写；要清除请填 \\N（大写）",
    "op_type_code": "这台设备绑的自制工种编号；要清除请填 \\N（大写）",
    "group_code": "设备组编号；要清除请填 \\N（大写）",
    "skill_codes": "JSON 文字数组，例如 [\"OT1\",\"OT2\"]；填 [] 表示清除，不接受用逗号分隔",
    "shift_profile_code": "班次编号；要清除请填 \\N（大写）",
    # 新增供应商时域层强制要大于 0 的默认周期（core/shared/value_policies.py 的 WRITE_REQUIRED），
    # 但这一列对已有供应商留空表示保持原样，所以列本身不是必填，必填只发生在新增那一行。
    "default_days": "默认周期天数，填大于 0 的数字；新增供应商必须填，已有的留空保持原样",
    "op_type_codes": "JSON 文字数组，例如 [\"OT1\",\"OT2\"]；填 [] 表示清除",
}
#: 只读列的说明。备注和设备类别在工种表里可填、在别的表里只读，所以两份提示不能共用一句话，
#: 否则文件里的「填写说明」会教用户去填一列根本不会被导入的格子。
_READONLY_HINTS = {
    "remark": "导出时带出的备注，导入时不看这一列",
    "category": "导出时带出的设备类别，导入时不看这一列",
    "default_hours": "导出时带出的原默认工时，导入时不看这一列",
    "legacy_status": "导出时带出的原始状态，导入时不看这一列",
    "inactive_reason": "导出时带出的停用原因，导入时不看这一列",
    "team_code": "导出时带出的原班组编号，导入时不看这一列",
    "skills_declared": "导出时带出的技能声明标记，导入时不看这一列",
    "skill_details": "导出时带出的原技能明细，导入时不看这一列",
    "machine_authorizations": "导出时带出的原设备授权，导入时不看这一列；设备授权要到人员详情里改",
    "legacy_op_type_code": "导出时带出的原单工种编号，导入时不看这一列",
    "explicit_op_type_codes": "导出时带出的单独设置的工种编号，导入时不看这一列",
    "created_at": "导出时带出的创建时间，导入时不看这一列",
    "updated_at": "导出时带出的更新时间，导入时不看这一列",
}
_ERROR_HINTS = {
    "business_code": "留空、有首尾空格、或同一份文件里出现了两次",
    "label": "新增时留空，或填了系统不接受的字符",
    "status": "填了中文，或者填了这一类资料没有的代号",
    "category": "填了 internal 和 external 以外的词",
    "default_merge_mode": "填了 separate 和 merged 以外的词",
    "remark": "填了 \\N 以外的清除写法",
    "op_type_code": "这个工种编号在系统里找不到，或者不是自制工种",
    "group_code": "这个设备组编号在系统里找不到",
    "skill_codes": "不是 JSON 数组、用逗号分隔、或者里面的工种编号找不到",
    "shift_profile_code": "这个班次编号在系统里找不到",
    "default_days": "新增供应商时留空、不大于 0、不是数字、或者带了单位和千分位逗号",
    "op_type_codes": "不是 JSON 数组，或者里面的工种编号找不到、不是外协工种",
}
#: 四类资源的规则大同小异，但不能共用一份：工种表没有状态列也没有多值列，
#: 把"状态填英文代号""多值列要写 JSON 数组"贴到工种的填写说明上，用户会去找根本不存在的列。
_CODE_RULES = {
    "op_type": "归属、外协周期策略这两列填英文代号，不要填界面上看到的中文。",
    "machine": "状态这一列填英文代号，不要填界面上看到的中文。",
    "operator": "状态这一列填英文代号，不要填界面上看到的中文。",
    "supplier": "状态这一列填英文代号，不要填界面上看到的中文。",
}
_MULTI_RULE = "多值列必须是 JSON 文字数组，例如 [\"OT1\",\"OT2\"]，不接受用逗号分隔。"
_READONLY_RULES = {
    "op_type": "只读列仅供参考，不导入。",
    "machine": "只读列仅供参考，不导入；设备授权要到人员详情里改。",
    "operator": "只读列仅供参考，不导入；设备授权要到人员详情里改，技能不会自动带出设备权限。",
    "supplier": "只读列仅供参考，不导入。",
}


def _general_rules(kind):
    rules = [
        "一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行。",
        "按编号增量更新：编号已有的更新，没有的新增，文件里没写的记录完全不动，不会被删除。",
        "空格子表示这一项保持原样，不是清除；要清除请填 \\N（大写）"
        + ("，数组填 []。" if MULTI_CODES & set(WRITABLE[kind]) else "。"),
        _CODE_RULES[kind],
    ]
    if MULTI_CODES & set(WRITABLE[kind]):
        rules.append(_MULTI_RULE)
    rules.append(_READONLY_RULES[kind])
    return tuple(rules)
_SAMPLE_ROWS = {
    "op_type": (("OT1", "车削", "internal", "", "常用工种"),
                ("OT9", "热处理", "external", "merged", "外协")),
    "machine": (("M001", "车床 1 号", "active", "OT1", "G1"),
                ("M002", "车床 2 号", "maintain", "OT1", "")),
    "operator": (("OP001", "张三", "active", "[\"OT1\"]", "SHIFT1"),
                 ("OP002", "李四", "leave", "[\"OT1\",\"OT2\"]", "")),
    "supplier": (("S001", "某热处理厂", "active", "2.5", "[\"OT9\"]"),
                 ("S002", "某表面处理厂", "pending_review", "3", "[]")),
}


def file_columns(kind):
    action_kind(kind)
    return WRITABLE[kind] + READONLY[kind]


def table_descriptor(kind):
    """模板与填写说明生成器的唯一入口，12 张表统一形状。"""
    action_kind(kind)
    columns = []
    for item in public_columns(kind):
        key = item["key"]
        readonly = key in READONLY[kind]
        columns.append({
            "key": key,
            "label": item["label"],
            "required": key in REQUIRED[kind],
            "readonly": readonly,
            "value_hint": _READONLY_HINTS[key] if readonly else _VALUE_HINTS[key],
            "error_hint": "这一列不校验" if readonly else _ERROR_HINTS[key],
            "enum": ENUMS[kind].get(key) if not readonly else None,
            "nullable": key in NULLABLE,
        })
    return {
        "table_id": kind,
        "display_name": DISPLAY_NAMES[kind],
        "sheet_name": SHEET_NAME,
        "file_stem": DISPLAY_NAMES[kind],
        "columns": columns,
        "general_rules": _general_rules(kind),
        "sample_rows": _SAMPLE_ROWS[kind],
        "row_limit": IMPORT_ROW_LIMIT,
        "byte_limit": DEFAULT_IMPORT_BYTE_LIMIT,
        "modes": UPSERT_ONLY,
    }


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


#: 预检响应里的那段提示，和说明表的通用规则同一份来源。四类资源各有自己的列，规则也各是一份。
INSTRUCTIONS = {kind: instructions_text(table_descriptor(kind)) for kind in WRITABLE}

"""可操作设备关系文件的列目录。只读列是参考资料，不写入；文件不删除任何已有关系。"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_table_descriptor import (
    DEFAULT_IMPORT_BYTE_LIMIT,
    UPSERT_ONLY,
    instructions_text,
)

IMPORT_ROW_LIMIT = 2000
TEMPLATE_VERSION = 1
RELATION_KINDS = ("operator_machine",)

WRITABLE: Dict[str, Tuple[str, ...]] = {
    "operator_machine": ("operator_code", "machine_code", "skill_level", "is_primary"),
}
READONLY: Dict[str, Tuple[str, ...]] = {
    "operator_machine": ("operator_label", "machine_label"),
}
REQUIRED: Dict[str, Tuple[str, ...]] = {
    "operator_machine": ("operator_code", "machine_code"),
}
LABELS: Dict[str, str] = {
    "operator_code": "工号",
    "machine_code": "设备编号",
    "skill_level": "技能等级",
    "is_primary": "主操设备",
    "operator_label": "人员姓名",
    "machine_label": "设备名称",
}
ENUMS: Dict[str, Tuple[str, ...]] = {
    "skill_level": ("初级", "普通", "熟练"),
    "is_primary": ("是", "否"),
}
#: 库里存的是英文代号，文件里给用户看的是中文。导出必须按这张表翻过去，
#: 否则格子里是 normal 而下拉给的是「普通」：用户点一下下拉就改了值，
#: 想照原样填回 normal 又会被 Excel 的数据校验拒掉。
#: 不能用 ENUMS 的下标对齐代替这张表——SkillLevel 有四个值（skilled 也归到
#: expert），顺序一致只是巧合。
EXPORT_LABELS: Dict[str, Dict[str, str]] = {
    "skill_level": {"beginner": "初级", "normal": "普通", "expert": "熟练"},
    "is_primary": {"yes": "是", "no": "否"},
}
NULLABLE: FrozenSet[str] = frozenset()
NUMERIC_FIELDS: FrozenSet[str] = frozenset()
DATE_FIELDS: FrozenSet[str] = frozenset()
TIME_FIELDS: FrozenSet[str] = frozenset()

SHEET_NAMES = {"operator_machine": "可操作设备"}
DISPLAY_NAMES = {"operator_machine": "可操作设备"}


_VALUE_HINTS = {
    "operator_code": "已存在的人员工号，例如 OP001",
    "machine_code": "已存在的设备编号，例如 M001",
    "skill_level": "初级 / 普通 / 熟练；留空保持原样，新增时按普通处理",
    "is_primary": "是 / 否；留空保持原样，新增时按否处理",
    "operator_label": "导出时带出的人员姓名，导入时不看这一列",
    "machine_label": "导出时带出的设备名称，导入时不看这一列",
}
_ERROR_HINTS = {
    "operator_code": "留空、有首尾空格、或这个工号在系统里找不到",
    "machine_code": "留空、有首尾空格、这个编号找不到、或同一份文件里这对组合重复出现",
    "skill_level": "填了初级 / 普通 / 熟练以外的词",
    "is_primary": "填了是 / 否以外的词，或同一个人有多行都填了是",
    "operator_label": "这一列不校验",
    "machine_label": "这一列不校验",
}
_GENERAL_RULES = (
    "一次最多导入 2000 行。",
    "文件里没有列出的关系不会被清除；解除关系请到人员详情里操作。",
    "同一个人最多一台主操设备；设了新的主操，原来的会自动变成非主操。",
    "技能等级和主操设备留空表示保持原样，不是清除。",
    "只读列仅供参考，不导入。",
)
_SAMPLE_ROWS = (
    ("OP001", "M001", "熟练", "是"),
    ("OP001", "M002", "普通", "否"),
    ("OP002", "M001", "初级", "否"),
)


def relation_kind(kind: str) -> str:
    if type(kind) is not str or kind not in RELATION_KINDS:
        raise WorkbenchCommandRejected("entity_not_found", "此资料不支持文件操作。", 404)
    return kind


def file_columns(kind: str) -> Tuple[str, ...]:
    relation_kind(kind)
    return WRITABLE[kind] + READONLY[kind]


def public_columns(kind: str):
    result = []
    for key in file_columns(kind):
        label = LABELS[key]
        if key in READONLY[kind]:
            label += "（只读）"
        result.append({"key": key, "label": label})
    return result


def row_identity(values: Dict[str, Any]) -> Optional[str]:
    """预检行对用户显示的标识。关系表主键是两个编号的组合，没有单一编号。"""
    operator = values.get("operator_code")
    machine = values.get("machine_code")
    if type(operator) is not str or type(machine) is not str:
        return None
    return operator + " / " + machine


def import_request(kind: str, content: bytes, file_format: str, mode: str) -> Dict[str, Any]:
    relation_kind(kind)
    if type(content) is not bytes or type(file_format) is not str or file_format not in ("csv", "xlsx"):
        raise ValidationError("必须提供CSV/XLSX原始文件字节。", field="file")
    if type(mode) is not str or mode != "upsert":
        raise ValidationError("只支持按编号增量导入，不支持替换。", field="mode")
    return {"file_sha256": hashlib.sha256(content).hexdigest(), "format": file_format, "mode": mode, "scope": {}}


def table_descriptor(kind: str) -> Dict[str, Any]:
    """模板与填写说明生成器的唯一入口，12 张表统一形状。"""
    relation_kind(kind)
    columns = []
    for item in public_columns(kind):
        key = item["key"]
        columns.append({
            "key": key,
            # 标签就是文件里真正的表头，读取器按它认列，不能和 public_columns 不一致。
            "label": item["label"],
            "required": key in REQUIRED[kind],
            "readonly": key in READONLY[kind],
            "value_hint": _VALUE_HINTS[key],
            "error_hint": _ERROR_HINTS[key],
            "enum": ENUMS.get(key),
            "nullable": key in NULLABLE,
        })
    return {
        "table_id": kind,
        "display_name": DISPLAY_NAMES[kind],
        "sheet_name": SHEET_NAMES[kind],
        "file_stem": DISPLAY_NAMES[kind],
        "columns": columns,
        "general_rules": _GENERAL_RULES,
        "sample_rows": _SAMPLE_ROWS,
        "row_limit": IMPORT_ROW_LIMIT,
        "byte_limit": DEFAULT_IMPORT_BYTE_LIMIT,
        "modes": UPSERT_ONLY,
    }


@dataclass(frozen=True)
class RelationFileDownload:
    filename: str
    mime_type: str
    content: bytes
    row_count: int


#: 预检响应里的那段提示，和说明表的通用规则同一份来源。
INSTRUCTIONS = instructions_text(table_descriptor("operator_machine"))

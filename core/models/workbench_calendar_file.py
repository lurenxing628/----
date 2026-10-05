"""全局工作日历文件的列目录。文件只改列出的日期，不删除整行；清除某一天请用日历页的范围清除。"""

import hashlib
from typing import Any, Dict, Optional, Tuple

from core.errors import ValidationError
from core.models.calendar_period_columns import PERIOD_CLOCKS, PERIOD_COLUMNS, PERIOD_DAYS, period_column_label
from core.models.workbench_action_values import FileDownload
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_table_descriptor import (
    DEFAULT_IMPORT_BYTE_LIMIT,
    UPSERT_ONLY,
    instructions_text,
)

IMPORT_ROW_LIMIT = 2000
TEMPLATE_VERSION = 1
#: 导出与导入的日期跨度上限，与 roadmap 4.1 一致。
MAX_RANGE_DAYS = 1096
CALENDAR_KINDS = ("work_calendar", "operator_calendar")

WRITABLE: Dict[str, Tuple[str, ...]] = {
    "work_calendar": ("date", "day_type", "shift_hours", "efficiency", "allow_normal", "allow_urgent", "remark", "shift_start", "shift_end"),
    # 个人日历以班次起止为准，工时由系统算出来，所以工时是只读列，不在可写列里。
    "operator_calendar": ("operator_code", "date", "day_type", "shift_start", "shift_end", "efficiency",
                          "allow_normal", "allow_urgent", "remark"),
}
READONLY: Dict[str, Tuple[str, ...]] = {
    "work_calendar": (), "operator_calendar": ("operator_label", "shift_hours"),
}
REQUIRED: Dict[str, Tuple[str, ...]] = {
    "work_calendar": ("date",), "operator_calendar": ("operator_code", "date"),
}
NUMERIC: Dict[str, Tuple[str, ...]] = {
    "work_calendar": ("shift_hours", "efficiency"), "operator_calendar": ("efficiency",),
}
NULLABLE: Dict[str, Tuple[str, ...]] = {"work_calendar": ("remark", "shift_end"), "operator_calendar": ("remark", "shift_end")}
DATE_FIELDS: Dict[str, Tuple[str, ...]] = {"work_calendar": ("date",), "operator_calendar": ("date",)}
CLOCK_FIELDS: Dict[str, Tuple[str, ...]] = {"work_calendar": ("shift_start", "shift_end"), "operator_calendar": ("shift_start", "shift_end")}
CODE_FIELDS: Dict[str, Tuple[str, ...]] = {"work_calendar": (), "operator_calendar": ("operator_code",)}

LABELS = {
    "date": "日期", "day_type": "类型", "shift_hours": "可排工时（小时）", "efficiency": "效率（%）",
    "allow_normal": "允许普通件", "allow_urgent": "允许急件", "remark": "备注",
    "operator_code": "工号", "operator_label": "人员姓名", "shift_start": "班次开始", "shift_end": "班次结束",
}
#: 文件里写中文，落库写英文。留空表示这一项不改。
ENUMS = {
    "day_type": {"工作日": "work", "假期": "rest"},
    "allow_normal": {"是": "yes", "否": "no"},
    "allow_urgent": {"是": "yes", "否": "no"},
}
#: 领域层字段名对应的界面字段名；两个日历服务的 proposed_row 收的都是各自的界面字段名。
UI_FIELDS = {
    "work_calendar": {"day_type": "type", "shift_hours": "hours", "efficiency": "eff",
                      "allow_normal": "allowNormal", "allow_urgent": "allowUrgent", "remark": "note",
                      "shift_start": "shiftStart", "shift_end": "shiftEnd"},
    "operator_calendar": {"day_type": "type", "shift_start": "shiftStart", "shift_end": "shiftEnd",
                          "efficiency": "eff", "allow_normal": "allowNormal", "allow_urgent": "allowUrgent",
                          "remark": "note"},
}
SHEET_NAMES = {"work_calendar": "工作日历", "operator_calendar": "个人日历"}
DISPLAY_NAMES = {"work_calendar": "工作日历", "operator_calendar": "个人日历"}

_VALUE_HINTS = {
    "work_calendar": {
        "date": "YYYY-MM-DD，例如 2026-10-01；也接受 Excel 的日期格子",
        "day_type": "工作日 / 假期；留空保持原样，这一天原来没配置过就按默认规则定",
        "shift_hours": "0 到 24 的数字；只改工时时按班次开始重新推算结束；同时填起止时须一致",
        "shift_start": "24 小时制 HH:MM；留空不改；新增且未填时段或工时，采用页面配置的默认工作时间",
        "shift_end": "24 小时制 HH:MM；不晚于开始表示次日；清除填 \\N，按工时推算",
        "efficiency": "大于 0 且不超过 200 的数字，按百分比填；留空保持原样",
        "allow_normal": "是 / 否；留空保持原样",
        "allow_urgent": "是 / 否；留空保持原样",
        "remark": "随便写；要清除请填 \\N（大写）",
    },
    "operator_calendar": {
        "operator_code": "已存在的人员工号，例如 OP001",
        "date": "YYYY-MM-DD，例如 2026-10-01；也接受 Excel 的日期格子",
        "day_type": "工作日 / 假期；留空按工作日处理",
        "shift_start": "24 小时制的 HH:MM，例如 09:00；这一天原来就上班可以留空保持原样，其余上班的日子必须填",
        "shift_end": "24 小时制的 HH:MM；不晚于开始表示次日；旧单时段格式留空按工时推算",
        "efficiency": "大于 0 且不超过 200 的数字，按百分比填；留空保持原样",
        "allow_normal": "是 / 否；留空保持原样",
        "allow_urgent": "是 / 否；留空保持原样",
        "remark": "随便写；要清除请填 \\N（大写）",
        "operator_label": "导出时带出的人员姓名，导入时不看这一列",
        "shift_hours": "导出时带出的可排工时，由班次起止算出来，导入时不看这一列",
    },
}
_ERROR_HINTS = {
    "work_calendar": {
        "shift_start": "不是 08:00 这样的时刻",
        "shift_end": "不是 16:00 这样的时刻，或与所填工时不一致",
        "date": "留空、不是真实日期、或同一个日期在文件里出现了两次",
        "day_type": "填了工作日和假期以外的词",
        "shift_hours": "不是数字、小于 0 或大于 24",
        "efficiency": "不是数字、不大于 0 或大于 200",
        "allow_normal": "填了是和否以外的词",
        "allow_urgent": "填了是和否以外的词",
        "remark": "填了 \\N 以外的清除写法",
    },
    "operator_calendar": {
        "operator_code": "留空、有首尾空格、或这个工号在系统里找不到",
        "date": "留空、不是真实日期、或同一个人同一个日期在文件里出现了两次",
        "day_type": "填了工作日和假期以外的词",
        "shift_start": "这一天原来不上班却没填开始时刻，或者不是 09:00 这样的时刻",
        "shift_end": "不是 17:30 这样的时刻",
        "efficiency": "不是数字、不大于 0 或大于 200",
        "allow_normal": "填了是和否以外的词",
        "allow_urgent": "填了是和否以外的词",
        "remark": "填了 \\N 以外的清除写法",
        "operator_label": "这一列不校验",
        "shift_hours": "这一列不校验",
    },
}
_GENERAL_RULES = {
    "work_calendar": (
        "一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行，最早和最晚的日期相差不超过 " + str(MAX_RANGE_DAYS) + " 天。",
        "文件不会把任何一天恢复成默认规则；要恢复请到日历页用范围清除。",
        "类型填假期又填了工时，表示这一天放假加班：能排产，效率按排产设置里的假期效率算，"
        "日历页上这一天会显示成工作日。",
        "这一天原来没配置过、类型又留空时，按这个日期的默认规则定：周末算假期且不可排产。",
    ),
    "operator_calendar": (
        "一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行，最早和最晚的日期相差不超过 " + str(MAX_RANGE_DAYS) + " 天。",
        "只填这个人有特殊安排的日期，正常上班的日子不用填；按每人每天一行填，一年就会超过行数上限。",
        "某个人某一天填进来以后，这一天就整天按这里的安排排产，不再套用他的班次轮换，也不看全局工作日历。",
        "工时不用填，由班次起止算出来；导出时会带出算好的工时供核对。",
        "填假期时不用填班次，工时按 0 算，普通件和急件都不可排产。",
        "文件不会取消任何一天的特殊安排；要取消请到人员详情的「编辑个人日历」里按日期范围清除。",
    ),
}
_SAMPLE_ROWS: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "work_calendar": (
        ("2026-10-01", "假期", "0", "", "否", "否", "国庆", "08:00", ""),
        ("2026-10-11", "工作日", "8", "100", "是", "是", "调休上班", "08:00", "16:00"),
        ("2026-12-31", "假期", "4", "80", "是", "否", "放假加班半天", "08:00", "12:00"),
    ),
    "operator_calendar": (
        ("OP001", "2026-10-11", "工作日", "09:00", "17:30", "100", "是", "是", "调休上班"),
        ("OP001", "2026-10-12", "工作日", "22:00", "06:00", "90", "是", "否", "夜班"),
        ("OP002", "2026-10-11", "假期", "", "", "", "否", "否", "调休"),
    ),
}


# Existing start/end columns are the first period when a period count is supplied.
for _kind in CALENDAR_KINDS:
    WRITABLE[_kind] += PERIOD_COLUMNS
    CLOCK_FIELDS[_kind] += PERIOD_CLOCKS
    for _key in PERIOD_COLUMNS:
        LABELS[_key] = period_column_label(_key)
        _VALUE_HINTS[_kind][_key] = ("0 至 8；分段设置须填写总段数，0 表示不工作；留空保持原有设置"
                                   if _key == "period_count" else "当天 / 次日；留空按当天" if _key in PERIOD_DAYS
                                   else "HH:MM；分段设置时须完整填写所选各段的起止，首段使用班次开始和班次结束列")
        _ERROR_HINTS[_kind][_key] = "段数与所填时段不一致、重叠、倒序或跨越超过 24 小时"
    _SAMPLE_ROWS[_kind] = tuple(tuple(row) + ("",) * len(PERIOD_COLUMNS) for row in _SAMPLE_ROWS[_kind])
for _key in PERIOD_DAYS:
    ENUMS[_key] = {"当天": "当天", "次日": "次日"}


def calendar_kind(kind: str) -> str:
    if type(kind) is not str or kind not in CALENDAR_KINDS:
        raise WorkbenchCommandRejected("invalid_input", "不支持这类日历的文件操作，没有导入。请从日历页重新打开。", 400)
    return kind


def file_columns(kind: str) -> Tuple[str, ...]:
    return WRITABLE[calendar_kind(kind)] + READONLY[kind]


def public_columns(kind: str):
    result = []
    for key in file_columns(kind):
        label = LABELS[key]
        if key in READONLY[kind]:
            label += "（只读）"
        result.append({"key": key, "label": label})
    return result


def row_identity(kind: str, values: Dict[str, Any]) -> Optional[str]:
    """预检行对用户显示的标识：全局日历是日期，个人日历是"工号 / 日期"。"""
    day = values.get("date")
    if type(day) is not str:
        return None
    if kind == "work_calendar":
        return day
    code = values.get("operator_code")
    return code + " / " + day if type(code) is str else None


def import_request(kind: str, content: bytes, file_format: str, mode: str) -> Dict[str, Any]:
    calendar_kind(kind)
    if type(content) is not bytes or file_format not in ("csv", "xlsx"):
        raise ValidationError("只能导入 CSV 或 XLSX 文件，没有导入。请重新选择文件。", field="file")
    if mode != "upsert":
        raise WorkbenchCommandRejected("invalid_input", "日历文件只支持按日期增量导入，没有导入。请重新选择导入方式。", 400)
    return {"kind": kind, "mode": mode, "format": file_format, "scope": {},
            "file_sha256": hashlib.sha256(content).hexdigest()}


def table_descriptor(kind: str) -> Dict[str, Any]:
    """模板与填写说明生成器的唯一入口，12 张表统一形状。"""
    calendar_kind(kind)
    return {
        "table_id": kind,
        "display_name": DISPLAY_NAMES[kind],
        "sheet_name": SHEET_NAMES[kind],
        "file_stem": DISPLAY_NAMES[kind],
        # 标签就是文件里真正的表头，读取器按它认列，不能和 public_columns 不一致。
        "columns": [{"key": item["key"], "label": item["label"],
                     "required": item["key"] in REQUIRED[kind],
                     "readonly": item["key"] in READONLY[kind],
                     "value_hint": _VALUE_HINTS[kind][item["key"]],
                     "error_hint": _ERROR_HINTS[kind][item["key"]],
                     "enum": tuple(ENUMS[item["key"]]) if item["key"] in ENUMS
                     and item["key"] not in READONLY[kind] else None,
                     "nullable": item["key"] in NULLABLE[kind]}
                    for item in public_columns(kind)],
        "general_rules": _GENERAL_RULES[kind],
        "sample_rows": _SAMPLE_ROWS[kind],
        "row_limit": IMPORT_ROW_LIMIT,
        "byte_limit": DEFAULT_IMPORT_BYTE_LIMIT,
        "modes": UPSERT_ONLY,
    }


CalendarFileDownload = FileDownload


#: 预检响应里的那段提示，和说明表的通用规则同一份来源。
INSTRUCTIONS = {kind: instructions_text(table_descriptor(kind)) for kind in CALENDAR_KINDS}

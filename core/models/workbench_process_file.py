"""Process file transport only; no preview, database or group creation policy.

Rows are sparse canonical mappings. Missing keys / empty cells omit an update;
explicit nulls survive as None for the domain to validate. Assertion columns
are parsed, never resolved here. Row diagnostics do not authorize partial apply.
"""

from core.errors import ValidationError
from core.models.workbench_action_values import FileDownload
from core.models.workbench_resource_file import IMPORT_ROW_LIMIT
from core.models.workbench_table_descriptor import (
    DEFAULT_IMPORT_BYTE_LIMIT,
    UPSERT_ONLY,
    instructions_text,
)

COLUMNS = {
    "route": ("business_code", "label", "route_raw", "remark"),
    "hours": ("business_code", "sequence", "op_type_name", "source", "setup_hours", "unit_hours",
              "external_days", "group_start", "group_end", "group_total_days"),
}
LABELS = {
    "business_code": "图号", "label": "名称", "route_raw": "工艺路线", "remark": "备注",
    "sequence": "工序", "op_type_name": "工种", "source": "归属", "setup_hours": "换型时间(h)",
    "unit_hours": "单件工时(h)", "external_days": "外协周期(天)", "group_start": "外协组起序",
    "group_end": "外协组止序", "group_total_days": "合并周期(天)",
}
REQUIRED = {"route": ("business_code",), "hours": ("business_code", "sequence")}
INTEGER_FIELDS = frozenset(("sequence", "group_start", "group_end"))
NUMBER_FIELDS = frozenset(("setup_hours", "unit_hours", "external_days", "group_total_days"))
SOURCE_VALUES = {"自制": "internal", "外协": "external", "internal": "internal", "external": "external"}
SOURCE_LABELS = {"internal": "自制", "external": "外协"}
TEMPLATE_VERSION = 1
INT64_MAX = 9223372036854775807
XLSX_EXACT_INTEGER_MAX = 2 ** 53
# 上限的唯一来源是表描述协议，别在这里另写一份 16MB：注释写着"Matches Config"，
# 可两边都是独立字面量，改一边不会有任何东西红。app_config.EXCEL_MAX_UPLOAD_BYTES 也取这个值。
IMPORT_BYTE_LIMIT = DEFAULT_IMPORT_BYTE_LIMIT
XLSX_EXPANDED_BYTE_LIMIT = 64 * 1024 * 1024


DISPLAY_NAMES = {"route": "零件工艺路线", "hours": "零件工序工时"}
SHEET_NAMES = {"route": "工艺路线", "hours": "工序工时"}
NULLABLE = frozenset(("remark", "external_days"))
ENUMS = {"source": tuple(SOURCE_LABELS.values())}
#: 图号和名称在两张表里含义不同：路线表能新建零件，工时表只改已有工序，所以两份提示不能共用。
_KIND_HINTS = {
    "route": {
        "business_code": ("零件图号，例如 P-001；系统里没有这个图号就新增一个零件",
                          "留空、有首尾空格、或同一份文件里出现了两次"),
        "label": ("零件名称；新增零件时必须填，已有的留空保持原样",
                  "新增零件时留空，或填了系统不接受的字符"),
    },
    "hours": {
        "business_code": ("已存在的零件图号，例如 P-001；工时导入不会新增零件",
                          "留空、有首尾空格、或这个图号在系统里找不到"),
    },
}
_VALUE_HINTS = {
    "business_code": "零件图号，例如 P-001",
    "label": "零件名称；留空保持原样",
    "route_raw": "一格填写整条路线，例如 10: 车削；20: 钻孔；30: 热处理；留空保持原样",
    "remark": "随便写；要清除请填 \\N（大写）",
    "sequence": "工序号，正整数，例如 10",
    "op_type_name": "工种名，只用来核对原记录，不改工种",
    "source": "自制 / 外协，只用来核对原记录",
    "setup_hours": "换型时间，单位小时，填非负数字；留空保持原样，不支持清除已填工时",
    "unit_hours": "单件工时，单位小时，填非负数字；留空保持原样，不支持清除已填工时",
    "external_days": "外协周期天数，填正数；留空保持原样；合并组优先使用合并周期",
    "group_start": "外协组的起始工序号，只用来核对原记录",
    "group_end": "外协组的结束工序号，只用来核对原记录",
    "group_total_days": "每个合并外协组只在第一道工序填一次正数天数，其余成员留空；不新增组或改范围",
}
_ERROR_HINTS = {
    "business_code": "留空、有首尾空格、或这个图号在系统里找不到",
    "label": "填了系统不接受的字符",
    "route_raw": "缺少工序号、序号重复或路线分隔不明确；已有路线不能通过导入清除",
    "remark": "填了 \\N 以外的清除写法",
    "sequence": "不是正整数、填了 TRUE 或 FALSE、或同一个图号里这个工序号出现了两次",
    "op_type_name": "和原记录里的工种对不上",
    "source": "填了自制和外协以外的词，或者和原记录对不上",
    "setup_hours": "不是数字，或者填了 TRUE、FALSE",
    "unit_hours": "不是数字，或者填了 TRUE、FALSE",
    "external_days": "不是数字，或者这道工序不是外协",
    "group_start": "和原记录里的外协组起序对不上",
    "group_end": "和原记录里的外协组止序对不上",
    "group_total_days": "不是数字，或者这几道工序不在同一个外协组里",
}
_GENERAL_RULES = {
    "route": (
        "一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行。",
        "按图号增量更新：图号已有的改写，没有的新增一个零件；文件里没列出的零件完全不动，不会被删除。",
        "每个零件仍占一行，整条路线填写在一个格子里；例如 10: 车削；20: 热处理；30: 精磨。原来的紧凑路线也可继续导入。",
        "空格子表示保持原样。完全空白行会略过；已有路线不能在文件里清除，备注需要清除时可填 \\N（大写）。",
        "请核对预检中每道工序的名称和增删改，再确认导入。",
    ),
    "hours": (
        "一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行。",
        "按「图号 + 工序号」增量更新：只改已有工序，不新增零件也不新增工序；没列出的工序完全不动，不会被删除。",
        "空格子表示保持原样，完全空白行会略过；已填的换型时间、单件工时和合并周期不能在文件里清除。",
        "工种、归属、外协组起止序只用来核对原记录，改不了它们。",
        "合并周期在每组第一道工序填一次，其余成员留空；只改原组周期，不新增组，也不调整组范围。",
        "空白工时不会补零，周期也不会自动补一天。",
        "工序号和组起止序必须是正整数；很大的数请按文本填。",
    ),
}
_SAMPLE_ROWS = {
    "route": (("P-001", "法兰盘", "10: 车削；20: 钻孔；30: 热处理", "常规件"),
              ("P-002", "轴套", "10: 车削；20: 磨削", "")),
    "hours": (("P-001", "10", "车削", "自制", "0.5", "0.25", "", "", "", ""),
              ("P-001", "30", "热处理", "外协", "", "", "3", "30", "40", "5")),
}


def table_descriptor(kind):
    """模板与填写说明生成器的唯一入口，12 张表统一形状。"""
    columns = []
    for field in file_columns(kind):
        value_hint, error_hint = _KIND_HINTS[kind].get(field, (_VALUE_HINTS[field], _ERROR_HINTS[field]))
        columns.append({
            "key": field,
            "label": LABELS[field],
            "required": field in REQUIRED[kind],
            # 工艺文件没有只读参考列：核对用的列本身也要填，只是改不动原记录。
            "readonly": False,
            "value_hint": value_hint,
            "error_hint": error_hint,
            "enum": ENUMS.get(field),
            "nullable": field in NULLABLE,
        })
    return {
        "table_id": kind,
        "display_name": DISPLAY_NAMES[kind],
        "sheet_name": SHEET_NAMES[kind],
        "file_stem": DISPLAY_NAMES[kind],
        "columns": columns,
        "general_rules": _GENERAL_RULES[kind],
        "sample_rows": _SAMPLE_ROWS[kind],
        "row_limit": IMPORT_ROW_LIMIT,
        "byte_limit": IMPORT_BYTE_LIMIT,
        "modes": UPSERT_ONLY,
    }


def file_error(message, row=1, field="file"):
    return ValidationError(message, field=field, details={"row": row})


def file_columns(kind):
    if type(kind) is not str or kind not in COLUMNS:
        raise file_error("文件类型只能是工艺路线或工序工时。", field="kind")
    return COLUMNS[kind]


def check_format(file_format):
    if type(file_format) is not str or file_format not in ("csv", "xlsx"):
        raise file_error("工艺文件仅支持 CSV 和 XLSX。", field="format")


def public_columns(kind):
    return [{"key": field, "label": LABELS[field]} for field in file_columns(kind)]


ProcessFileDownload = FileDownload


#: 预检响应里的那段提示，和说明表的通用规则同一份来源。工艺路线与工序工时各一份。
INSTRUCTIONS = {kind: instructions_text(table_descriptor(kind)) for kind in COLUMNS}

"""Process file transport only; no preview, database or group creation policy.

Rows are sparse canonical mappings. Missing keys / empty cells omit an update;
explicit nulls survive as None for the domain to validate. Assertion columns
are parsed, never resolved here. Row diagnostics do not authorize partial apply.
"""

from dataclasses import dataclass

from core.errors import ValidationError
from core.models.workbench_resource_file import IMPORT_ROW_LIMIT

COLUMNS = {
    "route": ("business_code", "label", "route_raw", "remark"),
    "hours": ("business_code", "sequence", "op_type_name", "source", "setup_hours", "unit_hours",
              "external_days", "group_start", "group_end", "group_total_days"),
}
LABELS = {
    "business_code": "图号", "label": "名称", "route_raw": "工艺路线字符串", "remark": "备注",
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
INSTRUCTIONS = ("图号必须是文本；缺列或空单元格不更新，\\N 表示明确清除，能不能清除由预检决定。"
                "文字开头的反斜线要写两个；CSV 文字有一层可逆单引号，空格和换行保留。"
                "工序号和组起止序必须是正整数，很大的数用文本填。工种、归属和组起止序只用来核对原记录；"
                "合并周期只用来改原来的组周期，不新增也不调整组范围。空白工时不补零，周期不自动补一天。")
INT64_MAX = 9223372036854775807
XLSX_EXACT_INTEGER_MAX = 2 ** 53
# Matches Config.EXCEL_MAX_UPLOAD_BYTES; this core contract does not import Flask/config.
IMPORT_BYTE_LIMIT = 16 * 1024 * 1024
XLSX_EXPANDED_BYTE_LIMIT = 64 * 1024 * 1024


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


@dataclass(frozen=True)
class ProcessFileDownload:
    filename: str
    mime_type: str
    content: bytes
    row_count: int

"""Batch XLSX uses the existing eight-column template, without advanced switches."""

HEADERS = ("批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注")
COLUMNS = ("business_code", "part_no", "quantity", "due_date", "priority", "ready_status", "ready_date", "remark")
HEADER_FIELDS = dict(zip(HEADERS, COLUMNS))
MAX_ROWS = 5000
MAX_BYTES = 10 * 1024 * 1024
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#: 导出时会多带一列「状态」供核对，导入时不看它；这里按导入列目录给。
REQUIRED = ("business_code", "part_no", "quantity", "due_date")
ENUMS = {"priority": ("普通", "急件", "特急"), "ready_status": ("齐套", "未齐套", "部分齐套")}
_VALUE_HINTS = {
    "business_code": "批次号，例如 B001；不填就不知道改哪一条",
    "part_no": "已存在的零件图号，例如 A1234",
    "quantity": "数量，填正整数，不要带单位",
    "due_date": "交期，填成 2026-01-25 这样的年月日，不要带时分",
    "priority": "普通 / 急件 / 特急",
    "ready_status": "齐套 / 未齐套 / 部分齐套",
    "ready_date": "齐套日期，填成 2026-01-25 这样的年月日；没有就留空",
    "remark": "随便写",
}
_ERROR_HINTS = {
    "business_code": "留空、有首尾空格、或同一份文件里出现了两次",
    "part_no": "留空，或者这个图号在系统里找不到",
    "quantity": "不是正整数，或者填了「是/否」",
    "due_date": "留空、不是真实日期、或者带了时分",
    "priority": "填了普通、急件、特急以外的词",
    "ready_status": "填了齐套、未齐套、部分齐套以外的词",
    "ready_date": "不是真实日期，或者带了时分",
    "remark": "基本不会报错",
}
_GENERAL_RULES = (
    "一次最多 " + str(MAX_ROWS) + " 行。",
    "批次号、图号必须是文本；日期只填年月日，不要带时分。",
    "已有批次的空格子不覆盖原值；新批次不会自动生成工序。",
    "导出文件会多一列「状态」供核对，导入时不看这一列。",
)
_SAMPLE_ROWS = (
    ("B001", "A1234", "50", "2026-01-25", "急件", "齐套", "", "示例"),
    ("B002", "A1234", "120", "2026-02-10", "普通", "未齐套", "2026-02-05", ""),
)


def table_descriptor(_kind=None):
    """模板与填写说明生成器的唯一入口，12 张表统一形状。批次只有一张表，不分 kind。"""
    columns = [{
        "key": key,
        "label": HEADERS[index],
        "required": key in REQUIRED,
        "readonly": False,
        "value_hint": _VALUE_HINTS[key],
        "error_hint": _ERROR_HINTS[key],
        "enum": ENUMS.get(key),
        "nullable": False,
    } for index, key in enumerate(COLUMNS)]
    return {
        "table_id": "batch",
        "display_name": "批次信息",
        "sheet_name": "批次信息",
        "file_stem": "批次信息",
        "columns": columns,
        "general_rules": _GENERAL_RULES,
        "sample_rows": _SAMPLE_ROWS,
        "row_limit": MAX_ROWS,
        "byte_limit": MAX_BYTES,
        "modes": ("已有批次就更新，没有的就新增", "只新增没有的批次（已有的跳过）", "先清除全部批次，再按表格重导"),
    }

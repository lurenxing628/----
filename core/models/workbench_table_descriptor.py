"""12 张导入表共用的表描述协议，以及「填写说明」表的内容生成。

各家族的列目录模块各自导出 `table_descriptor(kind)`，形状由这里定死并由门禁逐张校验。
模板和导出文件里的第二张表只由这里生成一份，不让各家族各写一段说明文字，避免同一条规则
在说明表、弹窗提示、用户文档里各写各的。

这里只产出数据，不碰 openpyxl；怎么落到工作簿里见 `core/services/common/excel_instruction_sheet.py`。
"""

from typing import Any, Dict, List, Sequence, Tuple

#: 第二张工作表的固定名字。读取器一律只读第一张，所以这个名字不参与导入判定，只给用户看。
INSTRUCTION_SHEET = "填写说明"

#: 上传文件本体的默认大小上限。多数表用它，批次和报工在自己的列目录里给更小的值。
#: `web/bootstrap/app_config.py` 的 EXCEL_MAX_UPLOAD_BYTES 从这里取，不再各写一份：
#: 原来说明书写"统一 16MB"，而批次实际是 10MB、报工是 8MB，三处各说各的。
DEFAULT_IMPORT_BYTE_LIMIT = 16 * 1024 * 1024

#: 写入方式（导入模式）。只有批次这一张表让用户选，其余一律按编号增量更新。
#: 说明书里"三种导入模式"曾被写到人员和日历头上，那两处根本没有这个选项。
UPSERT_ONLY = ("已有的就更新，没有的就新增",)

_HEADER = ("列名", "必填", "能填什么", "会报错的情况")
_TEXT_KEYS = ("table_id", "display_name", "sheet_name", "file_stem")
_COLUMN_TEXT = ("key", "label", "value_hint", "error_hint")
_COLUMN_FLAGS = ("required", "readonly", "nullable")
_DESCRIPTOR_KEYS = (*_TEXT_KEYS, "columns", "general_rules", "sample_rows", "row_limit",
                    "byte_limit", "modes")


def extra_sheet_notice(sheet_count: int) -> List[Dict[str, str]]:
    """文件里还有别的工作表时的整批级告知。12 张表一律只读第一张，其余忽略但要说出来。

    不收紧成"多一张就拒绝"：用户手里第二张表放着自己备注的现有文件会突然导不进去，
    而模板和导出文件本身就带一张「填写说明」。
    """
    if sheet_count <= 1:
        return []
    return [{"code": "first_sheet_only",
             "message": "这个文件里有 " + str(sheet_count) + " 张工作表，只读了第一张，其余的没有导入。"}]


def _fail(message: str, descriptor: Any) -> None:
    raise ValueError("表描述不符合协议：" + message + "（" + repr(descriptor)[:200] + "）")


def _nonempty_text(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _check_column_enum(column: Dict[str, Any]) -> None:
    choices = column["enum"]
    if choices is None:
        return
    if type(choices) is not tuple or not choices or any(not _nonempty_text(item) for item in choices):
        _fail("列的可选值要么不给，要么是非空文字元组", column)


def _check_column(column: Any) -> None:
    if type(column) is not dict or set(column) != {*_COLUMN_TEXT, *_COLUMN_FLAGS, "enum"}:
        _fail("列定义的项目不对", column)
    for key in _COLUMN_TEXT:
        if not _nonempty_text(column[key]):
            _fail("列的 " + key + " 必须是非空文字", column)
    for key in _COLUMN_FLAGS:
        if type(column[key]) is not bool:
            _fail("列的 " + key + " 只能是 True 或 False", column)
    _check_column_enum(column)
    if column["readonly"] and column["required"]:
        _fail("只读列不能同时是必填列", column)


def _check_columns(descriptor: Dict[str, Any]) -> None:
    columns = descriptor["columns"]
    if type(columns) is not list or not columns:
        _fail("columns 必须是非空列表", descriptor)
    for column in columns:
        _check_column(column)
    names = [column["key"] for column in columns]
    if len(set(names)) != len(names):
        _fail("列的标识有重复", descriptor)


def _check_rules(descriptor: Dict[str, Any]) -> None:
    rules = descriptor["general_rules"]
    if type(rules) is not tuple or not rules or any(not _nonempty_text(rule) for rule in rules):
        _fail("general_rules 必须是非空文字元组", descriptor)
    if type(descriptor["row_limit"]) is not int or descriptor["row_limit"] < 1:
        _fail("row_limit 必须是大于零的整数", descriptor)


def check_table_descriptor(descriptor: Any) -> Dict[str, Any]:
    """协议校验。这是内部契约，不是用户输入，违反就是代码错误，直接抛。"""
    if type(descriptor) is not dict or set(descriptor) != set(_DESCRIPTOR_KEYS):
        _fail("顶层项目不对，应为 " + "、".join(_DESCRIPTOR_KEYS), descriptor)
    for key in _TEXT_KEYS:
        if not _nonempty_text(descriptor[key]):
            _fail(key + " 必须是非空文字", descriptor)
    _check_columns(descriptor)
    _check_rules(descriptor)
    _check_samples(descriptor)
    _check_limits(descriptor)
    return descriptor


def _check_limits(descriptor: Dict[str, Any]) -> None:
    if type(descriptor["byte_limit"]) is not int or descriptor["byte_limit"] <= 0:
        _fail("byte_limit 必须是大于 0 的整数字节数", descriptor)
    modes = descriptor["modes"]
    if type(modes) is not tuple or not modes or any(not _nonempty_text(mode) for mode in modes):
        _fail("modes 必须是至少一条非空文字的元组，写用户在界面上看到的那句话", descriptor)


def _check_samples(descriptor: Dict[str, Any]) -> None:
    width = len(writable_columns(descriptor))
    samples = descriptor["sample_rows"]
    if type(samples) is not tuple or not 1 <= len(samples) <= 5:
        _fail("sample_rows 必须是 1 到 5 行的元组", descriptor)
    for sample in samples:
        if type(sample) is not tuple or len(sample) != width:
            _fail("示例行必须按可填列逐列给值，应有 " + str(width) + " 个", sample)
        if any(type(value) is not str for value in sample):
            _fail("示例行只能写文字，导出时才知道格子类型", sample)


def writable_columns(descriptor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """用户真正要填的列。只读参考列不算，示例行也按这个宽度给。"""
    return [column for column in descriptor["columns"] if not column["readonly"]]


def enum_columns(descriptor: Dict[str, Any]) -> List[Tuple[int, Sequence[str]]]:
    """要挂下拉的列，返回在数据表里的 1 起列号。只读列不挂，它不该被改。"""
    return [(index, column["enum"]) for index, column in enumerate(descriptor["columns"], 1)
            if column["enum"] is not None and not column["readonly"]]


def _duty(column: Dict[str, Any]) -> str:
    if column["readonly"]:
        return "只读，不导入"
    return "必填" if column["required"] else "选填"


def cell_notes(descriptor: Dict[str, Any]) -> List[str]:
    """模板表头每一列的批注。只留一句示例值，规则一律去说明表看，避免同一段话贴满整行。"""
    check_table_descriptor(descriptor)
    sample, position, notes = descriptor["sample_rows"][0], 0, []
    for column in descriptor["columns"]:
        if column["readonly"]:
            notes.append("这是只读列，导入时不看这一列。规则见「" + INSTRUCTION_SHEET + "」表。")
            continue
        value = sample[position]
        position += 1
        notes.append(("示例：" + value + "。" if value else "这一列可以留空。")
                     + "规则见「" + INSTRUCTION_SHEET + "」表。")
    return notes


def instructions_text(descriptor: Dict[str, Any]) -> str:
    """预检响应里那一段提示。就是说明表的通用规则接起来，不另写一份。"""
    check_table_descriptor(descriptor)
    return "".join(descriptor["general_rules"])


def instruction_rows(descriptor: Dict[str, Any]) -> List[List[str]]:
    """「填写说明」表的全部行。列说明、通用规则、完整示例三段，中间空行分隔。"""
    check_table_descriptor(descriptor)
    rows: List[List[str]] = [[descriptor["display_name"] + "导入填写说明"], list(_HEADER)]
    rows.extend([column["label"], _duty(column), column["value_hint"], column["error_hint"]]
                for column in descriptor["columns"])
    rows.append([])
    rows.append(["通用规则"])
    rows.extend([rule] for rule in descriptor["general_rules"])
    rows.append([])
    rows.append(["示例：照下面这样填在第一张「" + descriptor["sheet_name"] + "」表里"])
    rows.append([column["label"] for column in writable_columns(descriptor)])
    rows.extend(list(sample) for sample in descriptor["sample_rows"])
    return rows

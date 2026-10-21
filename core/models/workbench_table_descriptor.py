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


def extra_sheet_notice(sheet_count: int) -> List[Dict[str, str]]:
    """文件里还有别的工作表时的整批级告知。12 张表一律只读第一张，其余忽略但要说出来。

    不收紧成"多一张就拒绝"：用户手里第二张表放着自己备注的现有文件会突然导不进去，
    而模板和导出文件本身就带一张「填写说明」。
    """
    if sheet_count <= 1:
        return []
    return [{"code": "first_sheet_only",
             "message": "这个文件里有 " + str(sheet_count) + " 张工作表，只读了第一张，其余的没有导入。"}]


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
    return "".join(descriptor["general_rules"])


def instruction_rows(descriptor: Dict[str, Any]) -> List[List[str]]:
    """「填写说明」表的全部行。列说明、通用规则、完整示例三段，中间空行分隔。"""
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

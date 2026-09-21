"""从表描述协议生成说明书里各张导入表的列说明，写进标记区间。

用法：
  python3 -m tools.generate_table_docs --check    # 比对，不一致退出码 1
  python3 -m tools.generate_table_docs --write    # 重新生成并写回

为什么是"工具生成 + 门禁比对"而不是"人写文档 + 测试解析表格比对"：后者格式微调就会误报，
而且列说明和模板里的「填写说明」表本来就该是同一份东西。散文段落仍然人工撰写，不进这个门禁。
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List

from core.models.workbench_table_catalog import all_descriptors, table_descriptor
from core.models.workbench_table_descriptor import INSTRUCTION_SHEET, writable_columns

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUAL = REPO_ROOT / "static/docs/scheduler_manual.md"
BEGIN = "<!-- APS-TABLE-DOC:BEGIN "
END = "<!-- APS-TABLE-DOC:END -->"
_HINT = "<!-- 这一段由 python3 -m tools.generate_table_docs --write 生成，请勿手改。 -->"


def _cell(text: str) -> str:
    """Markdown 表格里竖线要转义，不然会把一列劈成两列。"""
    return str(text).replace("|", "\\|")


def _duty(column: Dict[str, object]) -> str:
    if column["readonly"]:
        return "只读"
    return "是" if column["required"] else "否"


def columns_table(descriptor: Dict[str, object]) -> List[str]:
    rows = ["| 列名 | 必填 | 能填什么 | 会报错的情况 |", "|---|---|---|---|"]
    for column in descriptor["columns"]:
        rows.append("| " + " | ".join([_cell(column["label"]), _duty(column),
                                       _cell(column["value_hint"]), _cell(column["error_hint"])]) + " |")
    return rows


def rules_list(descriptor: Dict[str, object]) -> List[str]:
    return ["- " + _cell(rule) for rule in descriptor["general_rules"]]


def sample_table(descriptor: Dict[str, object]) -> List[str]:
    labels = [column["label"] for column in writable_columns(descriptor)]
    rows = ["| " + " | ".join(_cell(label) for label in labels) + " |",
            "|" + "---|" * len(labels)]
    for sample in descriptor["sample_rows"]:
        rows.append("| " + " | ".join(_cell(value) if value else " " for value in sample) + " |")
    return rows


def table_section(descriptor: Dict[str, object]) -> List[str]:
    """一张表的完整说明：列表格、通用规则、示例。内容和模板里的「填写说明」表同源。"""
    lines = [_HINT, ""]
    lines.extend(columns_table(descriptor))
    lines.extend(["", "规则：", ""])
    lines.extend(rules_list(descriptor))
    lines.extend(["", "照着填的例子：", ""])
    lines.extend(sample_table(descriptor))
    lines.extend(["", "下载到的文件里，第一张表是数据表，第二张固定叫「" + INSTRUCTION_SHEET
                  + "」，写的就是上面这些内容。", ""])
    return lines


def _overview_name(descriptor: Dict[str, object], seen: List[str]) -> str:
    """报工的两个格式版本同名同表，只有列数不同；同名时把列数标出来，用户才知道拿到的是哪一版。"""
    name = str(descriptor["display_name"])
    if seen.count(name) > 1:
        return name + "（" + str(len(writable_columns(descriptor))) + " 列）"
    return name


def overview_section() -> List[str]:
    """总表：有哪些表、各有多少列、一次最多多少行。"""
    lines = [_HINT, "",
             "| 表 | 工作表名 | 可填列 | 只读参考列 | 一次最多 | 文件上限 | 写入方式 |",
             "|---|---|---:|---:|---:|---:|---|"]
    descriptors = all_descriptors()
    names = [str(descriptor["display_name"]) for descriptor in descriptors]
    for descriptor in descriptors:
        writable = len(writable_columns(descriptor))
        lines.append("| " + " | ".join([
            _cell(_overview_name(descriptor, names)), _cell(descriptor["sheet_name"]),
            str(writable), str(len(descriptor["columns"]) - writable), str(descriptor["row_limit"]),
            _megabytes(descriptor["byte_limit"]), _cell(" / ".join(descriptor["modes"])),
        ]) + " |")
    lines.append("")
    return lines


def _megabytes(byte_limit: object) -> str:
    """上限一律按整 MB 写；协议要求是正整数字节，不到 1MB 的表目前没有。"""
    return str(int(byte_limit) // (1024 * 1024)) + "MB"


def _generate(name: str) -> List[str]:
    if name == "overview":
        return overview_section()
    return table_section(table_descriptor(name))


def render(text: str) -> str:
    """把每个标记区间里的内容换成重新生成的结果，区间外一个字不动。"""
    lines, result, index = text.split("\n"), [], 0
    while index < len(lines):
        line = lines[index]
        result.append(line)
        if not line.startswith(BEGIN):
            index += 1
            continue
        name = line[len(BEGIN):].split("-->")[0].strip()
        closing = next((offset for offset in range(index + 1, len(lines)) if lines[offset].strip() == END), None)
        if closing is None:
            raise SystemExit("标记区间没有收尾：" + line)
        result.extend(_generate(name))
        result.append(END)
        index = closing + 1
    return "\n".join(result)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="重新生成并写回说明书")
    parser.add_argument("--check", action="store_true", help="比对，不一致退出码 1")
    parser.add_argument("--path", default=str(MANUAL), help="要处理的 Markdown 文件")
    args = parser.parse_args(argv)
    if args.write == args.check:
        parser.error("请选 --write 或 --check 其中一个。")
    path = Path(args.path)
    current = path.read_text(encoding="utf-8")
    expected = render(current)
    if args.write:
        if expected != current:
            path.write_text(expected, encoding="utf-8")
            print("已重新生成：" + str(path))
        else:
            print("没有变化：" + str(path))
        return 0
    if expected != current:
        print("说明书里的列说明和表描述对不上。请跑：python3 -m tools.generate_table_docs --write")
        return 1
    print("列说明与表描述一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

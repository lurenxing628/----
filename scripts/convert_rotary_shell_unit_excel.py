from __future__ import annotations

import argparse
import os
import sys
from typing import Dict


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录（要求存在 app.py 与 schema.sql）")


def _default_input_path(repo_root: str) -> str:
    return os.path.join(repo_root, "templates_excel", "回转壳体单元产品数据.xlsx")


def _default_output_dir(repo_root: str) -> str:
    return os.path.join(repo_root, "templates_excel", "转换输出")


def _print_paths(paths: Dict[str, str]) -> None:
    print("输出文件：")
    for filename in sorted(paths.keys()):
        print(f"- {filename}: {paths[filename]}")


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    repo_root = _find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process import UnitExcelConverter

    parser = argparse.ArgumentParser(
        description="把回转壳体单元实际运行数据转换为 APS 标准导入模板（工步并工序，去掉技能等级/主操）。"
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=_default_input_path(repo_root),
        help="源 Excel 路径（默认：templates_excel/回转壳体单元产品数据.xlsx）",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=_default_output_dir(repo_root),
        help="输出目录（默认：templates_excel/转换输出）",
    )
    parser.add_argument(
        "--sheet",
        dest="sheet_name",
        default=None,
        help="可选：指定 Sheet 名称（默认读取第一个 Sheet）",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input_path)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.exists(input_path):
        print(f"错误：源文件不存在：{input_path}")
        return 2

    converter = UnitExcelConverter()
    converted = converter.convert(input_path=input_path, sheet_name=args.sheet_name)
    paths = converter.write_templates(converted=converted, output_dir=output_dir)

    print("转换完成。")
    _print_paths(paths)
    print("")
    print("关键口径：")
    print("- 仅“有工步(XX-X)+有人员”的工序判为内部；其余按外协。")
    print("- 工步时间会累计成工序时间，并输出“零件工序工时.xlsx”。")
    print("- 人员设备关联仅输出 工号/设备编号 两列。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


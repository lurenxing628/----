import importlib
import inspect
import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    module = importlib.import_module("core.services.process.unit_excel_converter")
    source = inspect.getsource(module)
    if source.count("class UnitExcelConverter") != 1:
        raise RuntimeError("unit_excel_converter.py 中 UnitExcelConverter 定义数量不为 1")

    from core.services.process import UnitExcelConverter
    from core.services.process.unit_excel_converter import ConvertedTemplates, PartContext, StationMeta, StepRecord

    conv = UnitExcelConverter()
    if not hasattr(conv, "_parser") or not hasattr(conv, "_builder") or not hasattr(conv, "_exporter"):
        raise RuntimeError("UnitExcelConverter 未绑定 façade 依赖成员（_parser/_builder/_exporter）")
    if hasattr(conv, "_build_templates"):
        raise RuntimeError("检测到旧实现私有方法 _build_templates，清理不完整")

    if not hasattr(ConvertedTemplates, "output_specs"):
        raise RuntimeError("ConvertedTemplates 兼容别名失效（缺少 output_specs）")
    if StationMeta is None or StepRecord is None or PartContext is None:
        raise RuntimeError("StationMeta/StepRecord/PartContext 兼容别名失效")

    print("OK")


if __name__ == "__main__":
    main()

"""回归测试：templates_excel/转换输出/ 下「工种配置.xlsx」「供应商配置.xlsx」的交付内容须与当前 UnitExcelConverter 转换结果及模板定义（get_template_definition）保持一致——校验表头与转换结果逐行相等，且供应商启用列只取「启用/停用」。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, List, Sequence

import pytest
from openpyxl import load_workbook

from tests._support.paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.services.common.excel_templates import get_template_definition
from core.services.process import UnitExcelConverter
from core.services.process.unit_excel.exporter import UnitTemplateExporter


def _nonempty_rows(ws: Any, width: int) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for row_idx in range(2, ws.max_row + 1):
        values = [ws.cell(row_idx, col_idx).value for col_idx in range(1, width + 1)]
        if any(value not in (None, "") for value in values):
            rows.append(values)
    return rows


def _read_workbook_rows(path: Path, headers: Sequence[str]) -> List[List[Any]]:
    workbook = load_workbook(path, data_only=True)
    try:
        return _nonempty_rows(workbook.active, len(headers))
    finally:
        workbook.close()


def _skip_without_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("平台不支持软链接")
    target = tmp_path / "_symlink_probe_target"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "_symlink_probe"
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"平台不允许创建软链接：{exc}")
    finally:
        try:
            link.unlink()
        except OSError:
            pass


def _skip_without_hardlink(tmp_path: Path) -> None:
    target = tmp_path / "_hardlink_probe_target"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "_hardlink_probe"
    try:
        os.link(str(target), str(link))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"平台不允许创建硬链接：{exc}")
    finally:
        try:
            link.unlink()
        except OSError:
            pass


def test_op_type_conversion_output_matches_current_converter_result_and_layout() -> None:
    filename = "工种配置.xlsx"
    definition = get_template_definition(filename)
    headers = [str(item) for item in definition.get("headers") or []]
    path = REPO_ROOT / "templates_excel" / "转换输出" / filename
    source_path = REPO_ROOT / "templates_excel" / "回转壳体单元产品数据.xlsx"
    expected_rows = [
        [row.get(header) for header in headers]
        for row in UnitExcelConverter().convert(str(source_path)).op_types_rows
    ]

    workbook = load_workbook(path, data_only=True)
    try:
        ws = workbook.active
        assert [ws.cell(1, col_idx).value for col_idx in range(1, len(headers) + 1)] == headers
        assert _nonempty_rows(ws, len(headers)) == expected_rows
    finally:
        workbook.close()


def test_supplier_conversion_output_matches_current_template_layout() -> None:
    filename = "供应商配置.xlsx"
    definition = get_template_definition(filename)
    headers = [str(item) for item in definition.get("headers") or []]
    path = REPO_ROOT / "templates_excel" / "转换输出" / filename
    rows = _read_workbook_rows(path, headers)

    workbook = load_workbook(path, data_only=True)
    try:
        ws = workbook.active
        assert [ws.cell(1, col_idx).value for col_idx in range(1, len(headers) + 1)] == headers
        assert rows, "供应商配置转换输出至少要保留一行转换结果"
        for row in rows:
            assert row[4] in ("启用", "停用")
    finally:
        workbook.close()


def test_unit_template_exporter_refuses_symlink_output_without_touching_target(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from core.infrastructure.safe_files import UnsafeFixedFileError

    victim = tmp_path / "victim.xlsx"
    victim.write_text("VICTIM-UNCHANGED", encoding="utf-8")
    output_path = tmp_path / "供应商配置.xlsx"
    os.symlink(str(victim), str(output_path))

    with pytest.raises(UnsafeFixedFileError):
        UnitTemplateExporter._write_xlsx(
            path=str(output_path),
            filename="供应商配置.xlsx",
            headers=["供应商编号", "名称"],
            rows=[{"供应商编号": "SUP-1", "名称": "供应商一"}],
        )

    assert os.path.islink(str(output_path))
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNCHANGED"


def test_unit_template_exporter_refuses_hardlink_output_without_touching_target(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    from core.infrastructure.safe_files import UnsafeFixedFileError

    victim = tmp_path / "victim.xlsx"
    victim.write_text("VICTIM-UNCHANGED", encoding="utf-8")
    output_path = tmp_path / "供应商配置.xlsx"
    os.link(str(victim), str(output_path))

    with pytest.raises(UnsafeFixedFileError):
        UnitTemplateExporter._write_xlsx(
            path=str(output_path),
            filename="供应商配置.xlsx",
            headers=["供应商编号", "名称"],
            rows=[{"供应商编号": "SUP-1", "名称": "供应商一"}],
        )

    assert output_path.exists()
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNCHANGED"


def test_unit_template_exporter_sanitizes_formula_like_values(tmp_path: Path) -> None:
    output_path = tmp_path / "供应商配置.xlsx"

    UnitTemplateExporter._write_xlsx(
        path=str(output_path),
        filename="供应商配置.xlsx",
        headers=["供应商编号", "名称"],
        rows=[{"供应商编号": "SUP-1", "名称": "=1+1"}],
    )

    workbook = load_workbook(output_path, data_only=False)
    try:
        ws = workbook.active
        assert ws["B2"].value == "'=1+1"
        assert ws["B2"].data_type != "f"
    finally:
        workbook.close()

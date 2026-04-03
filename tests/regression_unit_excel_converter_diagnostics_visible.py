from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile

import openpyxl


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _build_source_xlsx(path: str) -> None:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        if ws is None:
            raise RuntimeError("Workbook.active 返回空 Sheet")
        ws.title = "单元产品信息统计"
        ws.append(
            [
                "图号",
                "名称",
                "是否关重件",
                "关键特性",
                "工艺路线",
                "材料牌号",
                "材料规格",
                "进单元可装夹直径",
                "3140124 胡凡 罗辉",
                "换型时间(min)",
                "单件加工时间(min)",
                "批次加工时间(min)",
            ]
        )
        ws.append(
            [
                "P001",
                "壳体A",
                "是",
                "",
                "5数车10热处理20总检",
                "",
                "",
                "",
                "15-1精铣",
                20,
                15,
                35,
            ]
        )
        ws.append(
            [
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "20去毛刺",
                10,
                5,
                15,
            ]
        )
        wb.save(path)
    finally:
        try:
            wb.close()
        except Exception:
            pass


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process import UnitExcelConverter
    from scripts import convert_rotary_shell_unit_excel as convert_script

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_converter_diag_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    out_dir = os.path.join(tmpdir, "out")
    _build_source_xlsx(src_xlsx)

    converter = UnitExcelConverter()
    converted = converter.convert(src_xlsx)

    diagnostics = dict(getattr(converted, "diagnostics", {}) or {})
    counters = dict(diagnostics.get("counters") or {})
    samples = dict(diagnostics.get("samples") or {})

    assert int(counters.get("default_filled") or 0) >= 1, diagnostics
    assert int(counters.get("inferred_field") or 0) >= 1, diagnostics
    assert int(counters.get("compatible_row") or 0) >= 1, diagnostics
    assert samples.get("default_filled"), diagnostics
    assert samples.get("inferred_field"), diagnostics
    assert samples.get("compatible_row"), diagnostics

    stdout = io.StringIO()
    old_argv = list(sys.argv)
    try:
        sys.argv = [
            "convert_rotary_shell_unit_excel.py",
            "--input",
            src_xlsx,
            "--output-dir",
            out_dir,
        ]
        with contextlib.redirect_stdout(stdout):
            rc = convert_script.main()
    finally:
        sys.argv = old_argv

    output = stdout.getvalue()
    assert rc == 0, output
    assert "转换完成（带退化成功）。" in output, output
    assert "诊断汇总：" in output, output
    assert "默认补齐次数：" in output, output
    assert "推断字段次数：" in output, output
    assert "兼容行数：" in output, output
    assert "人员设备关联会输出 工号/设备编号/技能等级/主操设备 四列；默认补齐会进入诊断汇总。" in output, output

    print("OK")


if __name__ == "__main__":
    main()

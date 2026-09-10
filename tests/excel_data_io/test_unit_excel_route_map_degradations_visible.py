"""守护单元 Excel 工艺路线解析留痕契约：路线里重复工序号（如"1车2铣2磨"）只按第一次出现转换时、
无法识别的片段（缺工序号的名称段、缺名称的工序号段）被丢弃时，必须逐条计入
diagnostics.counters/samples（route_duplicate_step_seq / route_segment_dropped），不许静默吃数据；
且保留既有转换行为（首个名称胜出、坏片段跳过）。"""

from __future__ import annotations

import os
import tempfile

import openpyxl


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
        # P001：重复工序号 2，"磨"会被首个胜出丢弃——必须出 route_duplicate_step_seq
        ws.append(["P001", "壳体A", "是", "", "1车2铣2磨", "", "", "", "1-1车削", 20, 15, 35])
        # P002：前导"钳"没有工序号、末尾"3"没有名称——必须各出一条 route_segment_dropped
        ws.append(["P002", "壳体B", "否", "", "钳2铣3", "", "", "", "2-1铣削", 10, 5, 15])
        wb.save(path)
    finally:
        try:
            wb.close()
        except Exception:
            pass


def test_route_map_degradations_are_visible_in_diagnostics() -> None:
    from core.services.process.unit_excel_converter import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_route_diag_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    _build_source_xlsx(src_xlsx)

    converted = UnitExcelConverter().convert(src_xlsx)

    diagnostics = dict(getattr(converted, "diagnostics", {}) or {})
    counters = dict(diagnostics.get("counters") or {})
    samples = dict(diagnostics.get("samples") or {})

    assert int(counters.get("route_duplicate_step_seq") or 0) == 1, diagnostics
    assert int(counters.get("route_segment_dropped") or 0) == 2, diagnostics

    dup_samples = list(samples.get("route_duplicate_step_seq") or [])
    assert dup_samples, diagnostics
    dup = dict(dup_samples[0])
    assert dup.get("part_no") == "P001"
    assert dup.get("seq") == 2
    assert dup.get("kept_name") == "铣"
    assert dup.get("dropped_name") == "磨"

    dropped_samples = [dict(s) for s in samples.get("route_segment_dropped") or []]
    dropped_segments = {s.get("segment") for s in dropped_samples}
    assert dropped_segments == {"钳", "3"}, diagnostics
    assert all(s.get("part_no") == "P002" for s in dropped_samples), diagnostics

    # 转换行为保持既有口径：首个名称胜出、坏片段跳过（本合同只要求"丢弃必须可见"）。
    routes_text = str(converted.routes_rows)
    assert "车" in routes_text and "铣" in routes_text
    assert "磨" not in routes_text
    assert "钳" not in routes_text


def test_clean_route_produces_no_route_degradation() -> None:
    from core.services.process.unit_excel_converter import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_route_clean_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        assert ws is not None
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
        ws.append(["P001", "壳体A", "是", "", "1车2铣3磨", "", "", "", "1-1车削", 20, 15, 35])
        wb.save(src_xlsx)
    finally:
        try:
            wb.close()
        except Exception:
            pass

    converted = UnitExcelConverter().convert(src_xlsx)
    counters = dict((getattr(converted, "diagnostics", {}) or {}).get("counters") or {})
    assert int(counters.get("route_duplicate_step_seq") or 0) == 0, counters
    assert int(counters.get("route_segment_dropped") or 0) == 0, counters

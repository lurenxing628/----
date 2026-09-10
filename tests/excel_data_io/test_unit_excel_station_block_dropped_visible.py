"""守护单元 Excel 站位（设备）列块丢弃留痕契约（审计 D09）：
表头识别失败导致整台设备的 4 列工时块被跳过时，不许无声消失——
1) 丢弃列块必须出 station_header_dropped 诊断（样本含列位置与读到的表头原文）；
   覆盖三种形态：块首表头为空（合并单元格锚点不在块首）、表头识别不出设备编号、
   表尾不足 4 列的残块；
2) 数据行落在被丢弃列块里的内容必须逐行出 station_block_data_dropped 诊断
   （样本含行号、列范围与单元格内容），计数反映丢了多少行；
3) 正常表头布局不产生上述诊断，已识别站位的数据照常转换。"""

from __future__ import annotations

import os
import tempfile

import openpyxl

_META_HEADERS = [
    "图号",
    "名称",
    "是否关重件",
    "关键特性",
    "工艺路线",
    "材料牌号",
    "材料规格",
    "进单元可装夹直径",
]
_VALID_BLOCK = ["3140124 胡凡 罗辉", "换型时间(min)", "单件加工时间(min)", "批次加工时间(min)"]


def _write_xlsx(path: str, header_row, data_rows) -> None:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        assert ws is not None
        ws.title = "单元产品信息统计"
        ws.append(header_row)
        for row in data_rows:
            ws.append(row)
        wb.save(path)
    finally:
        try:
            wb.close()
        except Exception:
            pass


def _diagnostics(converted):
    diagnostics = dict(getattr(converted, "diagnostics", {}) or {})
    return dict(diagnostics.get("counters") or {}), dict(diagnostics.get("samples") or {})


def test_blank_anchor_station_block_dropped_with_header_and_data_diagnostics() -> None:
    from core.services.process.unit_excel_converter import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_station_blank_anchor_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    # 第二个设备列块（M-P 列）的块首表头为空、子表头仍在——模拟合并单元格锚点不在块首。
    header = _META_HEADERS + _VALID_BLOCK + [None, "换型时间(min)", "单件加工时间(min)", "批次加工时间(min)"]
    data_rows = [
        ["P001", "壳体A", "是", "", "1车2铣", "", "", "", "1-1车削", 20, 15, 35, "2-1铣削", 10, 5, 15],
        [None, None, None, None, None, None, None, None, "1-2精车", 5, 8, None, "2-2精铣", 6, 7, None],
    ]
    _write_xlsx(src_xlsx, header, data_rows)

    converted = UnitExcelConverter().convert(src_xlsx)
    counters, samples = _diagnostics(converted)

    assert int(counters.get("station_header_dropped") or 0) == 1, counters
    header_sample = dict((samples.get("station_header_dropped") or [{}])[0])
    assert header_sample.get("columns") == "M-P", header_sample
    assert "换型时间(min)" in list(header_sample.get("headers") or []), header_sample

    # 两个数据行都在被丢弃列块里有内容：逐行留痕，计数=2。
    assert int(counters.get("station_block_data_dropped") or 0) == 2, counters
    data_samples = [dict(s) for s in samples.get("station_block_data_dropped") or []]
    assert [int(s.get("row_num") or 0) for s in data_samples] == [2, 3], data_samples
    assert all(s.get("columns") == "M-P" for s in data_samples), data_samples
    assert "2-1铣削" in list(data_samples[0].get("values") or []), data_samples

    # 已识别的站位（I-L 列）照常转换：工序 1 是内部工序、工时进入产物。
    assert [r.get("图号") for r in converted.routes_rows] == ["P001"], converted.routes_rows
    hours_seqs = [int(r.get("工序") or 0) for r in converted.part_operation_hours_rows]
    assert 1 in hours_seqs, converted.part_operation_hours_rows


def test_station_header_without_machine_id_dropped_visible() -> None:
    from core.services.process.unit_excel_converter import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_station_no_machine_id_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    # 多行表头首行只有括号备注，抽不出设备编号——整块应被丢弃并留痕。
    header = _META_HEADERS + _VALID_BLOCK + ["（备用）\n张三", "换型时间(min)", "单件加工时间(min)", "批次加工时间(min)"]
    data_rows = [["P001", "壳体A", "是", "", "1车", "", "", "", "1-1车削", 20, 15, 35, None, None, None, None]]
    _write_xlsx(src_xlsx, header, data_rows)

    converted = UnitExcelConverter().convert(src_xlsx)
    counters, samples = _diagnostics(converted)

    assert int(counters.get("station_header_dropped") or 0) == 1, counters
    sample = dict((samples.get("station_header_dropped") or [{}])[0])
    assert sample.get("columns") == "M-P", sample
    assert "（备用）" in str((sample.get("headers") or [""])[0]), sample
    # 被丢弃块下没有数据：不产生数据丢失诊断。
    assert int(counters.get("station_block_data_dropped") or 0) == 0, counters


def test_trailing_incomplete_station_block_dropped_visible() -> None:
    from core.services.process.unit_excel_converter import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_station_tail_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    # 表尾只剩 1 列的设备表头（不足 4 列成块）——老行为直接无声跳过。
    header = _META_HEADERS + _VALID_BLOCK + ["3150001 李四"]
    data_rows = [["P001", "壳体A", "是", "", "1车", "", "", "", "1-1车削", 20, 15, 35, "1-1车削"]]
    _write_xlsx(src_xlsx, header, data_rows)

    converted = UnitExcelConverter().convert(src_xlsx)
    counters, samples = _diagnostics(converted)

    assert int(counters.get("station_header_dropped") or 0) == 1, counters
    sample = dict((samples.get("station_header_dropped") or [{}])[0])
    assert sample.get("columns") == "M-M", sample
    assert list(sample.get("headers") or []) == ["3150001 李四"], sample
    assert int(counters.get("station_block_data_dropped") or 0) == 1, counters


def test_clean_station_layout_produces_no_drop_diagnostics() -> None:
    from core.services.process.unit_excel_converter import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_station_clean_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    header = _META_HEADERS + _VALID_BLOCK + ["3150001 李四", "换型时间(min)", "单件加工时间(min)", "批次加工时间(min)"]
    data_rows = [["P001", "壳体A", "是", "", "1车2铣", "", "", "", "1-1车削", 20, 15, 35, "2-1铣削", 10, 5, 15]]
    _write_xlsx(src_xlsx, header, data_rows)

    converted = UnitExcelConverter().convert(src_xlsx)
    counters, _samples = _diagnostics(converted)

    assert int(counters.get("station_header_dropped") or 0) == 0, counters
    assert int(counters.get("station_block_data_dropped") or 0) == 0, counters
    assert [r.get("图号") for r in converted.routes_rows] == ["P001"], converted.routes_rows

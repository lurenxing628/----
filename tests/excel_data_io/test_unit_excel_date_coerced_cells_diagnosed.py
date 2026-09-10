"""守护单元 Excel 单元格日期化/数字化留痕契约（审计 D08）：
1) 工序号单元格被 Excel 自动存成日期（"10-1"变 2026-10-01）时，不做猜测恢复——
   不许把年份前缀截成工序号（如 202），必须按无法识别处理（seq=None）并出
   step_cell_date_coerced 诊断（message 引导改文本格式重导，样本含原始值与行号）；
2) 图号单元格被日期化/存成小数（科学计数法）时，转换仍按文本继续（不改数据归属），
   但必须出 part_no_cell_date_coerced / part_no_cell_number_coerced 诊断留痕；
   正常的整数图号不受影响、不产生诊断。"""

from __future__ import annotations

import datetime
import os
import tempfile

import openpyxl

_HEADERS = [
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


def _write_xlsx(path: str, rows) -> None:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        assert ws is not None
        ws.title = "单元产品信息统计"
        ws.append(_HEADERS)
        for row in rows:
            ws.append(row)
        wb.save(path)
    finally:
        try:
            wb.close()
        except Exception:
            pass


def test_step_cell_stored_as_date_is_not_guessed_and_diagnosed() -> None:
    from core.services.process import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_step_date_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    # 工序号"10-1"被 Excel 自动转成日期 datetime(2026,10,1)：老行为会截出 seq=202 且零专门诊断。
    _write_xlsx(src_xlsx, [["P001", "壳体A", "是", "", "10车", "", "", "", datetime.datetime(2026, 10, 1), 20, 15, 35]])

    converted = UnitExcelConverter().convert(src_xlsx)

    diagnostics = dict(getattr(converted, "diagnostics", {}) or {})
    counters = dict(diagnostics.get("counters") or {})
    samples = dict(diagnostics.get("samples") or {})

    assert int(counters.get("step_cell_date_coerced") or 0) == 1, diagnostics
    sample = dict((samples.get("step_cell_date_coerced") or [{}])[0])
    assert sample.get("part_no") == "P001", sample
    assert int(sample.get("row_num") or 0) == 2, sample
    assert "2026-10-01" in str(sample.get("raw_value") or ""), sample

    events = [dict(e) for e in (diagnostics.get("events") or [])]
    date_events = [e for e in events if e.get("code") == "step_cell_date_coerced"]
    assert date_events, events
    assert "日期" in str(date_events[0].get("message") or ""), date_events
    assert "文本" in str(date_events[0].get("message") or ""), date_events

    # 不许猜测恢复：错误工序号 202 不得出现在任何转换产物里。
    assert converted.routes_rows == [{"图号": "P001", "名称": "壳体A", "工艺路线字符串": "10车"}], converted.routes_rows
    assert all(int(r.get("工序") or 0) != 202 for r in converted.part_operation_hours_rows), (
        converted.part_operation_hours_rows
    )


def test_part_no_cell_stored_as_date_keeps_row_but_diagnosed() -> None:
    from core.services.process import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_partno_date_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    _write_xlsx(
        src_xlsx,
        [[datetime.datetime(2026, 3, 10), "壳体B", "是", "", "1车", "", "", "", "1-1车削", 20, 15, 35]],
    )

    converted = UnitExcelConverter().convert(src_xlsx)

    diagnostics = dict(getattr(converted, "diagnostics", {}) or {})
    counters = dict(diagnostics.get("counters") or {})
    samples = dict(diagnostics.get("samples") or {})

    assert int(counters.get("part_no_cell_date_coerced") or 0) == 1, diagnostics
    sample = dict((samples.get("part_no_cell_date_coerced") or [{}])[0])
    assert int(sample.get("row_num") or 0) == 2, sample
    assert "2026-03-10" in str(sample.get("raw_value") or ""), sample

    # 行为保持：仍按文本化后的值转换（畸变图号在产物里可见），不静默丢行、不错挂到别的图号。
    assert [r.get("图号") for r in converted.routes_rows] == ["2026-03-10 00:00:00"], converted.routes_rows


def test_part_no_cell_stored_as_float_diagnosed_and_int_part_no_untouched() -> None:
    from core.services.process import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_unit_partno_float_")
    src_xlsx = os.path.join(tmpdir, "source.xlsx")
    _write_xlsx(
        src_xlsx,
        [
            # 长数字图号被 Excel 存成浮点（科学计数法形态）。
            [1.23456789012345e16, "壳体C", "是", "", "1车", "", "", "", "1-1车削", 20, 15, 35],
            # 普通整数图号是合法形态，不得产生诊断。
            [3140125, "壳体D", "是", "", "1车", "", "", "", "1-1车削", 20, 15, 35],
        ],
    )

    converted = UnitExcelConverter().convert(src_xlsx)

    diagnostics = dict(getattr(converted, "diagnostics", {}) or {})
    counters = dict(diagnostics.get("counters") or {})
    samples = dict(diagnostics.get("samples") or {})

    assert int(counters.get("part_no_cell_number_coerced") or 0) == 1, diagnostics
    assert int(counters.get("part_no_cell_date_coerced") or 0) == 0, diagnostics
    sample = dict((samples.get("part_no_cell_number_coerced") or [{}])[0])
    assert int(sample.get("row_num") or 0) == 2, sample

    part_nos = [r.get("图号") for r in converted.routes_rows]
    assert "3140125" in part_nos, part_nos

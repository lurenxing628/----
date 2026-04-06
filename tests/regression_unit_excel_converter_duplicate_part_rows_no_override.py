import os
import sys
import tempfile
from typing import Tuple

import openpyxl


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _build_source_xlsx(path: str, repeat_part_on_third_row: bool) -> None:
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
                "3140124 胡凡",
                "换型时间(min)",
                "单件加工时间(min)",
                "批次加工时间(min)",
            ]
        )
        ws.append(
            [
                "P100",
                "壳体X",
                None,
                None,
                "5数车",
                None,
                None,
                None,
                "5-1粗车",
                20,
                40,
                None,
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
                "5-2半精车",
                30,
                50,
                None,
            ]
        )
        ws.append(
            [
                "P100" if repeat_part_on_third_row else None,
                "壳体X" if repeat_part_on_third_row else None,
                None,
                None,
                "5数车" if repeat_part_on_third_row else None,
                None,
                None,
                None,
                "5-3精车",
                40,
                30,
                None,
            ]
        )
        wb.save(path)
    finally:
        try:
            wb.close()
        except Exception:
            pass


def _extract_hours(converted) -> Tuple[float, float]:
    for r in converted.part_operation_hours_rows:
        if str(r.get("图号") or "").strip() == "P100" and int(r.get("工序") or 0) == 5:
            return float(r.get("换型时间(h)") or 0.0), float(r.get("单件工时(h)") or 0.0)
    raise RuntimeError("未找到 P100-5 的工时记录")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process import UnitExcelConverter

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_unit_duplicate_part_")
    single_path = os.path.join(tmpdir, "single.xlsx")
    dup_path = os.path.join(tmpdir, "duplicate.xlsx")
    _build_source_xlsx(single_path, repeat_part_on_third_row=False)
    _build_source_xlsx(dup_path, repeat_part_on_third_row=True)

    conv = UnitExcelConverter()
    single_converted = conv.convert(single_path)
    dup_converted = conv.convert(dup_path)

    single_setup_h, single_unit_h = _extract_hours(single_converted)
    dup_setup_h, dup_unit_h = _extract_hours(dup_converted)

    # 3 个工步累计：setup=(20+30+40)/60=1.5，unit=(40+50+30)/60=2.0
    assert abs(single_setup_h - 1.5) < 1e-6 and abs(single_unit_h - 2.0) < 1e-6, (
        f"SINGLE 累计异常：setup={single_setup_h}, unit={single_unit_h}"
    )
    assert abs(dup_setup_h - 1.5) < 1e-6 and abs(dup_unit_h - 2.0) < 1e-6, (
        f"DUP 累计异常：setup={dup_setup_h}, unit={dup_unit_h}"
    )

    print("OK")


if __name__ == "__main__":
    main()

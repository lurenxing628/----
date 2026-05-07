from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from core.services.common.excel_templates import get_default_templates

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_batch_template_fallback_sample_ready_date_is_blank() -> None:
    template = next(item for item in get_default_templates() if item["filename"] == "批次信息.xlsx")

    assert template["sample_rows"][0][5] == "齐套"
    assert template["sample_rows"][0][6] is None


def test_batch_template_file_sample_ready_date_is_blank() -> None:
    workbook = load_workbook(REPO_ROOT / "templates_excel" / "批次信息.xlsx", data_only=True)
    try:
        sheet = workbook.active
        assert sheet["F2"].value == "齐套"
        assert sheet["G2"].value in (None, "")
    finally:
        workbook.close()

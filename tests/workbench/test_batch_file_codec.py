"""Batch XLSX codec admission through shared source_rows physical checks."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from core.errors import ValidationError
from core.services.workbench.batch.file_codec import read_batch_file, write_batch_file


def test_batch_xlsx_codec_rejects_duplicate_physical_rows_and_duplicate_cell_coordinates():
    valid_xlsx = write_batch_file(
        [
            ["B1", "P1", 10, "2026-10-15", "普通", "齐套", "", "first", "待排", "齐套"],
            ["B2", "P1", 20, "2026-10-16", "急件", "齐套", "", "second", "待排", "齐套"],
        ]
    )
    rows, warnings = read_batch_file(valid_xlsx)
    assert [row["values"]["批次号"] for row in rows] == ["B1", "B2"]
    assert [item["code"] for item in warnings] == [
        "first_sheet_only",
        "reference_column_ignored",
        "reference_column_ignored",
    ]

    def _tamper_sheet_xml(transform):
        buf = BytesIO()
        with ZipFile(BytesIO(valid_xlsx)) as src, ZipFile(buf, "w") as dst:
            for item in src.infolist():
                data = src.read(item.filename)
                if item.filename == "xl/worksheets/sheet1.xml":
                    data = transform(data.decode("utf-8")).encode("utf-8")
                dst.writestr(item, data)
        return buf.getvalue()

    dup_row_xlsx = _tamper_sheet_xml(
        lambda xml: xml.replace('<row r="3"', '<row r="2"').replace('r="A3"', 'r="A2"').replace('r="B3"', 'r="B2"')
    )
    with pytest.raises(ValidationError, match="行号有重复、倒序或不合法"):
        read_batch_file(dup_row_xlsx)

    dup_cell_xlsx = _tamper_sheet_xml(lambda xml: xml.replace('r="B2"', 'r="A2"', 1))
    with pytest.raises(ValidationError, match="有重复、倒序或错位的单元格"):
        read_batch_file(dup_cell_xlsx)

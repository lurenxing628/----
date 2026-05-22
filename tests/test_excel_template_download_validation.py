from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from openpyxl import Workbook

from core.infrastructure.errors import AppError
from core.services.common.excel_templates import get_template_definition
from web.routes.excel_utils import send_excel_template_file


def _write_workbook(path: Path, headers: list[str]) -> None:
    workbook = Workbook()
    try:
        ws = workbook.active
        ws.append(headers)
        workbook.save(path)
    finally:
        workbook.close()


def test_template_download_rejects_mismatched_headers(tmp_path: Path) -> None:
    template_path = tmp_path / "人员基本信息.xlsx"
    _write_workbook(template_path, ["自定义列", "姓名", "备注"])

    app = Flask(__name__)
    with app.test_request_context("/download"):
        with pytest.raises(AppError) as exc_info:
            send_excel_template_file(str(template_path), download_name="人员基本信息.xlsx")

    assert "表头不匹配" in str(exc_info.value)


def test_template_download_rejects_extra_header_columns(tmp_path: Path) -> None:
    template_path = tmp_path / "人员基本信息.xlsx"
    definition = get_template_definition("人员基本信息.xlsx")
    _write_workbook(template_path, [str(item) for item in definition.get("headers") or []] + ["现场列"])

    app = Flask(__name__)
    with app.test_request_context("/download"):
        with pytest.raises(AppError) as exc_info:
            send_excel_template_file(str(template_path), download_name="人员基本信息.xlsx")

    assert "表头不匹配" in str(exc_info.value)

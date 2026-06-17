"""回归测试：send_excel_template_file 下发 Excel 模板前校验表头——当模板文件首行表头与 get_template_definition 定义不一致（列名不符或多出额外列）时，抛出含“表头不匹配”的 AppError 而非把错误模板发给用户。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pytest
from flask import Flask
from openpyxl import Workbook

from core.infrastructure.errors import AppError
from core.services.common.excel_templates import get_template_definition
from web.routes.excel_utils import send_excel_template_file, template_file_exists_for_download


def _write_workbook(path: Path, headers: List[str]) -> None:
    workbook = Workbook()
    try:
        ws = workbook.active
        ws.append(headers)
        workbook.save(path)
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


def test_template_download_rejects_mismatched_headers(tmp_path: Path) -> None:
    template_path = tmp_path / "人员基本信息.xlsx"
    _write_workbook(template_path, ["自定义列", "姓名", "备注"])

    app = Flask(__name__)
    with app.test_request_context("/download"):
        with pytest.raises(AppError) as exc_info:
            send_excel_template_file(str(template_path), download_name="人员基本信息.xlsx")

    assert "表头不匹配" in str(exc_info.value)


def test_template_download_rejects_symlink_template_without_sending_target(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    template_path = tmp_path / "人员基本信息.xlsx"
    victim_path = tmp_path / "victim.xlsx"
    definition = get_template_definition("人员基本信息.xlsx")
    _write_workbook(victim_path, [str(item) for item in definition.get("headers") or []])
    os.symlink(str(victim_path), str(template_path))

    app = Flask(__name__)
    with app.test_request_context("/download"):
        with pytest.raises(AppError) as exc_info:
            send_excel_template_file(str(template_path), download_name="人员基本信息.xlsx")

    assert "模板文件读取失败" in str(exc_info.value)


def test_template_download_rejects_hardlink_template_without_sending_target(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    template_path = tmp_path / "人员基本信息.xlsx"
    victim_path = tmp_path / "victim.xlsx"
    definition = get_template_definition("人员基本信息.xlsx")
    _write_workbook(victim_path, [str(item) for item in definition.get("headers") or []])
    os.link(str(victim_path), str(template_path))

    app = Flask(__name__)
    with app.test_request_context("/download"):
        with pytest.raises(AppError) as exc_info:
            send_excel_template_file(str(template_path), download_name="人员基本信息.xlsx")

    assert "模板文件读取失败" in str(exc_info.value)


def test_dangling_template_symlink_counts_as_existing_for_loud_download_failure(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    template_path = tmp_path / "人员基本信息.xlsx"
    os.symlink(str(tmp_path / "missing.xlsx"), str(template_path))

    assert template_file_exists_for_download(str(template_path)) is True


def test_template_download_rejects_extra_header_columns(tmp_path: Path) -> None:
    template_path = tmp_path / "人员基本信息.xlsx"
    definition = get_template_definition("人员基本信息.xlsx")
    _write_workbook(template_path, [str(item) for item in definition.get("headers") or []] + ["现场列"])

    app = Flask(__name__)
    with app.test_request_context("/download"):
        with pytest.raises(AppError) as exc_info:
            send_excel_template_file(str(template_path), download_name="人员基本信息.xlsx")

    assert "表头不匹配" in str(exc_info.value)

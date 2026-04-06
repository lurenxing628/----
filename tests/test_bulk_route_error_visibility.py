from __future__ import annotations

import importlib
import os
from pathlib import Path

from core.infrastructure.database import ensure_schema
from core.infrastructure.errors import AppError, ErrorCode
from core.services.equipment.machine_service import MachineService
from core.services.personnel.operator_service import OperatorService
from core.services.process.part_service import PartService
from core.services.scheduler.batch_service import BatchService
from web.routes import system_backup as system_backup_mod

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _capture_exception_logs(app, monkeypatch):
    logged = []

    def _fake_exception(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "exception", _fake_exception)
    return logged


def test_scheduler_bulk_delete_surfaces_business_reason_and_logs_unexpected(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    logged = _capture_exception_logs(app, monkeypatch)

    def _fake_delete(self, batch_id):
        if batch_id == "B_OK":
            return None
        if batch_id == "B_RULE":
            raise AppError(ErrorCode.SCHEDULE_CONFLICT, "已被排程引用")
        raise RuntimeError("delete exploded")

    monkeypatch.setattr(BatchService, "delete", _fake_delete)

    resp = client.post(
        "/scheduler/batches/bulk/delete",
        data={"batch_ids": ["B_OK", "B_RULE", "B_BUG"]},
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "批量删除完成：成功 1，失败 2。" in body
    assert "B_RULE: 已被排程引用" in body
    assert "B_BUG: 内部错误，请查看日志" in body
    assert any("批量删除批次失败（batch_id=B_BUG）" in item for item in logged)


def test_equipment_bulk_routes_show_reasons_and_log_unexpected(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    logged = _capture_exception_logs(app, monkeypatch)

    def _fake_set_status(self, machine_id, status):
        if machine_id == "MC_OK":
            return None
        if machine_id == "MC_RULE":
            raise AppError(ErrorCode.MACHINE_NOT_AVAILABLE, "当前状态不允许切换")
        raise RuntimeError("status exploded")

    def _fake_delete(self, machine_id):
        if machine_id == "MC_OK":
            return None
        if machine_id == "MC_RULE":
            raise AppError(ErrorCode.MACHINE_IN_USE, "已被批次工序引用")
        raise RuntimeError("delete exploded")

    monkeypatch.setattr(MachineService, "set_status", _fake_set_status)
    monkeypatch.setattr(MachineService, "delete", _fake_delete)

    resp_status = client.post(
        "/equipment/bulk/status",
        data={"status": "inactive", "machine_ids": ["MC_OK", "MC_RULE", "MC_BUG"]},
        follow_redirects=True,
    )
    status_body = resp_status.get_data(as_text=True)
    assert resp_status.status_code == 200
    assert "批量状态更新完成：成功 1，失败 2。" in status_body
    assert "MC_RULE: 当前状态不允许切换" in status_body
    assert "MC_BUG: 内部错误，请查看日志" in status_body
    assert any("批量设置设备状态失败（machine_id=MC_BUG, status=inactive）" in item for item in logged)

    resp_delete = client.post(
        "/equipment/bulk/delete",
        data={"machine_ids": ["MC_OK", "MC_RULE", "MC_BUG"]},
        follow_redirects=True,
    )
    delete_body = resp_delete.get_data(as_text=True)
    assert resp_delete.status_code == 200
    assert "批量删除完成：成功 1，失败 2。" in delete_body
    assert "MC_RULE: 已被批次工序引用" in delete_body
    assert "MC_BUG: 内部错误，请查看日志" in delete_body
    assert any("批量删除设备失败（machine_id=MC_BUG）" in item for item in logged)


def test_personnel_bulk_routes_show_reasons_and_log_unexpected(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    logged = _capture_exception_logs(app, monkeypatch)

    def _fake_set_status(self, operator_id, status):
        if operator_id == "OP_OK":
            return None
        if operator_id == "OP_RULE":
            raise AppError(ErrorCode.PERMISSION_DENIED, "当前状态不允许切换")
        raise RuntimeError("status exploded")

    def _fake_delete(self, operator_id):
        if operator_id == "OP_OK":
            return None
        if operator_id == "OP_RULE":
            raise AppError(ErrorCode.OPERATOR_IN_USE, "已被排程引用")
        raise RuntimeError("delete exploded")

    monkeypatch.setattr(OperatorService, "set_status", _fake_set_status)
    monkeypatch.setattr(OperatorService, "delete", _fake_delete)

    resp_status = client.post(
        "/personnel/bulk/status",
        data={"status": "inactive", "operator_ids": ["OP_OK", "OP_RULE", "OP_BUG"]},
        follow_redirects=True,
    )
    status_body = resp_status.get_data(as_text=True)
    assert resp_status.status_code == 200
    assert "批量状态更新完成：成功 1，失败 2。" in status_body
    assert "OP_RULE: 当前状态不允许切换" in status_body
    assert "OP_BUG: 内部错误，请查看日志" in status_body
    assert any("批量设置人员状态失败（operator_id=OP_BUG, status=inactive）" in item for item in logged)

    resp_delete = client.post(
        "/personnel/bulk/delete",
        data={"operator_ids": ["OP_OK", "OP_RULE", "OP_BUG"]},
        follow_redirects=True,
    )
    delete_body = resp_delete.get_data(as_text=True)
    assert resp_delete.status_code == 200
    assert "批量删除完成：成功 1，失败 2。" in delete_body
    assert "OP_RULE: 已被排程引用" in delete_body
    assert "OP_BUG: 内部错误，请查看日志" in delete_body
    assert any("批量删除人员失败（operator_id=OP_BUG）" in item for item in logged)


def test_process_bulk_delete_shows_reason_and_logs_unexpected(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    logged = _capture_exception_logs(app, monkeypatch)

    def _fake_delete(self, part_no):
        if part_no == "P_OK":
            return None
        if part_no == "P_RULE":
            raise AppError(ErrorCode.PART_NOT_FOUND, "已被批次引用")
        raise RuntimeError("delete exploded")

    monkeypatch.setattr(PartService, "delete", _fake_delete)

    resp = client.post(
        "/process/parts/bulk/delete",
        data={"part_nos": ["P_OK", "P_RULE", "P_BUG"]},
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "批量删除完成：成功 1，失败 2。" in body
    assert "P_RULE: 已被批次引用" in body
    assert "P_BUG: 内部错误，请查看日志" in body
    assert any("批量删除零件失败（part_no=P_BUG）" in item for item in logged)


def test_system_backup_batch_delete_shows_specific_failure_reasons(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    logged = _capture_exception_logs(app, monkeypatch)
    backup_dir = Path(app.config["BACKUP_DIR"])
    keep_file = backup_dir / "aps_backup_keep.db"
    fail_file = backup_dir / "aps_backup_fail.db"
    keep_file.write_text("keep", encoding="utf-8")
    fail_file.write_text("fail", encoding="utf-8")

    real_remove = os.remove

    def _fake_remove(path):
        if str(path).endswith("aps_backup_fail.db"):
            raise PermissionError("locked")
        real_remove(path)

    monkeypatch.setattr(system_backup_mod.os, "remove", _fake_remove)

    resp = client.post(
        "/system/backup/delete-batch",
        data={
            "filenames": [
                "aps_backup_keep.db",
                "aps_backup_missing.db",
                "../evil.db",
                "aps_backup_fail.db",
            ]
        },
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "批量删除完成：成功 1，失败 3。" in body
    assert "aps_backup_missing.db: 文件不存在" in body
    assert "../evil.db: 备份文件名不合法" in body
    assert "aps_backup_fail.db: 删除失败，请查看日志" in body
    assert not keep_file.exists()
    assert fail_file.exists()
    assert any("批量删除备份失败（filename=aps_backup_fail.db）" in item for item in logged)

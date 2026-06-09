"""回归测试：路由层统一异常语义——供应商删除被引用时 BusinessError(PERMISSION_DENIED) 返回 403 且页面不泄漏 ErrorCode 值/“错误码”字样；物料创建重复、设备停机批量创建越权时仍走页面 flash + 302 重定向白名单，flash 里带原始业务提示。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from core.infrastructure.errors import BusinessError, ErrorCode
from core.services.equipment.machine_downtime_service import MachineDowntimeService
from core.services.material.material_service import MaterialService
from core.services.process.supplier_service import SupplierService
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

    from core.infrastructure.database import ensure_schema

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_process_supplier_delete_uses_global_http_semantics(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    def _raise_permission(self, supplier_id):
        raise BusinessError(ErrorCode.PERMISSION_DENIED, f"供应商“{supplier_id}”已被引用，不能删除。")

    monkeypatch.setattr(SupplierService, "delete", _raise_permission)

    response = client.post("/process/suppliers/SUP-LOCK/delete")

    body = response.get_data(as_text=True)
    assert response.status_code == 403
    assert "供应商“SUP-LOCK”已被引用，不能删除。" in body
    assert ErrorCode.PERMISSION_DENIED.value not in body
    assert "错误码" not in body


def test_material_create_keeps_page_flash_redirect_whitelist(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    def _raise_duplicate(self, **_kwargs):
        raise BusinessError(ErrorCode.DUPLICATE_ENTRY, "物料“MAT-001”已存在")

    monkeypatch.setattr(MaterialService, "create", _raise_duplicate)

    response = client.post(
        "/material/materials/create",
        data={"material_id": "MAT-001", "name": "重复物料", "status": "active"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/material/materials")
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any(category == "error" and "物料“MAT-001”已存在" in str(message) for category, message in flashes), flashes


def test_equipment_downtime_batch_create_keeps_page_flash_redirect_whitelist(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    def _raise_permission(self, **_kwargs):
        raise BusinessError(ErrorCode.PERMISSION_DENIED, "当前设备范围不允许创建停机计划")

    monkeypatch.setattr(MachineDowntimeService, "create_by_scope", _raise_permission)

    response = client.post(
        "/equipment/downtimes/batch/create",
        data={
            "scope_type": "machine",
            "scope_value": "MC001",
            "start_time": "2026-03-02 08:00",
            "end_time": "2026-03-02 12:00",
            "reason_code": "maintain",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/equipment/downtimes/batch")
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any(category == "error" and "当前设备范围不允许创建停机计划" in str(message) for category, message in flashes), flashes

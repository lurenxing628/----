"""回归测试：SystemMaintenanceService.run_if_due 的进程级节流短路——首轮 run 不节流并各触发一次配置读取与自动备份/清理备份/清理日志 runner；紧接的第二轮命中节流（throttled=True），不再读配置、不再调用任何 runner（各计数维持为 1）。"""

from __future__ import annotations

import os
from types import SimpleNamespace


def test_system_maintenance_throttle_short_circuit(tmp_path) -> None:
    from core.infrastructure.database import get_connection
    from core.services.system import SystemMaintenanceService
    from core.services.system import system_maintenance_service as svc_mod

    tmpdir = str(tmp_path)
    db_path = os.path.join(tmpdir, "aps_maintenance.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    conn = get_connection(db_path)
    try:
        SystemMaintenanceService.reset_throttle_for_tests()

        calls = {"snapshot": 0, "backup": 0, "backup_cleanup": 0, "log_cleanup": 0}

        class _FakeCfgService:
            def __init__(self, conn, logger=None):
                self.conn = conn
                self.logger = logger

            def get_snapshot(self, backup_keep_days_default: int):
                calls["snapshot"] += 1
                return SimpleNamespace(
                    auto_backup_enabled="yes",
                    auto_backup_interval_minutes=1,
                    auto_backup_keep_days=max(1, int(backup_keep_days_default)),
                    auto_backup_cleanup_enabled="yes",
                    auto_backup_cleanup_interval_minutes=1,
                    auto_log_cleanup_enabled="yes",
                    auto_log_cleanup_interval_minutes=1,
                    auto_log_cleanup_keep_days=1,
                )

        def _fake_backup(*args, **kwargs):
            calls["backup"] += 1
            return False, {"due": False, "last_run_time": None}

        def _fake_backup_cleanup(*args, **kwargs):
            calls["backup_cleanup"] += 1
            return False, {"due": False, "last_run_time": None}

        def _fake_log_cleanup(*args, **kwargs):
            calls["log_cleanup"] += 1
            return False, {"due": False, "last_run_time": None}

        orig_cfg = svc_mod.SystemConfigService
        orig_backup = svc_mod.maybe_run_auto_backup
        orig_backup_cleanup = svc_mod.maybe_run_auto_backup_cleanup
        orig_log_cleanup = svc_mod.maybe_run_auto_log_cleanup
        try:
            svc_mod.SystemConfigService = _FakeCfgService
            svc_mod.maybe_run_auto_backup = _fake_backup
            svc_mod.maybe_run_auto_backup_cleanup = _fake_backup_cleanup
            svc_mod.maybe_run_auto_log_cleanup = _fake_log_cleanup

            r1 = SystemMaintenanceService.run_if_due(
                conn,
                db_path=db_path,
                backup_dir=backup_dir,
                backup_keep_days_default=7,
                logger=None,
                op_logger=None,
            )
            assert r1.details.get("throttled") is False, f"首轮不应节流：{r1.details!r}"

            r2 = SystemMaintenanceService.run_if_due(
                conn,
                db_path=db_path,
                backup_dir=backup_dir,
                backup_keep_days_default=7,
                logger=None,
                op_logger=None,
            )
            assert r2.details.get("throttled") is True, f"第二轮应命中节流：{r2.details!r}"

            assert calls["snapshot"] == 1, f"节流命中后不应再次读取配置：{calls!r}"
            assert calls["backup"] == 1, f"节流命中后不应再次触发自动备份 runner：{calls!r}"
            assert calls["backup_cleanup"] == 1, f"节流命中后不应再次触发自动清理备份 runner：{calls!r}"
            assert calls["log_cleanup"] == 1, f"节流命中后不应再次触发自动清理日志 runner：{calls!r}"
        finally:
            svc_mod.SystemConfigService = orig_cfg
            svc_mod.maybe_run_auto_backup = orig_backup
            svc_mod.maybe_run_auto_backup_cleanup = orig_backup_cleanup
            svc_mod.maybe_run_auto_log_cleanup = orig_log_cleanup
            SystemMaintenanceService.reset_throttle_for_tests()
    finally:
        try:
            conn.close()
        except Exception:
            pass


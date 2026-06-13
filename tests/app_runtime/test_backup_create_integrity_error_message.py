"""回归测试（F2 修复）：POST /system/backup/create 当 BackupManager.backup() 因完整性
检查失败抛裸 RuntimeError（R32/O27 loud：坏库绝不升正式）时，web 入口必须转成具体中文提示
并重定向回备份页，绝不冒泡成 errorhandler(500) 的笼统「服务器内部错误，请查看日志」。

MaintenanceWindowError 是 RuntimeError 子类、走既有维护锁分支不受影响（已在 except 顺序上保证）。"""

from __future__ import annotations

from unittest import mock


class _BackupIntegrityBoomManager:
    """backup() 抛裸 RuntimeError，模拟完整性检查执行失败/未通过。"""

    def backup(self, suffix=None):
        raise RuntimeError("备份后的数据库完整性检查执行失败（视为不可信备份，不落地）：模拟")

    def list_backups(self):
        return []


def test_backup_create_integrity_runtime_error_shows_chinese_not_500(app_client, db_env) -> None:
    client = app_client
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_BackupIntegrityBoomManager(),
    ):
        resp = client.post("/system/backup/create", data={}, follow_redirects=False)
        assert resp.status_code in (302, 303), (
            f"完整性检查失败应重定向回备份页、不应 500，实际 {resp.status_code}"
        )

        html = client.post(
            "/system/backup/create", data={}, follow_redirects=True
        ).data.decode("utf-8", errors="ignore")
        assert "备份完整性检查失败" in html, "应展示具体中文提示而非笼统 500"
        assert "服务器内部错误" not in html, "不应落入 errorhandler(500) 笼统页"

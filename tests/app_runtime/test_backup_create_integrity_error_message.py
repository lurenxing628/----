"""回归测试（F2 修复）：POST /system/backup/create 当 BackupManager.backup() 因完整性
检查失败抛裸 RuntimeError（R32/O27 loud：坏库绝不升正式）时，web 入口必须转成具体中文提示
并重定向回备份页，绝不冒泡成 errorhandler(500) 的笼统「服务器内部错误，请查看日志」。

MaintenanceWindowError 是 RuntimeError 子类、走既有维护锁分支不受影响（已在 except 顺序上保证）。"""

from __future__ import annotations

import sqlite3
from unittest import mock

import pytest


class _BackupIntegrityBoomManager:
    """backup() 抛裸 RuntimeError，模拟完整性检查执行失败/未通过。"""

    def backup(self, suffix=None):
        raise RuntimeError("备份后的数据库完整性检查执行失败（视为不可信备份，不落地）：模拟")

    def list_backups(self):
        return []


class _BackupWriteBoomManager:
    """backup() 抛 OSError，模拟原子替换/写入阶段失败（非 RuntimeError 子类）。"""

    def backup(self, suffix=None):
        raise OSError("磁盘空间不足：模拟")

    def list_backups(self):
        return []


class _BackupOperationalErrorManager:
    """backup() 抛 sqlite3.OperationalError，模拟磁盘 I/O / 库被占用等运行时失败。"""

    def backup(self, suffix=None):
        raise sqlite3.OperationalError("disk I/O error：模拟")

    def list_backups(self):
        return []


class _BackupProgrammingErrorManager:
    """backup() 抛 sqlite3.ProgrammingError，模拟编程错误（bad binding 等）——
    必须 loud 透传、不被伪装成「磁盘空间不足」写入失败。"""

    def backup(self, suffix=None):
        raise sqlite3.ProgrammingError("bad binding：模拟")

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


def test_backup_create_write_error_shows_chinese_not_500(app_client, db_env) -> None:
    # finding-11：sqlite connect/backup 抛 sqlite3.Error、原子替换抛 OSError 都不是
    # RuntimeError 子类，过去会落到 errorhandler(500)；现在专门拦截并转具体中文。
    client = app_client
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_BackupWriteBoomManager(),
    ):
        resp = client.post("/system/backup/create", data={}, follow_redirects=False)
        assert resp.status_code in (302, 303), (
            f"写入异常应重定向回备份页、不应 500，实际 {resp.status_code}"
        )

        html = client.post(
            "/system/backup/create", data={}, follow_redirects=True
        ).data.decode("utf-8", errors="ignore")
        assert "备份写入失败" in html, "写入异常应展示具体中文提示而非笼统 500"
        assert "服务器内部错误" not in html, "不应落入 errorhandler(500) 笼统页"


def test_backup_create_operational_error_shows_chinese_not_500(app_client, db_env) -> None:
    # sqlite3.OperationalError（磁盘 I/O / 库被占用）是预期运行时失败，应转中文降级不落 500。
    client = app_client
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_BackupOperationalErrorManager(),
    ):
        html = client.post(
            "/system/backup/create", data={}, follow_redirects=True
        ).data.decode("utf-8", errors="ignore")
        assert "备份写入失败" in html, "OperationalError 应展示具体中文提示"
        assert "服务器内部错误" not in html


def test_backup_create_programming_error_is_not_masked(app_client, db_env) -> None:
    # finding-11/Codex：sqlite3.ProgrammingError 是编程错误，必须 loud 透传、不被
    # (sqlite3.OperationalError, OSError) 分支伪装成「磁盘空间不足」写入失败。
    client = app_client
    # 显式钉死 PROPAGATE_EXCEPTIONS：不依赖测试环境隐含的 debug 模式——否则若 fixture 改成
    # production（debug=False），未捕获异常会被 errorhandler(500) 吞掉、pytest.raises 退化失效。
    client.application.config["PROPAGATE_EXCEPTIONS"] = True
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_BackupProgrammingErrorManager(),
    ):
        # 未被备份路由捕获 → 冒泡（透传异常），证明没有被伪装成写入失败提示
        with pytest.raises(sqlite3.ProgrammingError):
            client.post("/system/backup/create", data={}, follow_redirects=True)

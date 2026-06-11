"""守卫测试（QUALITY_GATE_GUARD_TESTS 登记）：诊断包安全红线——zip 名单永不含
aps_secret_key.txt（logs 目录播种假 secret 后断言）、白名单三类之外零进包
（x.log.bak 等非数字分卷后缀拒收）、应含项齐全（log+数字分卷+launch_error+
diagnostic_info+操作日志文本）、操作日志读取失败时包内放说明文件不中断导出、
下载成功与构包失败两条路径均无残留临时文件。"""

from __future__ import annotations

import glob
import io
import os
import tempfile
import zipfile


def _seed(log_dir: str, name: str, text: str = "x\n"):
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, name), "w", encoding="utf-8") as f:
        f.write(text)


def _download_zip_names(client):
    resp = client.get("/system/runtime-logs/diagnostic-package")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    data = resp.get_data()
    resp.close()  # call_on_close 清理在响应流关闭时触发（test client 非 buffered）
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.namelist(), data


def _diag_tmp_files():
    return glob.glob(os.path.join(tempfile.gettempdir(), "aps_diagnostic_*.zip"))


def test_secret_never_in_zip_and_whitelist_only(app_client):
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log", "2026-06-11 10:00:00 [INFO] x\n")
    _seed(log_dir, "aps_error.log")
    _seed(log_dir, "aps.log.1")
    _seed(log_dir, "aps_launch_error.txt", "启动失败证据\n")
    # 红线：播种假 secret 与白名单外文件，断言永不进包
    _seed(log_dir, "aps_secret_key.txt", "FAKE-SECRET")
    _seed(log_dir, "x.log.bak")
    _seed(log_dir, "notes.txt")

    names, _ = _download_zip_names(app_client)

    assert "aps_secret_key.txt" not in names, "安全红线：密钥文件进了诊断包"
    assert "x.log.bak" not in names, "非数字分卷后缀不应进包"
    assert "notes.txt" not in names, "白名单外 .txt 不应进包"
    for expected in ("aps.log", "aps_error.log", "aps.log.1", "aps_launch_error.txt",
                     "diagnostic_info.txt", "operation_logs.txt"):
        assert expected in names, f"诊断包缺少 {expected}"


def test_diagnostic_info_facts(app_client):
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log")
    names, data = _download_zip_names(app_client)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        info = zf.read("diagnostic_info.txt").decode("utf-8")
    from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
    from web.routes.system_health import _CONTRACT_VERSION

    assert f"Schema 版本：{CURRENT_SCHEMA_VERSION}" in info
    assert f"健康检查契约版本：{_CONTRACT_VERSION}" in info
    assert "导出时间：" in info


def test_symlink_with_whitelist_name_rejected(app_client):
    # 白名单文件名挡路径注入，islink 挡「白名单名字指向任意文件」——
    # 播种一个名为 evil.log 的 symlink 指向假 secret，断言不进包
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log")
    _seed(log_dir, "aps_secret_key.txt", "FAKE-SECRET")
    os.symlink(
        os.path.join(log_dir, "aps_secret_key.txt"),
        os.path.join(log_dir, "evil.log"),
    )
    names, _ = _download_zip_names(app_client)
    assert "evil.log" not in names, "symlink 不应进诊断包"
    assert "aps.log" in names


def test_operation_logs_failure_yields_explanation_file(app_client, monkeypatch):
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log")

    import web.routes.system_runtime_logs as mod

    def boom():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(mod, "_get_operation_log_service", boom)
    names, data = _download_zip_names(app_client)
    assert "operation_logs_读取失败.txt" in names
    assert "operation_logs.txt" not in names
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        note = zf.read("operation_logs_读取失败.txt").decode("utf-8")
    assert "db unavailable" in note


def test_no_temp_file_residue_on_success(app_client):
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log")
    before = set(_diag_tmp_files())
    _download_zip_names(app_client)
    leaked = set(_diag_tmp_files()) - before
    assert not leaked, f"下载成功路径残留临时文件：{leaked}"


def test_no_temp_file_residue_on_build_failure(app_client, monkeypatch):
    import web.routes.system_runtime_logs as mod

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "build_diagnostic_zip", boom)
    before = set(_diag_tmp_files())
    resp = app_client.get("/system/runtime-logs/diagnostic-package")
    assert resp.status_code == 302  # flash 后回页面
    leaked = set(_diag_tmp_files()) - before
    assert not leaked, f"构包失败路径残留临时文件：{leaked}"
    follow = app_client.get(resp.headers["Location"])
    assert "诊断包导出失败" in follow.get_data(as_text=True)

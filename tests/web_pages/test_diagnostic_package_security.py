"""守卫测试（QUALITY_GATE_GUARD_TESTS 登记）：诊断包安全红线——zip 名单永不含
aps_secret_key.txt（logs 目录播种假 secret 后断言）、白名单三类之外零进包
（x.log.bak 等非数字分卷后缀拒收）、应含项齐全（log+数字分卷+launch_error+
diagnostic_info+操作日志文本）、操作日志读取失败时包内放说明文件不中断导出、
下载成功与构包失败两条路径均无残留临时文件。"""

from __future__ import annotations

import glob
import io
import json
import os
import tempfile
import zipfile
from types import SimpleNamespace

import pytest


def _symlink_supported() -> bool:
    # Windows（尤其 Win7/无 SeCreateSymbolicLink 权限）创建软链接会 OSError——此时跳过
    # 软链接安全用例，避免把「平台权限失败」误判成「产品逻辑失败」（finding-01）。
    try:
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "t")
            open(target, "w").close()
            os.symlink(target, os.path.join(d, "l"))
        return True
    except (OSError, NotImplementedError):
        return False


_requires_symlink = pytest.mark.skipif(
    not _symlink_supported(), reason="平台不支持创建软链接（如 Win 无权限），跳过软链接安全用例"
)


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


@_requires_symlink
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


@_requires_symlink
def test_runtime_logs_page_refuses_symlink(app_client):
    # 页面查看日志链路与诊断包同一道锁：白名单真名（aps_error.log）被替换成软链接
    # 指向假 secret 时，读原语拒读，密文绝不回显到页面（finding-01 页面链路补齐）。
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps_secret_key.txt", "PAGE-LEAK-SECRET")
    link = os.path.join(log_dir, "aps_error.log")
    if os.path.lexists(link):
        os.remove(link)
    os.symlink(os.path.join(log_dir, "aps_secret_key.txt"), link)

    resp = app_client.get("/system/runtime-logs?file=aps_error.log")
    html = resp.get_data(as_text=True)
    resp.close()

    assert resp.status_code == 200
    assert "PAGE-LEAK-SECRET" not in html, "页面不应跟随软链接读取并回显非日志内容"


def test_operation_logs_failure_yields_explanation_file(app_client, monkeypatch):
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log")

    import web.routes.system_runtime_logs as mod

    def boom():
        raise RuntimeError(
            '{"source_table": "candidate_rows", "candidate_id": 7, "node_id": "op:SECRET", "op_code": "OP010"}'
        )

    monkeypatch.setattr(mod, "_get_operation_log_service", boom)
    names, data = _download_zip_names(app_client)
    assert "operation_logs_读取失败.txt" in names
    assert "operation_logs.txt" not in names
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        note = zf.read("operation_logs_读取失败.txt").decode("utf-8")
    assert "操作日志读取失败" in note
    assert "内部标识已省略" in note
    for forbidden in ("source_table", "candidate_rows", "candidate_id", "node_id", "op:", "op_code", "OP010"):
        assert forbidden not in note


def test_operation_logs_text_uses_public_projection(app_client, monkeypatch):
    log_dir = app_client.application.config["LOG_DIR"]
    _seed(log_dir, "aps.log")

    import web.routes.system_runtime_logs as mod

    detail = json.dumps(
        {
            "filters": {
                "candidate_id": 7,
                "candidate_key": "graph_w1_of_5",
                "adopted_candidate_key": "graph_w1_of_5",
                "source_table": "candidate_rows",
                "safe_label": "可见说明",
                "candidate_rows": {"safe_label": "不应保留"},
                "attempts_debug": "不应保留",
                "op_ref": "op:SECRET",
                "op_note": "样本 op_code：OP010 / OP020；裸编号 OP010 / OP020",
                "standalone": "candidate_rows 查询失败 attempts_debug graph_debug target_id=987",
            },
            "attempts": [{"candidate_id": 7, "source_table": "attempts_debug"}],
            "candidate_comparison": {"adopted_candidate_key": "graph_w1_of_5"},
            "graph_analysis": {"critical_path_sample": ["op:SECRET-NODE"], "status": "available"},
        },
        ensure_ascii=False,
    )

    class _Svc:
        @staticmethod
        def list_recent(limit):
            return [
                SimpleNamespace(
                    log_time="2026-06-26 10:00:00",
                    log_level="INFO",
                    module="scheduler",
                    action="export",
                    target_type="schedule",
                    target_id="987",
                    operator="system",
                    detail=detail,
                        error_message=(
                            "candidate_id=7 node_id=op:SECRET op_code=OP010 裸编号 OP010 "
                            "candidate_key=graph_w1_of_5 adopted_candidate_key=graph_w1_of_5 "
                            "candidate_rows attempts_debug graph_debug target_id=987"
                        ),
                )
            ]

    monkeypatch.setattr(mod, "_get_operation_log_service", lambda: _Svc())

    names, data = _download_zip_names(app_client)
    assert "operation_logs.txt" in names
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        text = zf.read("operation_logs.txt").decode("utf-8")

    assert "可见说明" in text
    assert "内部标识已省略" in text
    for forbidden in (
        "op:",
        "candidate_id",
        "candidate_key",
        "adopted_candidate_key",
        "source_table",
        "node_id",
        "op_code",
        "OP010",
        "OP020",
        "critical_path_sample",
        "attempts",
        "SECRET",
        "candidate_rows",
        "attempts_debug",
        "graph_debug",
        "target_id",
        "987",
        "graph_w1_of_5",
    ):
        assert forbidden not in text


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

"""
回归测试：launcher 运行时契约文件。

验证点：
1) `write_runtime_contract_file()` 能写出包含 pid/host/port/token/data_dirs 的契约。
2) `read_runtime_contract()` 能正确解析契约。
3) `delete_runtime_contract_files()` 会一并清理 host/port/db/runtime.json。
4) 当 `cfg_log_dir != runtime_dir/logs` 时，镜像目录中的 host/port/db 文件也会被清理。
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _load_launcher():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher", None)
    return importlib.import_module("web.bootstrap.launcher")


def _write_contract_payload(runtime_dir: Path, payload) -> Path:
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    contract_path = state_dir / "aps_runtime.json"
    contract_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return contract_path


def _valid_contract_payload(runtime_dir: Path) -> dict:
    return {
        "contract_version": 1,
        "pid": 12345,
        "host": "127.0.0.1",
        "port": 5000,
        "shutdown_token": "runtime-token",
        "exe_path": sys.executable,
        "runtime_dir": str(runtime_dir),
        "chrome_profile_dir": str(runtime_dir / "chrome109_profile"),
    }


def test_read_runtime_contract_result_statuses(tmp_path: Path) -> None:
    launcher = _load_launcher()
    runtime_dir = tmp_path / "runtime"

    missing = launcher.read_runtime_contract_result(str(runtime_dir))
    assert missing.status == "missing"
    assert not missing.ok
    assert launcher.read_runtime_contract(str(runtime_dir)) is None

    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "aps_runtime.json").write_text("{bad-json", encoding="utf-8")
    unreadable = launcher.read_runtime_contract_result(str(runtime_dir))
    assert unreadable.status == "unreadable"
    assert unreadable.error
    assert launcher.read_runtime_contract(str(runtime_dir)) is None

    _write_contract_payload(runtime_dir, ["not", "dict"])
    invalid_type = launcher.read_runtime_contract_result(str(runtime_dir))
    assert invalid_type.status == "invalid"
    assert invalid_type.reason == "contract_not_object"

    payload = _valid_contract_payload(runtime_dir)
    payload["contract_version"] = 2
    _write_contract_payload(runtime_dir, payload)
    invalid_version = launcher.read_runtime_contract_result(str(runtime_dir))
    assert invalid_version.status == "invalid"
    assert invalid_version.reason == "contract_version_mismatch"

    for key in ("pid", "port"):
        payload = _valid_contract_payload(runtime_dir)
        payload[key] = 0
        _write_contract_payload(runtime_dir, payload)
        invalid_field = launcher.read_runtime_contract_result(str(runtime_dir))
        assert invalid_field.status == "invalid"
        assert invalid_field.reason == f"invalid_{key}"

    for key in ("shutdown_token", "exe_path", "runtime_dir", "chrome_profile_dir"):
        payload = _valid_contract_payload(runtime_dir)
        payload[key] = ""
        _write_contract_payload(runtime_dir, payload)
        missing_field = launcher.read_runtime_contract_result(str(runtime_dir))
        assert missing_field.status == "invalid"
        assert missing_field.reason == f"missing_{key}"

    payload = _valid_contract_payload(runtime_dir)
    _write_contract_payload(runtime_dir, payload)
    valid = launcher.read_runtime_contract_result(str(runtime_dir))
    assert valid.status == "valid"
    assert valid.ok
    assert valid.payload is not None
    assert launcher.read_runtime_contract(str(runtime_dir)) is not None


def _write_cleanup_artifacts(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "aps_port.txt",
        "aps_host.txt",
        "aps_db_path.txt",
        "aps_runtime.lock",
        "aps_launch_error.txt",
    ):
        (log_dir / name).write_text("x\n", encoding="utf-8")


def test_delete_runtime_contract_files_result_reports_success_and_missing(tmp_path: Path) -> None:
    launcher = _load_launcher()
    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    _write_cleanup_artifacts(state_dir)
    payload = _valid_contract_payload(runtime_dir)
    _write_contract_payload(runtime_dir, payload)
    (state_dir / "aps_launch_error.txt").unlink()

    result = launcher.delete_runtime_contract_files_result(str(runtime_dir))

    assert result.ok
    assert str(state_dir / "aps_runtime.json") in result.removed_paths
    assert str(state_dir / "aps_launch_error.txt") in result.missing_paths
    assert result.failures == ()


def test_delete_runtime_contract_files_result_reports_remove_failure(monkeypatch, tmp_path: Path) -> None:
    launcher = _load_launcher()
    cleanup_mod = importlib.import_module("web.bootstrap.launcher_cleanup_result")
    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    _write_cleanup_artifacts(state_dir)
    _write_contract_payload(runtime_dir, _valid_contract_payload(runtime_dir))
    blocked_path = str(state_dir / "aps_host.txt")
    real_remove = cleanup_mod.os.remove

    def _remove(path):
        if str(path) == blocked_path:
            raise PermissionError("locked")
        return real_remove(path)

    monkeypatch.setattr(cleanup_mod.os, "remove", _remove)

    result = launcher.delete_runtime_contract_files_result(str(runtime_dir))

    assert not result.ok
    assert any(failure.path == blocked_path and failure.reason == "remove_failed" for failure in result.failures)


def test_delete_runtime_contract_files_result_reports_mirror_failure(monkeypatch, tmp_path: Path) -> None:
    launcher = _load_launcher()
    cleanup_mod = importlib.import_module("web.bootstrap.launcher_cleanup_result")
    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    mirror_dir = runtime_dir / "logs_mirror"
    _write_cleanup_artifacts(state_dir)
    _write_cleanup_artifacts(mirror_dir)
    payload = _valid_contract_payload(runtime_dir)
    payload["data_dirs"] = {"log_dir": str(mirror_dir)}
    _write_contract_payload(runtime_dir, payload)
    blocked_path = str(mirror_dir / "aps_host.txt")
    real_remove = cleanup_mod.os.remove

    def _remove(path):
        if str(path) == blocked_path:
            raise PermissionError("mirror locked")
        return real_remove(path)

    monkeypatch.setattr(cleanup_mod.os, "remove", _remove)

    result = launcher.delete_runtime_contract_files_result(str(runtime_dir))

    assert not result.ok
    assert str(mirror_dir) in result.target_dirs
    assert any(failure.path == blocked_path for failure in result.failures)


def test_delete_runtime_contract_files_wrapper_keeps_legacy_no_raise(monkeypatch, tmp_path: Path) -> None:
    launcher = _load_launcher()
    cleanup_mod = importlib.import_module("web.bootstrap.launcher_cleanup_result")
    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    _write_cleanup_artifacts(state_dir)
    _write_contract_payload(runtime_dir, _valid_contract_payload(runtime_dir))

    def _remove(_path):
        raise PermissionError("locked")

    monkeypatch.setattr(cleanup_mod.os, "remove", _remove)

    launcher.delete_runtime_contract_files(str(runtime_dir))


def test_write_runtime_contract_file_writes_mirrors_and_cleanup(tmp_path: Path) -> None:
    launcher = _load_launcher()
    runtime_dir = tmp_path / "runtime"
    db_path = runtime_dir / "db" / "aps.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("", encoding="utf-8")
    runtime_log_dir = runtime_dir / "logs"
    mirror_log_dir = runtime_dir / "logs_mirror"
    backup_dir = runtime_dir / "backups"
    excel_template_dir = runtime_dir / "templates_excel"
    chrome_profile_dir = runtime_dir / "chrome109_profile"

    launcher.write_runtime_host_port_files(
        runtime_dir=str(runtime_dir),
        cfg_log_dir=str(mirror_log_dir),
        host="0.0.0.0",
        port=5728,
        db_path=str(db_path),
    )
    launcher.write_runtime_contract_file(
        str(runtime_dir),
        "0.0.0.0",
        5728,
        db_path=str(db_path),
        shutdown_token="runtime-contract-token",
        ui_mode="default",
        log_dir=str(mirror_log_dir),
        backup_dir=str(backup_dir),
        excel_template_dir=str(excel_template_dir),
        exe_path=sys.executable,
        chrome_profile_dir=str(chrome_profile_dir),
    )

    contract = launcher.read_runtime_contract(str(runtime_dir))
    assert contract is not None
    assert int(contract.get("contract_version") or 0) == 1
    assert int(contract.get("pid") or 0) > 0
    assert str(contract.get("host") or "") == "127.0.0.1"
    assert int(contract.get("port") or 0) == 5728
    assert str(contract.get("shutdown_token") or "") == "runtime-contract-token"
    assert str(contract.get("db_path") or "") == os.path.normcase(os.path.abspath(str(db_path)))
    data_dirs = contract.get("data_dirs") or {}
    assert str(data_dirs.get("log_dir") or "") == os.path.abspath(str(mirror_log_dir))
    assert str(data_dirs.get("backup_dir") or "") == os.path.abspath(str(backup_dir))
    assert str(data_dirs.get("excel_template_dir") or "") == os.path.abspath(str(excel_template_dir))
    assert str(contract.get("chrome_profile_dir") or "") == os.path.abspath(str(chrome_profile_dir))
    assert (runtime_log_dir / "aps_host.txt").exists()
    assert (runtime_log_dir / "aps_port.txt").exists()
    assert (runtime_log_dir / "aps_db_path.txt").exists()
    assert (mirror_log_dir / "aps_host.txt").exists()
    assert (mirror_log_dir / "aps_port.txt").exists()
    assert (mirror_log_dir / "aps_db_path.txt").exists()

    launcher.delete_runtime_contract_files(str(runtime_dir))
    assert not (runtime_log_dir / "aps_host.txt").exists()
    assert not (runtime_log_dir / "aps_port.txt").exists()
    assert not (runtime_log_dir / "aps_db_path.txt").exists()
    assert not (runtime_log_dir / "aps_runtime.json").exists()
    assert not (mirror_log_dir / "aps_host.txt").exists()
    assert not (mirror_log_dir / "aps_port.txt").exists()
    assert not (mirror_log_dir / "aps_db_path.txt").exists()

"""锁定 Win7 打包与安装契约：停机助手安装时只用随包程序、卸载时只信任 Program Files 下的安装目录，构建预检负责 networkx 离线轮子校验，ISCC 统一由 resolve_iscc.ps1 解析，validate_dist_exe 隔离环境并保护用户数据。"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_win7_build import REPO_ROOT, dependency_errors, vendor_wheel_errors


def _function_block(source: str, signature: str) -> str:
    start = source.index(signature)
    next_func = source.find("\nfunction ", start + len(signature))
    next_proc = source.find("\nprocedure ", start + len(signature))
    candidates = [pos for pos in (next_func, next_proc) if pos != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def test_installer_stop_helper_trusts_only_bundled_helper_on_install_and_program_files_on_uninstall() -> None:
    iss = (REPO_ROOT / "installer" / "aps_win7_shared.iss").read_text(encoding="utf-8")

    protected_block = _function_block(iss, "function IsUnderProtectedProgramFiles(const DirPath: String): Boolean;")
    for token in (
        "ExpandConstant('{pf}')",
        "ExpandConstant('{commonpf}')",
        "ExpandConstant('{pf32}')",
        "ExpandConstant('{commonpf32}')",
        "ExpandConstant('{pf64}')",
        "ExpandConstant('{commonpf64}')",
    ):
        assert token in protected_block

    trusted_block = _function_block(iss, "function IsTrustedInstallDir(const DirPath: String): Boolean;")
    assert "if not IsUnderProtectedProgramFiles(TrimmedDir) then" in trusted_block

    resolve_block = _function_block(iss, "function ResolveStopHelperExe: String;")
    install_branch_pos = resolve_block.index("if not IsUninstaller then")
    extract_pos = resolve_block.index("ExtractTemporaryFiles('{app}\\*');")
    current_dir_pos = resolve_block.index("CurrentAppDir := ExpandConstant('{app}');")
    registered_dir_pos = resolve_block.index("RegisteredAppDir := RegisteredMainAppDirPath;")

    assert install_branch_pos < extract_pos < current_dir_pos < registered_dir_pos
    install_branch = resolve_block[install_branch_pos:current_dir_pos]
    assert "RegisteredMainAppDirPath" not in install_branch
    assert "AppExePathFromDir" not in install_branch
    assert "Exit;\n  end;" in install_branch or "Exit;\r\n  end;" in install_branch


def test_win7_build_preflight_owns_networkx_and_vendor_wheel_verification(tmp_path: Path) -> None:
    bat = (REPO_ROOT / "build_win7_onedir.bat").read_text(encoding="utf-8")
    assert "python scripts\\check_win7_build.py" in bat

    manifest = json.loads((REPO_ROOT / "packaging" / "win7" / "offline-manifest.json").read_text(encoding="utf-8"))
    nx_entries = [entry for entry in manifest["files"] if entry.get("name") == "networkx"]
    assert len(nx_entries) == 1
    assert nx_entries[0]["version"] == "3.1"
    assert dependency_errors(nx_entries) == []

    assert vendor_wheel_errors(REPO_ROOT) == []
    assert vendor_wheel_errors(tmp_path) == ["vendor/wheels/networkx-3.1-*.whl: missing offline wheel"]


def test_iscc_resolution_is_centralized_in_resolve_iscc_ps1() -> None:
    resolver = (REPO_ROOT / "tools" / "resolve_iscc.ps1").read_text(encoding="utf-8")
    assert resolver.isascii()
    for token in (
        '$env:ISCC_EXE',
        '[ERROR] ISCC_EXE points to a missing file:',
        '$env:INNO_HOME',
        '[ERROR] INNO_HOME does not contain ISCC.exe:',
        'Programs\\Inno Setup 6\\ISCC.exe',
        'GetEnvironmentVariable("ProgramFiles(x86)")',
        '$env:ProgramFiles',
        'Get-Command "ISCC.exe"',
    ):
        assert token in resolver

    package_ps1 = (REPO_ROOT / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(
        encoding="utf-8"
    )
    assert package_ps1.isascii()
    assert 'Join-Path $repoRoot "tools\\resolve_iscc.ps1"' in package_ps1
    assert 'Programs\\Inno Setup 6\\ISCC.exe' not in package_ps1
    assert "Set-HostPortDefaults" not in package_ps1
    assert "APS_PORT=" not in package_ps1
    assert "Get-FreePort" in package_ps1

    installer_bat = (REPO_ROOT / "build_win7_installer.bat").read_text(encoding="utf-8")
    assert '"%CD%\\tools\\resolve_iscc.ps1"' in installer_bat
    assert ":find_iscc" not in installer_bat


def test_validate_dist_exe_isolates_non_portable_env_and_protects_existing_portable_user_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import os
    import sys

    import validate_dist_exe

    # 1) 非便携版：宿主机既有 APS_* 与契约文件完好无损，子进程使用独立 TemporaryDirectory 作为 APS_SHARED_DATA_ROOT
    host_shared = tmp_path / "host_shared"
    host_logs = host_shared / "logs"
    host_db_dir = host_shared / "db"
    host_logs.mkdir(parents=True)
    host_db_dir.mkdir(parents=True)
    host_contract = host_logs / "aps_host.txt"
    host_port = host_logs / "aps_port.txt"
    host_db_contract = host_logs / "aps_db_path.txt"
    host_db = host_db_dir / "aps.db"
    host_contract.write_text("127.0.0.1\n", encoding="utf-8")
    host_port.write_text("5000\n", encoding="utf-8")
    host_db_contract.write_text(str(host_db) + "\n", encoding="utf-8")
    host_db.write_bytes(b"precious-production-db")

    dist_dir = tmp_path / "dist_app"
    dist_dir.mkdir()
    exe_file = dist_dir / "排产系统.exe"
    exe_file.write_bytes(b"fake-exe")

    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(host_shared))
    monkeypatch.setenv("APS_LOG_DIR", str(host_logs))
    monkeypatch.setenv("APS_DB_PATH", str(host_db))
    monkeypatch.setenv("APS_PORT", "5999")
    monkeypatch.setattr(sys, "argv", ["validate_dist_exe.py", str(exe_file)])
    monkeypatch.setattr(validate_dist_exe, "_assert_networkx_bundled", lambda _exe: None)
    monkeypatch.setattr(validate_dist_exe, "_assert_static_bundled", lambda _cwd: None)
    monkeypatch.setattr(validate_dist_exe, "_wait_port_open", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(validate_dist_exe, "_assert_health", lambda *_args, **_kwargs: {"app": "aps", "status": "ok", "contract_version": 1})
    monkeypatch.setattr(validate_dist_exe, "_assert_workbench_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(validate_dist_exe, "_assert_retired_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(validate_dist_exe, "_http_get_bytes", lambda *_args, **_kwargs: b"non-empty-static")

    captured_runs = []

    class FakeProc:
        def __init__(self, args, *, cwd, env, **_kwargs):
            self.args = args
            self.cwd = cwd
            self.env = dict(env)
            self.pid = 43210
            self.terminated = False
            self.returncode = None
            root = Path(self.env["APS_SHARED_DATA_ROOT"])
            logs = root / "logs"
            db_file = root / "db" / "aps.db"
            logs.mkdir(parents=True, exist_ok=True)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db_file.write_bytes(b"isolated-validation-db")
            (logs / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
            (logs / "aps_port.txt").write_text("51234\n", encoding="utf-8")
            (logs / "aps_db_path.txt").write_text(str(db_file) + "\n", encoding="utf-8")
            captured_runs.append((root, self.env))

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(validate_dist_exe.subprocess, "Popen", FakeProc)
    assert validate_dist_exe.main() == 0
    assert len(captured_runs) == 1
    isolated_root, child_env = captured_runs[0]
    assert [key for key in child_env if key.upper().startswith("APS_")] == ["APS_SHARED_DATA_ROOT"]
    assert os.path.normcase(str(isolated_root)) != os.path.normcase(str(host_shared))
    assert not isolated_root.exists()  # 结束后临时目录已清理
    assert host_contract.read_text(encoding="utf-8") == "127.0.0.1\n"
    assert host_db.read_bytes() == b"precious-production-db"

    # 2) 便携版：当 <cwd>/user-data 已存在时直接拒绝且绝不删除既有数据
    (dist_dir / "aps-portable.txt").write_text("portable\n", encoding="utf-8")
    existing_user_data = dist_dir / "user-data"
    existing_user_data.mkdir()
    existing_marker = existing_user_data / "keep.txt"
    existing_marker.write_text("keep-existing-portable-data", encoding="utf-8")
    captured_runs.clear()
    assert validate_dist_exe.main() == 5
    assert captured_runs == []
    assert existing_marker.read_text(encoding="utf-8") == "keep-existing-portable-data"

    # 3) 便携版：当 <cwd>/user-data 不存在时，剥离所有 APS_* 启动并在 finally 中清理新建的 user-data
    existing_marker.unlink()
    existing_user_data.rmdir()

    class FakePortableProc:
        def __init__(self, args, *, cwd, env, **_kwargs):
            self.env = dict(env)
            self.pid = 43211
            self.returncode = None
            user_data = Path(cwd) / "user-data"
            logs = user_data / "logs"
            db_file = user_data / "db" / "aps.db"
            logs.mkdir(parents=True, exist_ok=True)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db_file.write_bytes(b"portable-validation-db")
            (logs / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
            (logs / "aps_port.txt").write_text("51235\n", encoding="utf-8")
            (logs / "aps_db_path.txt").write_text(str(db_file) + "\n", encoding="utf-8")
            captured_runs.append((user_data, self.env))

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(validate_dist_exe.subprocess, "Popen", FakePortableProc)
    assert validate_dist_exe.main() == 0
    assert len(captured_runs) == 1
    portable_root, portable_env = captured_runs[0]
    assert [key for key in portable_env if key.upper().startswith("APS_")] == []
    assert not portable_root.exists()

    # 4) 便携版：若收尾清理 user-data 失败，绝不能静默返回 0，必须返回非零退出码 5
    captured_runs.clear()

    def fail_rmtree(_path):
        raise PermissionError("simulated portable user-data lock")

    monkeypatch.setattr(validate_dist_exe.shutil, "rmtree", fail_rmtree)
    assert validate_dist_exe.main() == 5
    assert len(captured_runs) == 1


def test_validate_dist_exe_fails_and_preserves_isolated_data_when_child_cannot_be_stopped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import shutil
    import sys

    import validate_dist_exe

    dist_dir = tmp_path / "dist_app"
    dist_dir.mkdir()
    exe_file = dist_dir / "排产系统.exe"
    exe_file.write_bytes(b"fake-exe")

    monkeypatch.setattr(sys, "argv", ["validate_dist_exe.py", str(exe_file)])
    monkeypatch.setattr(validate_dist_exe, "_assert_networkx_bundled", lambda _exe: None)
    monkeypatch.setattr(validate_dist_exe, "_assert_static_bundled", lambda _cwd: None)
    monkeypatch.setattr(validate_dist_exe, "_wait_port_open", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        validate_dist_exe,
        "_assert_health",
        lambda *_args, **_kwargs: {"app": "aps", "status": "ok", "contract_version": 1},
    )
    monkeypatch.setattr(validate_dist_exe, "_assert_workbench_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(validate_dist_exe, "_assert_retired_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(validate_dist_exe, "_http_get_bytes", lambda *_args, **_kwargs: b"non-empty-static")

    captured_roots = []

    class UnstoppableProc:
        def __init__(self, args, *, cwd, env, **_kwargs):
            self.pid = 99999
            root = Path(env.get("APS_SHARED_DATA_ROOT") or (Path(cwd) / "user-data"))
            logs = root / "logs"
            db_file = root / "db" / "aps.db"
            logs.mkdir(parents=True, exist_ok=True)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db_file.write_bytes(b"active-child-db")
            (logs / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
            (logs / "aps_port.txt").write_text("51236\n", encoding="utf-8")
            (logs / "aps_db_path.txt").write_text(str(db_file) + "\n", encoding="utf-8")
            captured_roots.append(root)

        def poll(self):
            return None

        def terminate(self):
            raise PermissionError("simulated terminate denied")

        def kill(self):
            raise PermissionError("simulated kill denied")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(validate_dist_exe.subprocess, "Popen", UnstoppableProc)

    # 非便携版：子进程仍存活时返回 5 且保留隔离数据目录
    try:
        assert validate_dist_exe.main() == 5
        assert len(captured_roots) == 1
        non_portable_root = captured_roots[0]
        assert non_portable_root.exists()
        assert (non_portable_root / "db" / "aps.db").read_bytes() == b"active-child-db"
    finally:
        for root in captured_roots:
            if root.exists():
                shutil.rmtree(root)

    # 便携版：子进程仍存活时同样返回 5 且保留 user-data
    captured_roots.clear()
    (dist_dir / "aps-portable.txt").write_text("portable\n", encoding="utf-8")
    assert validate_dist_exe.main() == 5
    assert len(captured_roots) == 1
    portable_root = captured_roots[0]
    assert portable_root.exists()
    assert (portable_root / "db" / "aps.db").read_bytes() == b"active-child-db"

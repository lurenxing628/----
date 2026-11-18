"""锁定 Win7 打包与安装契约：停机助手安装时只用随包程序、卸载时只信任 Program Files 下的安装目录，构建预检负责 networkx 离线轮子
与 JSON1 SQLite 校验，离线材料把 JSON1 SQLite 装配进隔离构建环境，打包脚本只认仓库构建 venv、自己解析 ISCC，validate_dist_exe 隔离环境、
保护用户数据并实读值班台，便携目录说明与标记只经固定文件原语写入，入口脚本在 PowerShell 版本不足时返回非零。"""

from __future__ import annotations

import _sqlite3
import functools
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional, Tuple

import pytest

import scripts.check_win7_build as check_win7_build
from core.infrastructure import sqlite_udf
from core.infrastructure.database import get_connection
from core.infrastructure.snapshot_connection import open_readonly_immutable
from scripts.check_win7_build import REPO_ROOT, dependency_errors, sqlite_runtime_errors, vendor_wheel_errors
from scripts.prepare_win7_offline import SQLITE_PTH_LINE, load_manifest, stage_sqlite

PACKAGE_PS1 = REPO_ROOT / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1"


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
    assert '"%APS_BUILD_PYTHON%" scripts\\check_win7_build.py' in bat

    manifest = json.loads((REPO_ROOT / "packaging" / "win7" / "offline-manifest.json").read_text(encoding="utf-8"))
    nx_entries = [entry for entry in manifest["files"] if entry.get("name") == "networkx"]
    assert len(nx_entries) == 1
    assert nx_entries[0]["version"] == "3.1"
    assert dependency_errors(nx_entries) == []

    assert vendor_wheel_errors(REPO_ROOT) == []
    assert vendor_wheel_errors(tmp_path) == ["vendor/wheels/networkx-3.1-*.whl: missing offline wheel"]


def _powershell_runtime() -> Tuple[str, Tuple[int, int]]:
    """测试所用 PowerShell 及其主次版本号；原生 Win7 宿主可能只有 2.0。"""
    return _probe_powershell(os.environ.get("APS_TEST_POWERSHELL"))


@functools.lru_cache(maxsize=4)
def _probe_powershell(configured: Optional[str]) -> Tuple[str, Tuple[int, int]]:
    executable = configured or shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        pytest.skip("PowerShell runtime is needed to execute package_win7.ps1")
    probe = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                           capture_output=True, timeout=60)
    assert probe.returncode == 0, probe.stdout + probe.stderr
    major, minor = probe.stdout.decode("ascii").strip().split(".")[:2]
    return executable, (int(major), int(minor))


def _run_powershell(script: Path, **environment) -> subprocess.CompletedProcess:
    executable, _ = _powershell_runtime()
    return subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        env=dict(os.environ, **environment), capture_output=True, timeout=60,
    )


def _run_package_functions(tmp_path: Path, body: str) -> list:
    """只载入 package_win7.ps1 的函数定义（不进打包主流程），用真实 PowerShell 执行 body 并返回输出行。"""
    if _powershell_runtime()[1] < (5, 1):
        pytest.skip("PowerShell 5.1+ is needed to execute package_win7.ps1 functions")
    driver = tmp_path / "package-functions.ps1"
    driver.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)\n"
        "$ast = [Management.Automation.Language.Parser]::ParseFile($env:APS_TEST_PACKAGE_PS1, [ref]$null, [ref]$null)\n"
        "$isFunction = { param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }\n"
        "foreach ($function in $ast.FindAll($isFunction, $false)) { . ([ScriptBlock]::Create($function.Extent.Text)) }\n"
        + body,
        encoding="utf-8-sig",
    )
    result = _run_powershell(driver, APS_TEST_PACKAGE_PS1=str(PACKAGE_PS1), APS_TEST_ROOT=str(tmp_path))
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
    return result.stdout.decode("utf-8-sig").splitlines()


def test_resolve_iscc_honors_explicit_settings_then_default_folders_then_path(tmp_path: Path) -> None:
    found = {
        "explicit": tmp_path / "custom" / "ISCC.exe",
        "inno_home": tmp_path / "inno" / "ISCC.exe",
        "local": tmp_path / "local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
        "pf86": tmp_path / "pf86" / "Inno Setup 6" / "ISCC.exe",
        "pf": tmp_path / "pf" / "Inno Setup 6" / "ISCC.exe",
        "path": tmp_path / "path" / "ISCC.exe",
    }
    for path in found.values():
        path.parent.mkdir(parents=True)
        path.write_bytes(b"MZ")
        path.chmod(0o755)
    (tmp_path / "empty").mkdir()
    rows = _run_package_functions(tmp_path, r'''
function Use-Iscc([string]$Explicit, [string]$InnoHome, [string]$Local, [string]$Pf86, [string]$Pf, [string]$PathDir) {
    $env:ISCC_EXE = $Explicit
    $env:INNO_HOME = $InnoHome
    $env:LOCALAPPDATA = Join-Path $env:APS_TEST_ROOT $Local
    [Environment]::SetEnvironmentVariable('ProgramFiles(x86)', (Join-Path $env:APS_TEST_ROOT $Pf86))
    $env:ProgramFiles = Join-Path $env:APS_TEST_ROOT $Pf
    $env:PATH = Join-Path $env:APS_TEST_ROOT $PathDir
}
function Show-Iscc([string]$Name) {
    try { $Name + '=' + (Resolve-Iscc) } catch { $Name + '!' + $_.Exception.Message }
}
$root = $env:APS_TEST_ROOT
Use-Iscc '' '' 'empty' 'empty' 'empty' 'empty'; Show-Iscc 'NONE'
Use-Iscc '' '' 'empty' 'empty' 'empty' 'path'; Show-Iscc 'PATH'
Use-Iscc '' '' 'empty' 'empty' 'pf' 'path'; Show-Iscc 'PF'
Use-Iscc '' '' 'empty' 'pf86' 'pf' 'path'; Show-Iscc 'PF86'
Use-Iscc '' '' 'local' 'pf86' 'pf' 'path'; Show-Iscc 'LOCAL'
Use-Iscc '' (Join-Path $root 'empty') 'local' 'pf86' 'pf' 'path'; Show-Iscc 'HOME_MISSING'
Use-Iscc '' (' ' + (Join-Path $root 'inno') + ' ') 'local' 'pf86' 'pf' 'path'; Show-Iscc 'HOME'
Use-Iscc (Join-Path $root 'missing.exe') (Join-Path $root 'inno') 'local' 'pf86' 'pf' 'path'; Show-Iscc 'EXPLICIT_MISSING'
Use-Iscc (' ' + (Join-Path $root 'custom\ISCC.exe') + ' ') (Join-Path $root 'empty') 'local' 'pf86' 'pf' 'path'; Show-Iscc 'EXPLICIT'
''')
    parsed = [re.fullmatch(r"([A-Z_0-9]+)([=!])(.*)", row).groups() for row in rows]
    assert {name for name, sign, _ in parsed if sign == "!"} == {"NONE", "HOME_MISSING", "EXPLICIT_MISSING"}, rows
    results = {name: value for name, _, value in parsed}
    assert results["NONE"] == "ISCC.exe not found. Install Inno Setup 6 or set ISCC_EXE/INNO_HOME."
    assert results["HOME_MISSING"].startswith("INNO_HOME does not contain ISCC.exe:")
    assert results["EXPLICIT_MISSING"].startswith("ISCC_EXE points to a missing file:")
    for name, key in (("PATH", "path"), ("PF", "pf"), ("PF86", "pf86"), ("LOCAL", "local"),
                      ("HOME", "inno_home"), ("EXPLICIT", "explicit")):
        assert Path(results[name]).samefile(found[key]), (name, results[name])


def test_package_script_uses_only_the_repository_build_venv(tmp_path: Path) -> None:
    venv_python = tmp_path / "repo" / ".venv-win7-build" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"MZ")
    (tmp_path / "bare-repo").mkdir()
    rows = _run_package_functions(tmp_path, r'''
'FOUND=' + (Resolve-PythonExe (Join-Path $env:APS_TEST_ROOT 'repo'))
try { Resolve-PythonExe (Join-Path $env:APS_TEST_ROOT 'bare-repo') } catch { 'MISSING!' + $_.Exception.Message }
''')
    assert Path(rows[0].split("=", 1)[1]).samefile(venv_python)
    assert rows[1].startswith("MISSING!Build venv python not found:") and "Run setup_win7_build.bat first." in rows[1]


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
    monkeypatch.setattr(validate_dist_exe, "_assert_workbench_dashboard_api", lambda *_args, **_kwargs: None)
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
    monkeypatch.setattr(validate_dist_exe, "_assert_workbench_dashboard_api", lambda *_args, **_kwargs: None)
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


def _sqlite_entry() -> dict:
    entries = [entry for entry in load_manifest() if entry["name"] == "SQLite DLL"]
    assert len(entries) == 1
    return entries[0]


def test_offline_manifest_pins_official_json1_sqlite_dll() -> None:
    entry = _sqlite_entry()
    assert entry["version"] == "3.35.5"
    assert entry["path"] == "tools/sqlite-dll-win64-x64-3350500.zip"
    assert entry["url"] == entry["source"] == "https://www.sqlite.org/2021/sqlite-dll-win64-x64-3350500.zip"
    assert entry["size"] == 900912


def _stage_layout(tmp_path: Path):
    offline = tmp_path / "offline" / "win7"
    archive = offline / "tools" / "sqlite-dll-win64-x64-3350500.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(str(archive), "w") as bundle:
        bundle.writestr("sqlite3.def", "EXPORTS\n")
        bundle.writestr("sqlite3.dll", b"MZ-json1-sqlite")
    base = tmp_path / "基础 Python 3.8"
    (base / "DLLs").mkdir(parents=True)
    (base / "DLLs" / "_sqlite3.pyd").write_bytes(b"MZ-base-pyd")
    venv = tmp_path / "构建 venv"
    (venv / "Lib" / "site-packages").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = " + str(base) + "\ninclude-system-site-packages = false\nversion = 3.8.10\n",
                                     encoding="utf-8")
    entry = dict(_sqlite_entry(), size=archive.stat().st_size)
    return offline, venv, entry


def test_stage_sqlite_puts_json1_dll_and_base_pyd_first_on_build_venv_path(tmp_path: Path) -> None:
    offline, venv, entry = _stage_layout(tmp_path)
    stage_sqlite(offline, venv, [entry])

    assert (venv / "DLLs" / "sqlite3.dll").read_bytes() == b"MZ-json1-sqlite"
    assert (venv / "DLLs" / "_sqlite3.pyd").read_bytes() == b"MZ-base-pyd"
    pth = venv / "Lib" / "site-packages" / "_win7_sqlite.pth"
    assert pth.read_bytes() == SQLITE_PTH_LINE.encode("ascii")
    # site 真正执行这行 .pth：<prefix>/DLLs 排在 sys.path 最前，_sqlite3.pyd 与同目录 sqlite3.dll 先于基础解释器加载。
    first = subprocess.run(
        [sys.executable, "-c", "import site, sys; site.addsitedir(sys.argv[1]); print(sys.path[0]); print(sys.prefix)",
         str(pth.parent)], capture_output=True, encoding="utf-8", check=True, timeout=60,
    ).stdout.splitlines()
    assert Path(first[0]) == Path(first[1]) / "DLLs"


def test_stage_sqlite_refuses_mismatched_archive_without_touching_venv(tmp_path: Path) -> None:
    offline, venv, entry = _stage_layout(tmp_path)
    with pytest.raises(ValueError, match="Size mismatch"):
        stage_sqlite(offline, venv, [dict(entry, size=entry["size"] + 1)])
    with pytest.raises(ValueError, match="exactly one SQLite DLL"):
        stage_sqlite(offline, venv, [])
    assert not (venv / "DLLs").exists()
    assert not (venv / "Lib" / "site-packages" / "_win7_sqlite.pth").exists()


@pytest.mark.parametrize("relative", ["DLLs", "Lib", "Lib/site-packages"])
def test_stage_sqlite_rejects_redirected_venv_directories_before_writing(tmp_path: Path, relative: str) -> None:
    offline, venv, entry = _stage_layout(tmp_path)
    base = tmp_path / "基础 Python 3.8"
    (base / "Lib" / "site-packages").mkdir(parents=True)
    original_dll = base / "DLLs" / "sqlite3.dll"
    original_dll.write_bytes(b"original sqlite")
    link = venv / relative
    if link.exists():
        link.rename(tmp_path / "original venv directory")
    if sys.platform == "win32":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(base / relative)], check=True)
    else:
        link.symlink_to(base / relative, target_is_directory=True)

    with pytest.raises(ValueError, match="Build venv"):
        stage_sqlite(offline, venv, [entry])
    assert original_dll.read_bytes() == b"original sqlite"
    assert not (base / "Lib" / "site-packages" / "_win7_sqlite.pth").exists()
    if relative != "DLLs":
        assert not (venv / "DLLs").exists()


def test_stage_sqlite_rejects_base_interpreter_as_target(tmp_path: Path) -> None:
    offline, venv, entry = _stage_layout(tmp_path)
    base = tmp_path / "基础 Python 3.8"
    (base / "Lib" / "site-packages").mkdir(parents=True)
    (base / "pyvenv.cfg").write_bytes((venv / "pyvenv.cfg").read_bytes())
    with pytest.raises(ValueError, match="Build venv"):
        stage_sqlite(offline, base, [entry])
    assert not (base / "DLLs" / "sqlite3.dll").exists()


class _MissingJson1Connection:
    def execute(self, _sql):
        raise sqlite3.OperationalError("no such table: json_each")

    def close(self) -> None:
        pass


@pytest.mark.parametrize(("fault", "marker"), [
    ("sys.modules['_sqlite3'] = None", "_sqlite3"),
    ("import sqlite3; sqlite3.sqlite_version_info = (3, 35, 4); sqlite3.sqlite_version = '3.35.4'", "3.35.4"),
])
def test_build_preflight_reports_unloadable_or_too_old_sqlite(fault, marker):
    code = "import runpy, sys\n" + fault + "\nrunpy.run_path('scripts/check_win7_build.py', run_name='__main__')"
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=REPO_ROOT,
                            capture_output=True, encoding="utf-8", timeout=30)
    assert result.returncode == 1
    assert any(line.startswith("[preflight] SQLite runtime unavailable:") and marker in line
               for line in result.stdout.splitlines()), result.stdout


@pytest.fixture
def fresh_sqlite_guard():
    sqlite_udf.ensure_sqlite_runtime.cache_clear()
    yield
    sqlite_udf.ensure_sqlite_runtime.cache_clear()


def test_sqlite_runtime_probe_runs_json1_functions_and_rejects_missing_or_wrong_results(
    monkeypatch, fresh_sqlite_guard
) -> None:
    sqlite_udf.ensure_sqlite_runtime()

    sqlite_udf.ensure_sqlite_runtime.cache_clear()
    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: _MissingJson1Connection())
    with pytest.raises(RuntimeError, match="缺少本程序必需的 JSON1 函数支持（no such table: json_each）"):
        sqlite_udf.ensure_sqlite_runtime()
    errors = sqlite_runtime_errors(REPO_ROOT)
    assert len(errors) == 1 and "JSON1" in errors[0]
    monkeypatch.undo()

    real_connect = sqlite3.connect

    def wrong_json_set(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.create_function("json_set", 3, lambda *_values: '{"k":"3"}')
        return conn

    monkeypatch.setattr(sqlite3, "connect", wrong_json_set)
    with pytest.raises(RuntimeError, match="JSON1 能力探针返回异常结果"):
        sqlite_udf.ensure_sqlite_runtime()


def test_product_connections_probe_once_and_refuse_before_creating_database(
    tmp_path: Path, monkeypatch, fresh_sqlite_guard
) -> None:
    real_connect = sqlite3.connect
    probes = []

    def counting_connect(target, *args, **kwargs):
        if target == ":memory:":
            probes.append(target)
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)
    for _ in range(2):
        get_connection(str(tmp_path / "probed-once.db")).close()
    assert probes == [":memory:"]

    sqlite_udf.ensure_sqlite_runtime.cache_clear()
    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: _MissingJson1Connection())
    db_file = tmp_path / "db" / "aps.db"
    db_file.parent.mkdir()
    for _ in range(2):  # 失败不缓存：每次触库都重新拒绝
        with pytest.raises(RuntimeError, match="JSON1"):
            get_connection(str(db_file))
    assert not db_file.exists()
    archive = tmp_path / "archive.db"
    archive.write_bytes(b"")
    with pytest.raises(RuntimeError, match="JSON1"):
        with open_readonly_immutable(str(archive)):
            pass


def _isolated_build_venv(tmp_path: Path, monkeypatch, name: str = ".venv-win7-build") -> Path:
    """在 tmp 里摆出 Windows 隔离构建环境的事实：一个 venv、基础解释器，以及进程实际从该 venv 加载的两个 SQLite 二进制。"""
    venv = tmp_path / name
    (venv / "DLLs").mkdir(parents=True, exist_ok=True)
    for binary in ("_sqlite3.pyd", "sqlite3.dll"):
        (venv / "DLLs" / binary).write_bytes(b"MZ")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "prefix", str(venv))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "Python38"))
    monkeypatch.setattr(_sqlite3, "__file__", str(venv / "DLLs" / "_sqlite3.pyd"))
    monkeypatch.setattr(check_win7_build, "_loaded_module_path", lambda module: venv / "DLLs" / module)
    return venv


def test_build_preflight_requires_isolated_venv_loading_staged_sqlite(tmp_path: Path, monkeypatch) -> None:
    venv = _isolated_build_venv(tmp_path, monkeypatch)
    assert sqlite_runtime_errors(tmp_path) == []

    monkeypatch.setattr(sys, "base_prefix", str(venv))
    assert sqlite_runtime_errors(tmp_path) == [
        "Build must run inside an isolated venv (setup_win7_build.bat), not base Python: " + str(venv.resolve())
    ]

    # 仓内还没建出 .venv-win7-build 时，外部 venv 同样被拒，而不是因仓内缺 venv 放行。
    uninitialized_repo = tmp_path / "uninitialized-repo"
    uninitialized_repo.mkdir()
    other = _isolated_build_venv(tmp_path, monkeypatch, "other-venv")
    assert not (uninitialized_repo / ".venv-win7-build").exists()
    assert sqlite_runtime_errors(uninitialized_repo) == [
        f"Build interpreter is not the repository build venv {uninitialized_repo / '.venv-win7-build'}: {other}"
    ]

    _isolated_build_venv(tmp_path, monkeypatch)
    base_pyd = tmp_path / "Python38" / "DLLs" / "_sqlite3.pyd"
    monkeypatch.setattr(_sqlite3, "__file__", str(base_pyd))
    assert sqlite_runtime_errors(tmp_path) == [
        f"_sqlite3.pyd is loaded from {base_pyd}, expected {venv / 'DLLs'}; run setup_win7_build.bat"
    ]

    def sqlite_dll_not_mapped(name):
        raise OSError(126, "The specified module could not be found")

    monkeypatch.setattr(check_win7_build, "_loaded_module_path", sqlite_dll_not_mapped)
    assert sqlite_runtime_errors(tmp_path) == [
        "Could not inspect loaded sqlite3.dll: [Errno 126] The specified module could not be found"
    ]


def test_dashboard_cold_start_read_accepts_real_empty_database_contract(app_client, monkeypatch, capsys) -> None:
    import validate_dist_exe

    response = app_client.get("/api/workbench/v1/dashboard")
    assert response.status_code == 200
    requested = []

    def serve(url, timeout):
        requested.append((url, timeout))
        return response.status_code, response.get_data(as_text=True), url

    monkeypatch.setattr(validate_dist_exe, "_http_get_page", serve)
    validate_dist_exe._assert_workbench_dashboard_api("http://127.0.0.1:5999", timeout=5.0)
    assert requested == [("http://127.0.0.1:5999/api/workbench/v1/dashboard", 5.0)]
    assert "[validate] GET /api/workbench/v1/dashboard -> 200" in capsys.readouterr().out


@pytest.mark.parametrize("status,analysis_error,reason", [
    (500, None, "GET /api/workbench/v1/dashboard -> 500"),
    (200, "值班台分析读取失败", "值班台分析没有正常读取"),
])
def test_dashboard_cold_start_rejects_failed_read_or_analysis_error(
    app_client, monkeypatch, status, analysis_error, reason
) -> None:
    """接口 500（仓储查询失败）与 200 但分析报错（路由把业务拒绝写进 analysis_error）都不能算冷启通过。"""
    import validate_dist_exe

    payload = app_client.get("/api/workbench/v1/dashboard").get_json()
    payload["data"]["analysis_error"] = analysis_error
    monkeypatch.setattr(validate_dist_exe, "_http_get_page", lambda url, timeout: (status, json.dumps(payload), url))
    with pytest.raises(RuntimeError, match=reason):
        validate_dist_exe._assert_workbench_dashboard_api("http://127.0.0.1:5999", timeout=5.0)


def test_frozen_startup_failure_preserves_first_error_before_portable_cleanup(tmp_path, monkeypatch, capsys):
    import validate_dist_exe

    exe = tmp_path / "排产系统.exe"
    exe.touch()
    (tmp_path / "aps-portable.txt").touch()
    logs = tmp_path / "user-data" / "logs"
    log_lines = []

    class ExitedProcess:
        def __init__(self, *args, **kwargs):
            logs.mkdir(parents=True)
            (logs / "launcher.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
            (logs / "aps_runtime.json").write_text('{"shutdown_token":"test-only-value"}', encoding="utf-8")

        def poll(self):
            return 14

        def terminate(self):
            pass

        def wait(self, timeout):
            return 14

    monkeypatch.setattr(sys, "argv", ["validate_dist_exe.py", str(exe)])
    monkeypatch.setattr(validate_dist_exe, "_assert_networkx_bundled", lambda _path: None)
    monkeypatch.setattr(validate_dist_exe, "_assert_static_bundled", lambda _path: None)
    monkeypatch.setattr(validate_dist_exe.subprocess, "Popen", ExitedProcess)
    monkeypatch.setattr(validate_dist_exe.tempfile, "tempdir", str(tmp_path))
    diagnostic = tmp_path / "aps-validate-startup-error.log"
    for first_error in ("2026-11-18 00:00:01 [ERROR] 应用启动失败：SQLite 缺少 JSON1",
                        "2026-11-18 00:05:00 [ERROR] 应用启动失败：端口被占用"):
        log_lines[:] = ["ignored", first_error, "2026-11-18 00:09:00 [ERROR] 后续连带错误"]
        assert validate_dist_exe.main() == 5
        output = capsys.readouterr().out
        assert "exit_code=14" in output and str(diagnostic) in output
        assert "test-only-value" not in output
        # 固定单槽：重复失败覆写同一文件，只留本次首错，不堆积随机名文件。
        assert diagnostic.read_text(encoding="utf-8") == first_error + "\n"
        assert list(tmp_path.glob("aps-validate-startup*")) == [diagnostic]
        assert not (tmp_path / "user-data").exists()


_CMD_ENTRIES = ("setup_win7_build.bat", "build_win7_onedir.bat", "build_win7_portable.bat", "build_win7_installer.bat",
                "stage_chrome109_to_dist.bat")
# PowerShell 2.0 先解析整份脚本再执行：出现这些 3.0+ 语法时，版本守卫来不及运行，调用方只能拿到解析错误。
_PS3_PARSE_ONLY_SYNTAX = re.compile(r"(?im)\s-(?:not)?in\s|::new\(|\[ordered\]|^\s*(?:class|enum|using)\s")


def test_cmd_entries_are_crlf_without_bom_and_keep_only_release_names_non_ascii() -> None:
    for name in _CMD_ENTRIES:
        data = (REPO_ROOT / name).read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf"), name
        assert data.count(b"\n") == data.count(b"\r\n") > 0, name
        text = data.decode("utf-8")
        assert "setlocal EnableExtensions DisableDelayedExpansion\r\n" in text, name
        non_ascii = [line for line in text.splitlines() if not line.isascii()]
        if name == "build_win7_onedir.bat":
            assert non_ascii and all("排产系统" in line for line in non_ascii)
        else:
            assert non_ascii == [], name


def test_package_script_is_ascii_lf_and_guards_version_before_anything_else(tmp_path: Path) -> None:
    data = PACKAGE_PS1.read_bytes()
    assert data.isascii() and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
    text = data.decode("ascii")
    assert "#Requires" not in text
    assert not _PS3_PARSE_ONLY_SYNTAX.search(text)

    # 两个构建入口与打包脚本按仓库相对位置摆进 tmp_path，CMD 入口实跑的就是这份低版本副本。
    for name in ("build_win7_portable.bat", "build_win7_installer.bat"):
        shutil.copyfile(str(REPO_ROOT / name), str(tmp_path / name))
    simulated = tmp_path / PACKAGE_PS1.relative_to(REPO_ROOT)
    simulated.parent.mkdir(parents=True)
    if _powershell_runtime()[1] < (5, 1):
        # 原生低版本宿主（如 Win7 自带 2.0）直接跑原脚本，不碰 3.0+ 才有的 AST 解析器。
        shutil.copyfile(str(PACKAGE_PS1), str(simulated))
    else:
        # $PSVersionTable 是常量，无法伪造低版本宿主：用 AST 找到首条语句里的 $PSVersionTable.PSVersion，
        # 只把它换成 [Version]"2.0" 后整份实跑，守卫必须先于其它任何语句报错并返回 2。
        builder = tmp_path / "simulate-powershell-2.ps1"
        builder.write_text(r'''
$ErrorActionPreference = 'Stop'
$ast = [Management.Automation.Language.Parser]::ParseFile($env:APS_TEST_PACKAGE_PS1, [ref]$null, [ref]$null)
if ($ast.DynamicParamBlock -or $ast.BeginBlock -or $ast.ProcessBlock) { throw 'Only an end block may run' }
$guard = $ast.EndBlock.Statements[0]
if ($guard -isnot [Management.Automation.Language.IfStatementAst]) { throw ('First statement is not an if: ' + $guard.Extent.Text) }
$version = $guard.Clauses[0].Item1.Find({ param($node)
    $node -is [Management.Automation.Language.MemberExpressionAst] -and
    $node.Expression.Extent.Text -eq '$PSVersionTable' -and $node.Member.Extent.Text -eq 'PSVersion' }, $true)
if ($null -eq $version) { throw 'First statement does not test $PSVersionTable.PSVersion' }
$source = $ast.Extent.Text
$start = $version.Extent.StartOffset - $ast.Extent.StartOffset
$end = $version.Extent.EndOffset - $ast.Extent.StartOffset
$source = $source.Substring(0, $start) + '([Version]"2.0")' + $source.Substring($end)
[IO.File]::WriteAllText($env:APS_TEST_SIMULATED, $source, (New-Object Text.UTF8Encoding($false)))
''', encoding="utf-8-sig")
        built = _run_powershell(builder, APS_TEST_PACKAGE_PS1=str(PACKAGE_PS1), APS_TEST_SIMULATED=str(simulated))
        assert built.returncode == 0, built.stdout + built.stderr

    result = _run_powershell(simulated)
    assert result.returncode == 2, result.stdout + result.stderr
    assert b"Windows PowerShell 5.1 or newer is required" in result.stderr
    assert result.stdout.strip() == b""
    if os.name == "nt":
        for name in ("build_win7_portable.bat", "build_win7_installer.bat"):
            entry = subprocess.run([os.environ["COMSPEC"], "/d", "/c", name], cwd=tmp_path, capture_output=True, timeout=60)
            assert entry.returncode == 2, entry.stdout + entry.stderr
            assert b"Windows PowerShell 5.1 or newer is required" in entry.stdout + entry.stderr


def test_package_pipeline_prepares_browser_before_onedir_and_never_cleans_after_validation() -> None:
    text = PACKAGE_PS1.read_text(encoding="ascii")
    tail = text[text.index("\ntry {\n    if ($MainOnly -and $ChromeOnly) {"):]
    assert "return\n" not in tail  # 主流程只以显式 exit 0 / exit 1 结束
    assert re.findall(r"(?m)^\s*python\s", text) == []
    # 浏览器源先准备好再进 onedir：损坏的 ZIP 不会先让 onedir 删空既有 dist。
    portable = _function_block(text, "function Invoke-PortablePackageBuild")
    assert portable.index("Initialize-OfflineChrome109 $chrome") < portable.index('Invoke-CmdBat "build_win7_onedir.bat"')
    # 冷启动校验只清理它自己创建的数据。其后新出现的数据应由归档拒绝，不可先删再出包。
    after_validation = portable.split("Test-DistExeStartup $distDir", 1)[1]
    assert "Remove-PathWithRetry" not in after_validation
    assert "scripts/portable_release.py archive" in after_validation


def test_setup_stages_sqlite_before_preflight_and_onedir_freezes_with_build_venv() -> None:
    setup = (REPO_ROOT / "setup_win7_build.bat").read_text(encoding="utf-8")
    stage = '".venv-win7-build\\Scripts\\python.exe" scripts\\prepare_win7_offline.py stage-sqlite --venv .venv-win7-build'
    assert setup.index("-r requirements-win7-build.txt") < setup.index(stage) < setup.index("scripts\\check_win7_build.py")

    onedir = (REPO_ROOT / "build_win7_onedir.bat").read_text(encoding="utf-8")
    assert 'set "APS_BUILD_PYTHON=%CD%\\.venv-win7-build\\Scripts\\python.exe"' in onedir
    assert '"%APS_BUILD_PYTHON%" -m PyInstaller ' in onedir
    assert 'scripts\\portable_release.py check-sqlite "dist\\排产系统"' in onedir


@pytest.mark.parametrize("missing", ["sqlite3.dll", "_sqlite3.pyd"])
def test_sqlite_binary_required_by_onedir_and_portable_archive(tmp_path, missing):
    from scripts import portable_release

    payload = tmp_path / "payload"
    for name in portable_release.REQUIRED_FILES:
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"payload")
    target = payload / missing
    target.unlink()
    target.mkdir()
    with pytest.raises(ValueError, match=re.escape(missing)):
        portable_release.require_payload_files(payload, portable_release.SQLITE_BINARIES)
    target.rmdir()
    target.touch()
    with pytest.raises(ValueError, match=re.escape(missing)):
        portable_release.write_portable_archive(payload, tmp_path / "out.zip")


def test_prepare_portable_directory_writes_bom_docs_and_rejects_links(tmp_path: Path) -> None:
    from core.infrastructure.safe_files import UnsafeFixedFileError
    from scripts import portable_release

    payload = tmp_path / "payload"
    for name in portable_release.REQUIRED_FILES:
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"payload")
    portable_release.prepare_portable_directory(payload)
    # Win7 记事本靠 BOM 认中文说明、靠 CRLF 换行；标记文件保持纯 ASCII、无 BOM。
    for name in (portable_release.README, portable_release.ACCEPTANCE):
        source = (REPO_ROOT / "assets" / name).read_text(encoding="utf-8")
        raw = (payload / name).read_bytes()
        assert raw == b"\xef\xbb\xbf" + source.replace("\n", "\r\n").encode("utf-8")
        assert raw.count(b"\r\n") == raw.count(b"\n") > 0
    assert (payload / portable_release.MARKER).read_bytes() == b"APS portable directory, format 1. Do not remove this file.\n"

    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside the package")
    readme = payload / portable_release.README
    readme.unlink()
    os.link(str(outside), str(readme))
    with pytest.raises(UnsafeFixedFileError):
        portable_release.prepare_portable_directory(payload)
    assert outside.read_bytes() == b"outside the package"
    readme.unlink()
    if os.name != "nt":
        marker = payload / portable_release.MARKER
        marker.unlink()
        marker.symlink_to(outside)
        with pytest.raises(UnsafeFixedFileError):
            portable_release.prepare_portable_directory(payload)
        assert outside.read_bytes() == b"outside the package"


@pytest.mark.skipif(os.name != "nt", reason="Requires cmd.exe and Windows PowerShell")
@pytest.mark.parametrize(("entry_name", "main_only"), [("build_win7_portable.bat", False), ("build_win7_installer.bat", True)])
def test_build_entries_delegate_to_package_script_and_preserve_its_exit_code(tmp_path, entry_name, main_only):
    entry = tmp_path / entry_name
    entry.write_bytes((REPO_ROOT / entry_name).read_bytes())
    script = tmp_path / PACKAGE_PS1.relative_to(REPO_ROOT)
    script.parent.mkdir(parents=True)
    mode = script.parent / "mode.txt"
    script.write_text(
        "param([switch]$MainOnly)\n"
        "[IO.File]::WriteAllText($env:APS_TEST_MODE_FILE, [string]$MainOnly.IsPresent)\n"
        "exit 7\n",
        encoding="ascii",
    )

    def run(*arguments):
        return subprocess.run(
            [os.environ["COMSPEC"], "/d", "/c", entry.name, *arguments], cwd=tmp_path,
            env=dict(os.environ, ERRORLEVEL="0", APS_TEST_MODE_FILE=str(mode)), capture_output=True, timeout=30,
        )

    result = run()
    assert result.returncode == 7, result.stdout + result.stderr
    assert mode.read_text() == str(main_only)
    mode.unlink()
    rejected = run("extra")
    assert rejected.returncode == 2, rejected.stdout + rejected.stderr
    assert not mode.exists()

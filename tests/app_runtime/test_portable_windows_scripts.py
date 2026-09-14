"""Static Windows contracts plus an actual PowerShell parser check on Windows."""
from __future__ import annotations

import os
import subprocess

import pytest

from tests._support.paths import REPO_ROOT

PACKAGE = REPO_ROOT / ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
LAUNCHER = REPO_ROOT / "assets/启动_排产系统_Chrome.bat"


def test_powershell51_source_and_native_output_encodings_are_explicit():
    text = PACKAGE.read_bytes().decode("ascii")
    assert text.startswith("#Requires -Version 5.1\n")
    assert "[Console]::InputEncoding = $utf8NoBom" in text
    assert "[Console]::OutputEncoding = $utf8NoBom" in text
    assert "$OutputEncoding = $utf8NoBom" in text
    assert '$env:PYTHONIOENCODING = "utf-8"' in text
    assert "-Encoding utf8NoBOM" not in text
    assert "-Parallel" not in text


def test_browser_smoke_quotes_paths_and_covers_nonascii_spaces():
    text = PACKAGE.read_text(encoding="ascii")
    assert '--directory "{1}"' in text
    assert '--user-data-dir="{0}"' in text
    assert '"aps chrome smoke " + $unicodeProbe' in text


def test_default_build_validates_portable_before_requiring_inno():
    text = PACKAGE.read_text(encoding="ascii")
    dispatch = text[text.index("$repoRoot = Resolve-RepoRoot"):]
    assert dispatch.index("Invoke-PortablePackageBuild") < dispatch.index("$iscc = Resolve-Iscc")
    build = text[text.index("function Invoke-PortablePackageBuild"):text.index("function Invoke-ChromeRuntimeBuild")]
    assert build.index("prepare") < build.index("Test-DistExeStartup") < build.index("archive")
    assert build.index("Invoke-ChromeRuntimeSmoke") < build.index("archive")
    assert build.index('Join-Path $distDir "user-data"') < build.index("archive")


def test_portable_launcher_skips_installed_paths_and_uses_local_profile():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'if exist "%APP_DIR%\\aps-portable.txt" set "PORTABLE=1"' in text
    assert text.index("call :configure_portable_data") < text.index("call :resolve_shared_data_root")
    assert text.index("goto :CHROME_RESOLVED") < text.index("call :read_machine_registry_chrome_dir")
    assert 'set "CHROME_PROFILE_DIR=%APP_DIR%\\user-data\\chrome109_profile"' in text
    assert 'set "CHROME_EXE=%APP_DIR%\\tools\\chrome109\\chrome.exe"' in text
    for name, suffix in (("APS_DB_PATH", "db\\aps.db"), ("APS_LOG_DIR", "logs"),
                         ("APS_BACKUP_DIR", "backups"), ("APS_EXCEL_TEMPLATE_DIR", "templates_excel")):
        assert 'set "' + name + '=%APP_DIR%\\user-data\\' + suffix + '"' in text


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 is unavailable on this host")
def test_windows_powershell51_parses_real_packaging_script():
    env = dict(os.environ, APS_PACKAGE_SCRIPT=str(PACKAGE))
    script = (
        "if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { exit 51 }; "
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile($env:APS_PACKAGE_SCRIPT,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")

"""Fail before deleting build/dist when the Win7 build environment is incomplete."""
from __future__ import annotations

import ctypes
import json
import os
import platform
import struct
import subprocess
import sys
from ctypes import wintypes
from importlib import metadata
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_VENV_NAME = ".venv-win7-build"


def dependency_errors(entries: list) -> list:
    errors = []
    for entry in entries:
        if not entry["path"].startswith("wheels/"):
            continue
        try:
            installed = metadata.version(entry["name"])
        except metadata.PackageNotFoundError:
            installed = "missing"
        if installed != entry["version"]:
            errors.append("{name}: expected {version}, found {installed}".format(installed=installed, **entry))
    return errors


def vendor_wheel_errors(repo_root: Path = REPO_ROOT) -> list:
    wheels_dir = repo_root / "vendor" / "wheels"
    if not list(wheels_dir.glob("networkx-3.1-*.whl")):
        return ["vendor/wheels/networkx-3.1-*.whl: missing offline wheel"]
    return []


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def build_interpreter_errors(repo_root: Path, prefix: Path, base_prefix: Path, extension: Path, library: Path) -> list:
    """The interpreter PyInstaller freezes must be the repository build venv that loads the staged JSON1 SQLite."""
    if _same_path(prefix, base_prefix):
        return ["Build must run inside an isolated venv (setup_win7_build.bat), not base Python: " + str(prefix)]
    errors = []
    build_venv = repo_root / BUILD_VENV_NAME
    if not _same_path(prefix, build_venv):
        errors.append(f"Build interpreter is not the repository build venv {build_venv}: {prefix}")
    dlls_dir = prefix / "DLLs"
    for loaded, name in ((extension, "_sqlite3.pyd"), (library, "sqlite3.dll")):
        if not _same_path(loaded, dlls_dir / name):
            errors.append(f"{name} is loaded from {loaded}, expected {dlls_dir}; run setup_win7_build.bat")
    return errors


def _loaded_module_path(name: str) -> Path:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    kernel32.GetModuleFileNameW.restype = wintypes.DWORD
    handle = kernel32.GetModuleHandleW(name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel32.GetModuleFileNameW(handle, buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(buffer.value)


def sqlite_runtime_errors(repo_root: Path = REPO_ROOT) -> list:
    """Run the product JSON1 probe in this interpreter; on Windows also prove which SQLite binaries it loaded."""
    try:
        # A missing DLL or an unsupported SQLite version belongs in the same
        # preflight diagnostic as a failed JSON1 query.
        import _sqlite3

        from core.infrastructure.sqlite_udf import ensure_sqlite_runtime

        ensure_sqlite_runtime()
    except (ImportError, RuntimeError) as exc:
        return [f"SQLite runtime unavailable: {exc}"]
    if sys.platform != "win32":
        return []
    try:
        library = _loaded_module_path("sqlite3.dll")
    except OSError as exc:
        return [f"Could not inspect loaded sqlite3.dll: {exc}"]
    return build_interpreter_errors(
        repo_root, Path(sys.prefix), Path(sys.base_prefix), Path(_sqlite3.__file__), library
    )


def main() -> int:
    errors = []
    if sys.platform != "win32" or platform.release() != "7":
        errors.append("Build on Windows 7 SP1 x64; this host is " + platform.platform())
    elif sys.getwindowsversion().service_pack_major < 1:
        errors.append("Windows 7 SP1 is required")
    if sys.version_info[:2] != (3, 8) or struct.calcsize("P") != 8:
        errors.append("CPython 3.8 x64 is required")
    manifest = json.loads((REPO_ROOT / "packaging/win7/offline-manifest.json").read_text(encoding="utf-8"))
    errors.extend(dependency_errors(manifest["files"]))
    errors.extend(vendor_wheel_errors(REPO_ROOT))
    errors.extend(sqlite_runtime_errors(REPO_ROOT))
    if errors:
        for error in errors:
            print("[preflight] " + error)
        print("[preflight] Run setup_win7_build.bat using the verified offline kit; build/dist are untouched.")
        return 1
    return subprocess.call([sys.executable, "-m", "pip", "check"])


if __name__ == "__main__":
    raise SystemExit(main())

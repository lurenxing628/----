"""Fail before deleting build/dist when the Win7 build environment is incomplete."""
from __future__ import annotations

import json
import platform
import struct
import subprocess
import sys
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


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
    if errors:
        for error in errors:
            print("[preflight] " + error)
        print("[preflight] Run setup_win7_build.bat using the verified offline kit; build/dist are untouched.")
        return 1
    return subprocess.call([sys.executable, "-m", "pip", "check"])


if __name__ == "__main__":
    raise SystemExit(main())

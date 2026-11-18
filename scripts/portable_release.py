"""Prepare and archive a fresh Win7 portable payload; never package user data."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, List

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.infrastructure.safe_files import open_fixed_file_for_write_binary

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKER = "aps-portable.txt"
LAUNCHER = "启动_排产系统_Chrome.bat"
README = "README_PORTABLE.txt"
ACCEPTANCE = "WIN7_ACCEPTANCE.txt"
ARCHIVE_ROOT = "APS_Portable"
SQLITE_BINARIES = ("_sqlite3.pyd", "sqlite3.dll")
REQUIRED_FILES = (
    "排产系统.exe", "python38.dll", *SQLITE_BINARIES, "base_library.zip", "schema.sql", LAUNCHER, "aps-launcher.ps1",
    "static/workbench/app/workbench.css", "static/workbench/app/main.js",
    "tools/chrome109/chrome.exe", "tools/chrome109/locales/zh-CN.pak",
    "tools/chrome109/locales/en-US.pak",
)
RUNTIME_ROOTS = {"user-data", "db", "logs", "backups", "chrome109_profile"}


def require_payload_files(dist_dir: Path, names: Iterable[str]) -> None:
    for relative in names:
        target = dist_dir / relative
        if target.is_symlink() or not target.is_file() or target.stat().st_size == 0:
            raise ValueError("Missing or empty portable payload: " + relative)


def payload_files(dist_dir: Path) -> List[Path]:
    """Reject incomplete packages and runtime state instead of silently filtering it."""
    require_payload_files(dist_dir, REQUIRED_FILES)
    files = []
    for path in sorted(dist_dir.rglob("*")):
        relative = path.relative_to(dist_dir)
        name = path.name.lower()
        if path.is_symlink():
            raise ValueError("Portable payload contains a symlink: " + str(relative))
        if (relative.parts[0].lower() in RUNTIME_ROOTS
                or name.endswith((".db", ".sqlite", ".sqlite3", ".log", ".lock", ".lock.guard"))
                or ".db-" in name or name.startswith(("aps_runtime.", "aps_secret_key."))
                or relative.as_posix().lower().startswith("tools/chrome109/user data/")
                or relative.as_posix().lower().startswith("tools/chrome109/default/")):
            raise ValueError("Portable payload contains runtime/user data: " + str(relative))
        if path.is_file():
            files.append(path)
    return files


def prepare_portable_directory(dist_dir: Path) -> None:
    """Add the portable instructions and marker; the whole tree is checked once when it is archived."""
    require_payload_files(dist_dir, REQUIRED_FILES)
    # Win7 Notepad needs UTF-8 BOM and CRLF line endings to display the Chinese readme reliably.
    contents = {
        name: (REPO_ROOT / "assets" / name).read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8-sig")
        for name in (README, ACCEPTANCE)
    }
    contents[MARKER] = b"APS portable directory, format 1. Do not remove this file.\n"
    for name, data in contents.items():
        # The fixed-file primitive refuses symlinks, hard links and non-regular files before writing.
        with open_fixed_file_for_write_binary(dist_dir / name, append=False) as stream:
            stream.write(data)


def write_portable_archive(dist_dir: Path, output: Path) -> None:
    dist_dir = dist_dir.resolve()
    output = output.resolve()
    if dist_dir == output or dist_dir in output.parents:
        raise ValueError("ZIP output must be outside the portable payload directory")
    files = payload_files(dist_dir)
    for name in (MARKER, README, ACCEPTANCE):
        if not (dist_dir / name).is_file() or (dist_dir / name).stat().st_size == 0:
            raise ValueError("Portable directory is not prepared: " + name)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="aps_portable_", suffix=".zip", dir=str(output.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(str(temp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(str(path), ARCHIVE_ROOT + "/" + path.relative_to(dist_dir).as_posix())
        with zipfile.ZipFile(str(temp_path)) as archive:
            failed = archive.testzip()
            if failed:
                raise ValueError("Portable ZIP integrity check failed: " + failed)
        os.replace(str(temp_path), str(output))
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check-sqlite", "prepare", "archive"))
    parser.add_argument("dist_dir", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "check-sqlite":
        require_payload_files(args.dist_dir, SQLITE_BINARIES)
    elif args.action == "prepare":
        prepare_portable_directory(args.dist_dir)
    else:
        if args.output is None:
            parser.error("archive requires an output ZIP path")
        write_portable_archive(args.dist_dir, args.output)
        print("[portable] ZIP verified: " + str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

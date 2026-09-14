"""Prepare and archive a fresh Win7 portable payload; never package user data."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKER = "aps-portable.txt"
LAUNCHER = "启动_排产系统_Chrome.bat"
README = "README_PORTABLE.txt"
ARCHIVE_ROOT = "APS_Portable"
REQUIRED_FILES = (
    "排产系统.exe", "python38.dll", "base_library.zip", "schema.sql",
    "static/workbench/prototype/styles.css", "static/workbench/app/main.js",
    "tools/chrome109/chrome.exe", "tools/chrome109/locales/zh-CN.pak",
    "tools/chrome109/locales/en-US.pak",
)
RUNTIME_ROOTS = {"user-data", "db", "logs", "backups", "chrome109_profile"}


def payload_files(dist_dir: Path) -> List[Path]:
    """Reject incomplete packages and runtime state instead of silently filtering it."""
    for relative in REQUIRED_FILES:
        target = dist_dir / relative
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("Missing or empty portable payload: " + relative)
    files = []
    for path in sorted(dist_dir.rglob("*")):
        relative = path.relative_to(dist_dir)
        name = path.name.lower()
        if path.is_symlink():
            raise ValueError("Portable payload contains a symlink: " + str(relative))
        if (relative.parts[0].lower() in RUNTIME_ROOTS
                or name.endswith((".db", ".sqlite", ".sqlite3", ".log", ".lock"))
                or ".db-" in name or name.startswith(("aps_runtime.", "aps_secret_key."))
                or relative.as_posix().lower().startswith("tools/chrome109/user data/")
                or relative.as_posix().lower().startswith("tools/chrome109/default/")):
            raise ValueError("Portable payload contains runtime/user data: " + str(relative))
        if path.is_file():
            files.append(path)
    return files


def prepare_portable_directory(dist_dir: Path) -> None:
    payload_files(dist_dir)
    shutil.copyfile(REPO_ROOT / "assets" / LAUNCHER, dist_dir / LAUNCHER)
    # Win7 Notepad needs a BOM to recognize the Chinese readme reliably.
    readme_text = (REPO_ROOT / "assets" / README).read_text(encoding="utf-8")
    (dist_dir / README).write_text(readme_text, encoding="utf-8-sig")
    (dist_dir / MARKER).write_text("APS portable directory, format 1. Do not remove this file.\n", encoding="ascii")


def write_portable_archive(dist_dir: Path, output: Path) -> str:
    dist_dir = dist_dir.resolve()
    output = output.resolve()
    if dist_dir == output or dist_dir in output.parents:
        raise ValueError("ZIP output must be outside the portable payload directory")
    files = payload_files(dist_dir)
    for name in (MARKER, LAUNCHER, README):
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
        digest = hashlib.sha256()
        with temp_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
        os.replace(str(temp_path), str(output))
        output.with_suffix(output.suffix + ".sha256").write_text(
            checksum + "  " + output.name + "\n", encoding="ascii")
        return checksum
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "archive"))
    parser.add_argument("dist_dir", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare_portable_directory(args.dist_dir)
    else:
        if args.output is None:
            parser.error("archive requires an output ZIP path")
        checksum = write_portable_archive(args.dist_dir, args.output)
        print("[portable] ZIP verified: " + str(args.output))
        print("[portable] SHA-256: " + checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

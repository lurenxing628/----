"""Download or verify the fixed Win7 build kit, and stage its JSON1 SQLite into the build venv.

Files are only downloaded, checked and copied; nothing from the kit is installed or executed.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "packaging/win7/offline-manifest.json"


def load_manifest(path: Path = MANIFEST) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1 or not data.get("files"):
        raise ValueError("Unsupported or empty offline manifest")
    seen = set()
    for entry in data["files"]:
        relative = PurePosixPath(entry["path"])
        if (relative.is_absolute() or ".." in relative.parts or "\\" in entry["path"]
                or ":" in entry["path"] or entry["path"] in seen):
            raise ValueError("Unsafe or duplicate artifact path: " + entry["path"])
        if not entry["url"].startswith("https://") or entry["size"] <= 0:
            raise ValueError("Invalid artifact metadata: " + entry["path"])
        seen.add(entry["path"])
    return data["files"]


def verify_file(path: Path, entry: dict) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing or non-regular artifact: " + str(path))
    if path.stat().st_size != entry["size"]:
        raise ValueError("Size mismatch: " + str(path))


def download_file(path: Path, entry: dict) -> None:
    if path.exists():
        verify_file(path, entry)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="aps-download-", suffix=".part", dir=str(path.parent))
    os.close(fd)
    temporary_path = Path(temporary)
    try:
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "APS-Win7-offline-kit/1"})
        with urllib.request.urlopen(request, timeout=60) as source, temporary_path.open("wb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)
        verify_file(temporary_path, entry)
        os.replace(str(temporary_path), str(path))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def artifact_path(root: Path, entry: dict) -> Path:
    target = root / entry["path"]
    if root not in target.resolve().parents:
        raise ValueError("Artifact escapes output directory: " + str(target))
    return target


def prepare(action: str, output: Path, entries: list) -> None:
    root = output.resolve()
    for entry in entries:
        target = artifact_path(root, entry)
        if action == "download":
            download_file(target, entry)
        else:
            verify_file(target, entry)
        print("[offline] 文件就绪，尺寸符合清单：" + entry["path"], flush=True)


SQLITE_ENTRY_NAME = "SQLite DLL"
SQLITE_PTH_LINE = 'import os, sys; sys.path.insert(0, os.path.join(sys.prefix, "DLLs"))\n'


def _write_atomic(target: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix="aps-stage-", suffix=".part", dir=str(target.parent))
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(str(temporary_path), str(target))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _venv_home(venv_dir: Path) -> Path:
    config = venv_dir / "pyvenv.cfg"
    if not config.is_file() or config.is_symlink():
        raise ValueError("Missing or non-regular build venv config: " + str(config))
    for line in config.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "home":
            return Path(value.strip())
    raise ValueError("Build venv config has no home entry: " + str(config))


def stage_sqlite(offline_root: Path, venv_dir: Path, entries: list) -> None:
    """Put the kit's JSON1 sqlite3.dll beside a copy of the base _sqlite3.pyd in <venv>/DLLs and load them first."""
    matches = [entry for entry in entries if entry["name"] == SQLITE_ENTRY_NAME]
    if len(matches) != 1:
        raise ValueError("Offline manifest must list exactly one " + SQLITE_ENTRY_NAME + " entry")
    archive = artifact_path(offline_root.resolve(), matches[0])
    verify_file(archive, matches[0])
    venv_dir = venv_dir.resolve()
    base_home = _venv_home(venv_dir).resolve()
    if venv_dir == base_home:
        raise ValueError("Build venv must be separate from base Python: " + str(venv_dir))
    base_pyd = base_home / "DLLs" / "_sqlite3.pyd"
    if not base_pyd.is_file() or base_pyd.stat().st_size == 0:
        raise ValueError("Base interpreter has no _sqlite3.pyd: " + str(base_pyd))
    dlls_dir = venv_dir / "DLLs"
    site_packages = venv_dir / "Lib" / "site-packages"
    # Check both destinations before writing either; a junction in Lib can redirect site-packages too.
    for directory in (dlls_dir, site_packages):
        if directory.resolve() != directory:
            raise ValueError("Build venv directory is redirected: " + str(directory))
    if not site_packages.is_dir():
        raise ValueError("Build venv has no Lib/site-packages: " + str(site_packages))
    with zipfile.ZipFile(str(archive)) as bundle:
        library = bundle.read("sqlite3.dll")
    if not library:
        raise ValueError("Empty sqlite3.dll inside " + str(archive))
    dlls_dir.mkdir(exist_ok=True)
    _write_atomic(dlls_dir / "sqlite3.dll", library)
    _write_atomic(dlls_dir / "_sqlite3.pyd", base_pyd.read_bytes())
    _write_atomic(site_packages / "_win7_sqlite.pth", SQLITE_PTH_LINE.encode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("download", "verify", "stage-sqlite"))
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "offline/win7")
    parser.add_argument("--venv", type=Path, default=REPO_ROOT / ".venv-win7-build")
    args = parser.parse_args()
    if args.action == "stage-sqlite":
        stage_sqlite(args.output, args.venv, load_manifest())
        print("[offline] JSON1 SQLite 已装配到构建环境：" + str(args.venv / "DLLs"))
        return 0
    prepare(args.action, args.output, load_manifest())
    print("[offline] 文件齐全且尺寸符合清单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Download or verify the fixed Win7 build kit; never install or execute its files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
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
        if (not entry["url"].startswith("https://") or len(entry["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in entry["sha256"]) or entry["size"] <= 0):
            raise ValueError("Invalid artifact metadata: " + entry["path"])
        seen.add(entry["path"])
    return data["files"]


def verify_file(path: Path, entry: dict) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing or non-regular artifact: " + str(path))
    if path.stat().st_size != entry["size"]:
        raise ValueError("Size mismatch: " + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != entry["sha256"]:
        raise ValueError("SHA-256 mismatch: " + str(path))


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


def prepare(action: str, output: Path, entries: list) -> None:
    root = output.resolve()
    for entry in entries:
        target = root / entry["path"]
        if root not in target.resolve().parents:
            raise ValueError("Artifact escapes output directory: " + str(target))
        if action == "download":
            download_file(target, entry)
        else:
            verify_file(target, entry)
        print("[offline] verified " + entry["path"], flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("download", "verify"))
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "offline/win7")
    args = parser.parse_args()
    prepare(args.action, args.output, load_manifest())
    print("[offline] All artifacts verified. Windows execution still requires real-machine validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

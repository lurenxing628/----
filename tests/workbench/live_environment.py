"""Fresh paths and process isolation for workbench browser tests; stdlib only."""

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
READY_PREFIX = "WB_LIVE_READY "


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def create_root(parent=None):
    root = Path(tempfile.mkdtemp(prefix="aps-workbench-live-", dir=parent)).resolve()
    for name in ("db", "logs", "backups", "templates_excel", "tmp", "home", "screenshots", "downloads", "static", "templates"):
        (root / name).mkdir()
    write_json(root / "isolation.json", {"schema_version": 1, "kind": "workbench-live-fixture",
                                        "root": str(root), "nonce": uuid.uuid4().hex})
    return root


def read_identity(root):
    root = Path(root).resolve()
    identity = json.loads((root / "isolation.json").read_text(encoding="utf-8"))
    if identity.get("kind") != "workbench-live-fixture" or identity.get("root") != str(root):
        raise ValueError("Not a freshly created workbench fixture root")
    return identity


def environment(root):
    root = Path(root).resolve()
    identity = read_identity(root)
    env = {key: value for key, value in os.environ.items() if not key.startswith("APS_")}
    env.pop("WERKZEUG_RUN_MAIN", None)
    env.update({"APS_ENV": "development", "APS_DB_PATH": str(root / "db/aps-live.db"),
                "APS_LOG_DIR": str(root / "logs"), "APS_BACKUP_DIR": str(root / "backups"),
                "APS_EXCEL_TEMPLATE_DIR": str(root / "templates_excel"),
                "SECRET_KEY": "isolated-browser-only-" + identity["nonce"],
                "TMPDIR": str(root / "tmp"), "TMP": str(root / "tmp"), "TEMP": str(root / "tmp"),
                "HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
                "XDG_CACHE_HOME": str(root / "home/.cache"),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
    return env


def check_assets():
    path = REPO / "static/workbench/asset-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("target") != "chrome109":
        raise ValueError("Expected a chrome109 workbench asset manifest")
    for item in manifest["files"]:
        data = (REPO / "static" / item["path"]).read_bytes()
        if sha256(data) != item["sha256"] or len(data) != item["bytes"]:
            raise ValueError("Built asset differs from manifest: " + item["path"])
    for item in manifest.get("inputs", []):
        if item["path"].startswith("frontend/workbench/app/"):
            if sha256((REPO / item["path"]).read_bytes()) != item["sha256"]:
                raise ValueError("Live assets are stale; ask the main task to rebuild: " + item["path"])
    return {"path": str(path), "sha256": sha256(path.read_bytes()), "build_id": manifest["build_id"]}


def freeze_assets(root):
    evidence = check_assets()
    source = Path(evidence["path"])
    manifest = json.loads(source.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        target = root / "static" / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(REPO / "static" / item["path"]), str(target))
        if sha256(target.read_bytes()) != item["sha256"]:
            raise ValueError("Assets changed during freeze; retry after the main task rebuilds")
    shutil.copyfile(str(source), str(root / "static/workbench/asset-manifest.json"))
    if sha256(source.read_bytes()) != evidence["sha256"]:
        raise ValueError("Asset manifest changed during freeze")
    shutil.copytree(str(REPO / "templates/workbench"), str(root / "templates/workbench"))
    evidence["frozen_manifest"] = str(root / "static/workbench/asset-manifest.json")
    evidence["template_hashes"] = {str(file.relative_to(root)): sha256(file.read_bytes())
                                  for file in sorted((root / "templates/workbench").rglob("*")) if file.is_file()}
    return evidence


def install_path_guard(root):
    """Reject every non-isolated SQLite connection and server-side filesystem write."""
    import sqlite3
    import sys
    from urllib.parse import unquote, urlsplit

    root = Path(root).resolve()
    evidence = {"sqlite_connections": [], "violations": []}

    def require_inside(value, event):
        if isinstance(value, int) or value is None:
            return
        file = Path(os.fsdecode(value)).resolve()
        try:
            file.relative_to(root)
        except ValueError:
            evidence["violations"].append({"event": event, "path": str(file)})
            raise PermissionError(f"Isolation guard rejected {event}: {file}")

    def audit(event, args):
        if event == "sqlite3.connect":
            value = os.fsdecode(args[0])
            if value == ":memory:":
                evidence["sqlite_connections"].append(value)
                return
            file = unquote(urlsplit(value).path) if value.startswith("file:") else value
            require_inside(file, event)
            evidence["sqlite_connections"].append(str(Path(file).resolve()))
        elif event == "open":
            mode, flags = args[1], args[2]
            writing = bool(isinstance(mode, str) and any(char in mode for char in "wax+"))
            writing = writing or bool(isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing:
                require_inside(args[0], event)
        elif event in ("os.mkdir", "os.remove", "os.rmdir"):
            require_inside(args[0], event)
        elif event in ("os.rename", "os.link", "os.symlink"):
            require_inside(args[0], event)
            require_inside(args[1], event)

    sys.addaudithook(audit)
    original_connect = sqlite3.connect

    def checked_connect(database, *args, **kwargs):
        audit("sqlite3.connect", (database,))
        return original_connect(database, *args, **kwargs)

    # Python 3.8 does not expose all newer sqlite audit events. Forward to the real driver.
    sqlite3.connect = checked_connect
    return evidence


def file_snapshot(root):
    return {str(file.relative_to(root)): sha256(file.read_bytes())
            for directory in (root / "backups", root / "templates_excel")
            for file in sorted(directory.rglob("*")) if file.is_file()}

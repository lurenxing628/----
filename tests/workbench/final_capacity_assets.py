"""Freeze a Main-built artifact without rebuilding or changing global static files."""

import hashlib
import json
import shutil
from pathlib import Path

from tests.workbench.live_environment import REPO, sha256
from tests.workbench.run_live_server_support import inside, tree_hashes


def freeze_named_assets(root, session, *, asset_root, manifest_sha256):
    asset_root = Path(asset_root).resolve()
    manifest_path = asset_root / "asset-manifest.json"
    raw = manifest_path.read_bytes()
    if sha256(raw) != manifest_sha256:
        raise ValueError("The Main build manifest changed after capacity admission")
    manifest = json.loads(raw)
    if manifest.get("schema_version") != 1 or manifest.get("target") != "chrome109":
        raise ValueError("Expected the complete chrome109 build manifest")
    records = manifest["files"]
    if not records or len({item["path"] for item in records}) != len(records):
        raise ValueError("Build file list is empty or contains duplicate paths")
    frozen = root / "frozen" / session
    static = frozen / "static"
    for item in records:
        source = inside(asset_root, asset_root.parent / item["path"])
        target = inside(static, static / item["path"])
        data = source.read_bytes()
        if sha256(data) != item["sha256"] or len(data) != item["bytes"]:
            raise ValueError("Main build file does not match manifest: " + item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (static / "workbench/asset-manifest.json").write_bytes(raw)
    shutil.copytree(str(REPO / "templates/workbench"), str(frozen / "templates/workbench"))
    if manifest_path.read_bytes() != raw:
        raise ValueError("Main build manifest changed during freeze")
    stale = [item["path"] for item in manifest["inputs"] if not inside(REPO, REPO / item["path"]).is_file()
             or sha256((REPO / item["path"]).read_bytes()) != item["sha256"]]
    return {"build_id": manifest["build_id"], "sha256": hashlib.sha256(raw).hexdigest(),
            "frozen_manifest": str(static / "workbench/asset-manifest.json"),
            "static": str(static), "templates": str(frozen / "templates"), "root": str(frozen),
            "hashes": tree_hashes(frozen), "source_differences": stale,
            "main_asset_root": str(asset_root), "verified_file_count": len(records), "verified_input_count": len(manifest["inputs"])}

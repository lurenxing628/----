"""Read the built workspace entry manifest; never serve an incomplete entry."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional


class WorkbenchAssetsUnavailable(RuntimeError):
    pass


def _entry_paths(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("target") != "chrome109":
        raise WorkbenchAssetsUnavailable("页面文件版本不对，页面没有打开。请联系维护人员重新安装本机程序。")
    paths = []
    for key in ("styles", "scripts"):
        value = manifest.get(key)
        if not isinstance(value, list) or not value:
            raise WorkbenchAssetsUnavailable("页面文件清单不完整，页面没有打开。请联系维护人员重新安装本机程序。")
        paths.extend(value)
    theme_script = manifest.get("theme_script")
    paths.append(theme_script)
    if manifest.get("icon") is not None:
        paths.append(manifest["icon"])
    if any(not isinstance(value, str) for value in paths):
        raise WorkbenchAssetsUnavailable("页面文件登记有误，页面没有打开。请联系维护人员重新安装本机程序。")
    if len(paths) != len(set(paths)):
        raise WorkbenchAssetsUnavailable("页面文件重复登记，页面没有打开。请联系维护人员重新安装本机程序。")
    return paths


def _validate_file(root: Path, value: str) -> None:
    relative = PurePosixPath(value)
    invalid = (not value.startswith("workbench/") or value != relative.as_posix() or "\\" in value
               or ".." in relative.parts or "?" in value or "#" in value)
    if invalid:
        raise WorkbenchAssetsUnavailable("页面文件不在本机安装位置内，页面没有打开。请联系维护人员重新安装本机程序。")
    target = root / str(relative)
    try:
        target.resolve().relative_to((root / "workbench").resolve())
    except ValueError as exc:
        raise WorkbenchAssetsUnavailable("页面文件位置超出本机安装位置，页面没有打开。请联系维护人员重新安装本机程序。") from exc
    if not target.is_file():
        raise WorkbenchAssetsUnavailable("页面文件缺失，页面没有打开。请联系维护人员重新安装本机程序。")


def read_asset_manifest(static_root: Optional[str]) -> Dict[str, Any]:
    if not static_root:
        raise WorkbenchAssetsUnavailable("本机程序没有设置页面文件位置，页面没有打开。请联系维护人员检查安装。")
    root = Path(static_root)
    try:
        manifest = json.loads((root / "workbench" / "asset-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkbenchAssetsUnavailable("页面文件清单读不到，页面没有打开。请联系维护人员重新安装本机程序。") from exc
    paths = _entry_paths(manifest)
    for value in paths:
        _validate_file(root, value)
    return manifest

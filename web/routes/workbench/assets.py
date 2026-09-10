"""Read the built workspace entry manifest; never serve an incomplete entry."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional


class WorkbenchAssetsUnavailable(RuntimeError):
    pass


def _entry_paths(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("target") != "chrome109":
        raise WorkbenchAssetsUnavailable("工作台资源清单版本不匹配。")
    paths = []
    for key in ("styles", "scripts"):
        value = manifest.get(key)
        if not isinstance(value, list) or not value:
            raise WorkbenchAssetsUnavailable("工作台资源清单不完整。")
        paths.extend(value)
    theme_script = manifest.get("theme_script")
    paths.append(theme_script)
    if manifest.get("icon") is not None:
        paths.append(manifest["icon"])
    if any(not isinstance(value, str) for value in paths):
        raise WorkbenchAssetsUnavailable("工作台资源路径无效。")
    if len(paths) != len(set(paths)):
        raise WorkbenchAssetsUnavailable("工作台资源重复登记。")
    return paths


def _validate_file(root: Path, value: str) -> None:
    relative = PurePosixPath(value)
    invalid = (not value.startswith("workbench/") or value != relative.as_posix() or "\\" in value
               or ".." in relative.parts or "?" in value or "#" in value)
    if invalid:
        raise WorkbenchAssetsUnavailable("工作台资源路径不在交付目录内。")
    target = root / str(relative)
    try:
        target.resolve().relative_to((root / "workbench").resolve())
    except ValueError as exc:
        raise WorkbenchAssetsUnavailable("工作台资源路径越界。") from exc
    if not target.is_file():
        raise WorkbenchAssetsUnavailable("工作台资源文件缺失，请重新构建资源。")


def read_asset_manifest(static_root: Optional[str]) -> Dict[str, Any]:
    if not static_root:
        raise WorkbenchAssetsUnavailable("工作台静态资源目录未配置。")
    root = Path(static_root)
    try:
        manifest = json.loads((root / "workbench" / "asset-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkbenchAssetsUnavailable("工作台资源清单尚未生成或无法读取。") from exc
    paths = _entry_paths(manifest)
    for value in paths:
        _validate_file(root, value)
    return manifest

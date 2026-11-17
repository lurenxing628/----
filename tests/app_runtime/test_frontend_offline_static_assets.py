"""交付资源离线自包含检查。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from tests._support.paths import REPO_ROOT

# 随包交付的网页资源根，来源 build_win7_onedir.bat:45-46。
DELIVERED_WEB_ROOTS = (
    REPO_ROOT / "templates",
    REPO_ROOT / "static",
)

FRONTEND_SUFFIXES = {".html", ".css", ".js", ".md"}

EXTERNAL_RESOURCE_PATTERNS = [
    re.compile(r"<script\b[^>]*\bsrc\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE),
    re.compile(r"<link\b[^>]*\bhref\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE),
    re.compile(r"<(?:img|source|video|audio|track|iframe|embed)\b[^>]*\bsrc\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE),
    re.compile(r"<object\b[^>]*\bdata\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE),
    re.compile(r"<(?:img|source)\b[^>]*\bsrcset\s*=\s*(?:['\"][^'\"]*(?:https?:)?//|[^>\s]*(?:https?:)?//)", re.IGNORECASE),
    re.compile(r"@import\s+url\(\s*['\"]?https?://", re.IGNORECASE),
    re.compile(r"@import\s+url\(\s*['\"]?//", re.IGNORECASE),
    re.compile(r"@import\s+['\"]https?://", re.IGNORECASE),
    re.compile(r"@import\s+['\"]//", re.IGNORECASE),
    re.compile(r"\bimport\s*\(\s*['\"]https?://", re.IGNORECASE),
    re.compile(r"\bimport\s*\(\s*['\"]//", re.IGNORECASE),
    re.compile(r"\bimport\b[\s\S]{0,400}?\bfrom\s*['\"]https?://", re.IGNORECASE),
    re.compile(r"\bimport\b[\s\S]{0,400}?\bfrom\s*['\"]//", re.IGNORECASE),
    re.compile(r"\bimport\s*['\"]https?://", re.IGNORECASE),
    re.compile(r"\bimport\s*['\"]//", re.IGNORECASE),
    re.compile(r"@font-face[\s\S]{0,400}?url\(\s*['\"]?https?://", re.IGNORECASE),
    re.compile(r"@font-face[\s\S]{0,400}?url\(\s*['\"]?//", re.IGNORECASE),
    re.compile(r"\burl\(\s*['\"]?(?:https?:)?//", re.IGNORECASE),
]

CDN_MARKERS = [
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "unpkg.com",
    "stackpath.bootstrapcdn.com",
    "maxcdn.bootstrapcdn.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
]


def _frontend_files() -> List[Path]:
    return [
        path
        for root in DELIVERED_WEB_ROOTS
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in FRONTEND_SUFFIXES
    ]


def _line_no(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _collect_external_resource_violations_from_text(rel: str, text: str) -> List[str]:
    violations: List[str] = []
    lower = text.lower()

    for pattern in EXTERNAL_RESOURCE_PATTERNS:
        for match in pattern.finditer(text):
            violations.append(f"{rel}:{_line_no(text, match.start())}: 前端资源不能使用外链脚本、样式或字体")

    for marker in CDN_MARKERS:
        index = lower.find(marker)
        if index >= 0:
            violations.append(f"{rel}:{_line_no(text, index)}: 前端资源不能引用 CDN 或外链字体域名 {marker}")

    return violations


def _collect_external_resource_violations() -> List[str]:
    violations: List[str] = []
    for path in _frontend_files():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        violations.extend(_collect_external_resource_violations_from_text(str(rel), text))

    return violations


def test_frontend_static_assets_are_offline_local() -> None:
    violations = _collect_external_resource_violations()
    assert not violations, "\n".join(violations)


def test_workbench_entry_has_few_requests_and_all_bundled_css_targets_exist():
    from urllib.parse import unquote, urlsplit

    from scripts.workbench.asset_sources import css_references

    static = REPO_ROOT / "static"
    manifest = json.loads((static / "workbench/asset-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["scripts"]) <= 4 and len(manifest["styles"]) <= 2
    for relative in manifest["scripts"] + manifest["styles"] + [manifest["theme_script"], manifest["icon"]]:
        assert (static / relative).is_file(), relative
    for relative in manifest["styles"]:
        sheet = static / relative
        text = sheet.read_text(encoding="utf-8")
        assert not re.search(r"@import\s", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
        for ref in css_references(text):
            target = (sheet.parent / unquote(urlsplit(ref).path)).resolve()
            assert static.resolve() in target.parents and target.is_file(), ref


def test_style_bundle_preserves_cascade_and_rebases_nested_imports():
    from scripts.workbench.entry_bundle import bundle_styles

    payload = {"workbench/app/styles/base.css": b'@import "./type.css"; .x { color:red; }',
               "workbench/app/styles/type.css": b'@font-face { src: url("../assets/font.ttf"); }',
               "workbench/app/assets/font.ttf": b"font",
               "workbench/app/styles/live.css": b'.x { color:blue; background:url("data:image/png;base64,AA=="); }'}
    result = bundle_styles(payload, ["workbench/app/styles/base.css", "workbench/app/styles/live.css"],
                           "workbench/app/workbench.css").decode()
    assert '@import' not in result
    assert 'url("assets/font.ttf")' in result
    assert result.index('color:red') < result.index('color:blue')
    assert 'url("data:image/png;base64,AA==")' in result

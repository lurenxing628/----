"""回归测试：前端与用户可见文档必须离线自包含——扫描 templates/static/docs 等资源，禁止外链 script/link/img/srcset/@import/@font-face 及 CDN 域名（jsdelivr、cdnjs、unpkg、googleapis 等），
并校验用户可见文档不出现 plan_role、scenario_id 等内部字段与草稿措辞；UTF-8 严格读取遇坏字节抛 UnicodeDecodeError。"""

from __future__ import annotations

import re
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Set

import pytest

from tests._support.paths import REPO_ROOT

FRONTEND_ROOTS = [
    REPO_ROOT / "templates",
    REPO_ROOT / "static",
    REPO_ROOT / "web_new_test" / "templates",
    REPO_ROOT / "web_new_test" / "static",
]

FRONTEND_SUFFIXES = {".html", ".css", ".js", ".md"}
WORKBENCH_MOCKUP = REPO_ROOT / "docs" / "aps_frontend_workbench_mockup.html"
USER_VISIBLE_DOC_ROOTS = [
    REPO_ROOT / "docs",
    REPO_ROOT / "static" / "docs",
    REPO_ROOT / "web_new_test" / "static" / "docs",
]
USER_VISIBLE_DOC_EXCLUDED_DIRS = {
    (REPO_ROOT / "docs" / "dev").resolve(),
}
GENERATED_USER_VISIBLE_DOC_GLOBS = (
    "docs/_panorama_data/**",
    "docs/*全景图*.html",
    "docs/*演进时间线.html",
    "docs/**/*全景图*.html",
    "docs/**/*演进时间线.html",
    "docs/v2/panorama.css",
    "docs/v2/panorama.js",
)

USER_VISIBLE_INTERNAL_TERMS = [
    "plan_role",
    "scenario_id",
    "source_table",
    "candidate_id",
    "event_type",
    "ReasonCode",
    "score tuple",
    "score_tuple",
    "PlanIdentity",
    "EvidenceLink",
    "ExecutionEvent",
    "ExecutionState",
    "OperationExecutionEvents",
    "OperationExecutionState",
    "state_revision",
    "dirty_fields",
]

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


def _frontend_files() -> Iterable[Path]:
    seen: Set[Path] = set()
    for root in FRONTEND_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in FRONTEND_SUFFIXES:
                seen.add(path)
                yield path
    for root in USER_VISIBLE_DOC_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in FRONTEND_SUFFIXES:
                continue
            resolved_parent = path.parent.resolve()
            if any(excluded == resolved_parent or excluded in resolved_parent.parents for excluded in USER_VISIBLE_DOC_EXCLUDED_DIRS):
                continue
            if _is_generated_user_visible_doc(path):
                continue
            if path not in seen:
                seen.add(path)
                yield path
    if WORKBENCH_MOCKUP.exists() and WORKBENCH_MOCKUP not in seen:
        yield WORKBENCH_MOCKUP


def _line_no(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _is_generated_user_visible_doc(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    return any(fnmatch(rel, pattern) for pattern in GENERATED_USER_VISIBLE_DOC_GLOBS)


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


def _user_visible_text_files() -> Iterable[Path]:
    seen: Set[Path] = set()
    for root in USER_VISIBLE_DOC_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".html", ".md"}:
                continue
            resolved_parent = path.parent.resolve()
            if any(excluded == resolved_parent or excluded in resolved_parent.parents for excluded in USER_VISIBLE_DOC_EXCLUDED_DIRS):
                continue
            if _is_generated_user_visible_doc(path):
                continue
            if path not in seen:
                seen.add(path)
                yield path
    for path in (REPO_ROOT / "web" / "viewmodels").glob("page_manuals_*.py"):
        if path not in seen:
            seen.add(path)
            yield path


def test_frontend_static_assets_are_offline_local() -> None:
    violations = _collect_external_resource_violations()
    assert not violations, "\n".join(violations)


def test_external_resource_patterns_cover_remote_images_srcset_and_css_url() -> None:
    samples = [
        '<script src=https://assets.example/a.js></script>',
        "<link href=//assets.example/a.css rel=stylesheet>",
        '<img src="https://assets.example/a.png">',
        "<img src=https://assets.example/a.png>",
        '<img srcset="/local.png 1x, https://assets.example/a@2x.png 2x">',
        '<source srcset="//assets.example/a.webp 1x">',
        '<object data="https://assets.example/a.pdf"></object>',
        '.hero { background-image: url("https://assets.example/a.png"); }',
        ".hero { background-image: url(//assets.example/a.png); }",
    ]

    for index, sample in enumerate(samples, start=1):
        violations = _collect_external_resource_violations_from_text(f"sample-{index}.html", sample)
        assert violations == [f"sample-{index}.html:1: 前端资源不能使用外链脚本、样式或字体"]


def test_frontend_static_asset_scan_reads_utf8_strictly(tmp_path, monkeypatch) -> None:
    bad_file = tmp_path / "bad.html"
    bad_file.write_bytes(b"\xff")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_frontend_files", lambda: [bad_file])

    with pytest.raises(UnicodeDecodeError):
        _collect_external_resource_violations()


def test_user_visible_docs_do_not_use_internal_or_draft_terms() -> None:
    violations: List[str] = []
    forbidden_terms = tuple(USER_VISIBLE_INTERNAL_TERMS)
    for path in _user_visible_text_files():
        rel = str(path.relative_to(REPO_ROOT))
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            index = text.find(term)
            if index >= 0:
                violations.append(f"{rel}:{_line_no(text, index)}: 用户可见说明不能出现 {term}")

    assert not violations, "\n".join(violations)

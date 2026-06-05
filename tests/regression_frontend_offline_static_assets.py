from __future__ import annotations

import re
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Set

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

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

WORKBENCH_MOCKUP_FORBIDDEN_TEXT = [
    "异常解释",
    "异常必须解释",
    "异常批次列表",
    "第一卡点",
    "主要原因",
    "业务主方案",
    "基线方案",
    "最终推荐",
    "评分",
    "参考分",
    "row.score_label",
    "看影响清单",
    "预计恢复",
    "计划 vs 实际",
    "对照基线",
    "基线",
    "设备故障",
    "换型等待",
    "缺料",
    "影响交期",
    "已停工",
    "物料未齐",
    "先看卡点",
    "卡在 M-03",
    "暂停 / 异常",
    "按钮应优先显示“完工 / 暂停 / 报异常”",
    "示例：暂停",
    "示例：继续生产",
    "示例：报异常",
    "异常上报",
    "暂停后可继续",
    "后续：报异常",
    "后续异常反馈",
    "后续再补异常反馈",
    "车间待开工 / 暂停 / 完工",
    "开工 / 暂停 / 完工",
    "当前阶段不展示暂停或继续生产按钮",
    "查看偏差",
    "后续复盘视图",
    "分析复盘",
    "风险复盘入口",
]

USER_VISIBLE_LEGACY_DRAFT_TEXT = [
    "第一版",
    "后续版本再补",
    "如果进入正式实现",
    "后续开放",
    "静态 HTML 原型",
    "设计讨论材料",
    "当前阶段",
    "第一阶段",
    "后续再补",
]

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

WORKBENCH_MOCKUP_FORBIDDEN_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?h\b", re.IGNORECASE),
    re.compile(r"\b\d+h\d+m\b", re.IGNORECASE),
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


def test_workbench_mockup_uses_plain_language_for_users() -> None:
    text = WORKBENCH_MOCKUP.read_text(encoding="utf-8")

    violations = [
        forbidden
        for forbidden in WORKBENCH_MOCKUP_FORBIDDEN_TEXT
        if forbidden in text
    ]
    for pattern in WORKBENCH_MOCKUP_FORBIDDEN_PATTERNS:
        violations.extend(match.group(0) for match in pattern.finditer(text))

    assert not violations, "原型页面仍有不适合直接给用户看的旧词：" + "、".join(violations)


def test_user_visible_docs_do_not_use_internal_or_draft_terms() -> None:
    violations: List[str] = []
    forbidden_terms = tuple(USER_VISIBLE_LEGACY_DRAFT_TEXT + USER_VISIBLE_INTERNAL_TERMS)
    for path in _user_visible_text_files():
        rel = str(path.relative_to(REPO_ROOT))
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            index = text.find(term)
            if index >= 0:
                violations.append(f"{rel}:{_line_no(text, index)}: 用户可见说明不能出现 {term}")

    assert not violations, "\n".join(violations)

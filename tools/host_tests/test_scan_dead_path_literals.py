from __future__ import annotations

import pytest

from tools.scan_dead_path_literals import EXISTENCE_FILE_SCOPES, is_repo_path_literal
from tools.test_registry import scope_matches_path


@pytest.mark.parametrize("literal", [
    ".codestable/checkup/baseline.json",
    ".limcode/skills/example/SKILL.md",
    "docs/panorama.css",
    "docs/panorama.js",
    "docs/v2/panorama.css",
    "docs/v2/panorama.js",
])
def test_local_only_paths_are_not_candidates(literal):
    # pre-push runs this scanner in a clean worktree where these local-only paths never exist.
    assert not is_repo_path_literal(literal)


@pytest.mark.parametrize("literal", [".github/workflows/quality.yml", "tools/scan_dead_path_literals.py"])
def test_tracked_top_level_paths_stay_candidates(literal):
    assert is_repo_path_literal(literal)


@pytest.mark.parametrize("literal", [
    ".github/workflows/quality.yml",
    "tools/scan_dead_path_literals.py",
    "开发文档/README.md",
    "frontend/workbench/app/nested/main.jsx",
    "templates_excel/sample.xlsx",
])
def test_candidate_literals_fall_in_declared_existence_scopes(literal):
    # 门禁规格把 EXISTENCE_FILE_SCOPES 登记为只看存在性的输入：扫描器会核对存在性的路径必须都在其中，
    # 增删这些文件时日常门禁才会触发本扫描、完整门禁的指纹才会变化。
    assert is_repo_path_literal(literal)
    assert any(scope_matches_path(literal, scope) for scope in EXISTENCE_FILE_SCOPES)

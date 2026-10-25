from __future__ import annotations

import pytest

from tools.scan_dead_path_literals import is_repo_path_literal


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

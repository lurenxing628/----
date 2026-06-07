from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests._support.paths import REPO_ROOT

SEARCH_TOOL = REPO_ROOT / ".codestable" / "tools" / "search-yaml.py"
VALIDATE_TOOL = REPO_ROOT / ".codestable" / "tools" / "validate-yaml.py"


def _run_tool(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_architecture_entrypoint_is_valid_and_slug_searchable() -> None:
    architecture_dir = REPO_ROOT / ".codestable" / "architecture"
    validate = _run_tool(
        VALIDATE_TOOL,
        "--dir",
        str(architecture_dir),
        "--require",
        "doc_type",
        "--require",
        "slug",
        "--require",
        "status",
        "--json",
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr

    search = _run_tool(
        SEARCH_TOOL,
        "--dir",
        str(architecture_dir),
        "--filter",
        "doc_type=architecture",
        "--filter",
        "slug=ARCHITECTURE",
        "--json",
    )
    assert search.returncode == 0, search.stdout + search.stderr
    assert "ARCHITECTURE.md" in search.stdout


def test_roadmap_related_architecture_slugs_are_searchable() -> None:
    for related_slug in ("ARCHITECTURE", "ui-gantt"):
        proc = _run_tool(
            SEARCH_TOOL,
            "--dir",
            str(REPO_ROOT / ".codestable" / "roadmap"),
            "--filter",
            "doc_type=roadmap",
            "--filter",
            f"related_architecture~={related_slug}",
            "--json",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "aps-three-gap-directions-roadmap.md" in proc.stdout

        architecture = _run_tool(
            SEARCH_TOOL,
            "--dir",
            str(REPO_ROOT / ".codestable" / "architecture"),
            "--filter",
            "doc_type=architecture",
            "--filter",
            f"slug={related_slug}",
            "--json",
        )
        assert architecture.returncode == 0, architecture.stdout + architecture.stderr
        assert ".md" in architecture.stdout

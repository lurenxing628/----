from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCH_TOOL = REPO_ROOT / "codestable" / "tools" / "search-yaml.py"
VALIDATE_TOOL = REPO_ROOT / "codestable" / "tools" / "validate-yaml.py"


def _run_tool(script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _env_without_pyyaml(shadow_dir: Path) -> dict:
    shadow_dir.mkdir()
    (shadow_dir / "yaml.py").write_text("raise ImportError('PyYAML hidden for fallback test')\n", encoding="utf-8")
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(shadow_dir) if not existing else str(shadow_dir) + os.pathsep + existing
    return env


def test_codestable_tools_start_under_current_python_runtime() -> None:
    for script in [SEARCH_TOOL, VALIDATE_TOOL]:
        proc = _run_tool(script, "--help")
        assert proc.returncode == 0, proc.stdout + proc.stderr


def test_search_yaml_rejects_bad_frontmatter_instead_of_fallback_parsing(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "bad.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: learning
            tags: [broken
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(SEARCH_TOOL, "--dir", str(docs_dir), "--query", "body")

    assert proc.returncode == 1
    assert "YAML syntax error" in proc.stderr or "Malformed inline YAML list" in proc.stderr


def test_search_yaml_rejects_unclosed_frontmatter(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "bad.md").write_text("---\ndoc_type: learning\nbody\n", encoding="utf-8")

    proc = _run_tool(SEARCH_TOOL, "--dir", str(docs_dir), "--query", "body")

    assert proc.returncode == 1
    assert "No closing" in proc.stderr


def test_search_yaml_rejects_non_line_frontmatter_delimiter(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "bad.md").write_text("---oops\ndoc_type: learning\n---\nbody\n", encoding="utf-8")

    proc = _run_tool(SEARCH_TOOL, "--dir", str(docs_dir), "--query", "body")

    assert proc.returncode == 1
    assert "Opening delimiter" in proc.stderr


def test_search_yaml_builtin_fallback_reads_block_list_filters(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "decision.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: decision
            tags:
              - codestable
              - quality-gate
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        SEARCH_TOOL,
        "--dir",
        str(docs_dir),
        "--filter",
        "tags~=codestable",
        "--json",
        env=_env_without_pyyaml(tmp_path / "shadow-search"),
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "decision.md" in proc.stdout
    assert "codestable" in proc.stdout


def test_search_yaml_rejects_empty_filter_parts(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc.md").write_text(
        textwrap.dedent(
            """
            ---
            status: active
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    for raw_filter in ["=active", "~=active", "status=", "status~="]:
        proc = _run_tool(SEARCH_TOOL, "--dir", str(docs_dir), "--filter", raw_filter)
        assert proc.returncode == 2
        assert "Invalid filter expression" in proc.stderr


def test_search_yaml_skips_markdown_without_frontmatter(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "plain.md").write_text("needle\n", encoding="utf-8")
    (docs_dir / "doc.md").write_text(
        textwrap.dedent(
            """
            ---
            status: active
            ---
            needle
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(SEARCH_TOOL, "--dir", str(docs_dir), "--query", "needle")

    assert proc.returncode == 0
    assert "doc.md" in proc.stdout
    assert "plain.md" not in proc.stdout


def test_search_yaml_json_output_serializes_yaml_dates(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "dated.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: learning
            date: 2026-04-27
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(SEARCH_TOOL, "--dir", str(docs_dir), "--query", "body", "--json")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "2026-04-27" in proc.stdout


def test_validate_yaml_rejects_bad_frontmatter(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(
        textwrap.dedent(
            """
            ---
            doc_type: learning
            tags: [broken
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(VALIDATE_TOOL, "--file", str(doc))

    assert proc.returncode == 1
    assert "YAML syntax error" in proc.stdout


def test_validate_yaml_builtin_fallback_rejects_bad_block_list(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(
        textwrap.dedent(
            """
            ---
            doc_type: learning
            tags:
              - codestable
              broken
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        VALIDATE_TOOL,
        "--file",
        str(doc),
        env=_env_without_pyyaml(tmp_path / "shadow-validate"),
    )

    assert proc.returncode == 1
    assert "Unsupported nested YAML" in proc.stdout


def test_validate_yaml_builtin_fallback_requires_pyyaml_for_yaml_files(tmp_path: Path) -> None:
    checklist = tmp_path / "feature-checklist.yaml"
    checklist.write_text(
        textwrap.dedent(
            """
            steps:
              - id: implement
                status: done
            checks:
              - pytest
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        VALIDATE_TOOL,
        "--file",
        str(checklist),
        "--yaml-only",
        env=_env_without_pyyaml(tmp_path / "shadow-yaml"),
    )

    assert proc.returncode == 1
    assert "PyYAML is required to validate pure YAML files" in proc.stdout


def test_validate_yaml_builtin_fallback_rejects_unclosed_quote(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(
        textwrap.dedent(
            """
            ---
            doc_type: learning
            title: "unterminated
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        VALIDATE_TOOL,
        "--file",
        str(doc),
        env=_env_without_pyyaml(tmp_path / "shadow-quote-validate"),
    )

    assert proc.returncode == 1
    assert "Unterminated quoted scalar" in proc.stdout


def test_search_yaml_builtin_fallback_rejects_unclosed_quote(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "bad.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: learning
            title: "unterminated
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        SEARCH_TOOL,
        "--dir",
        str(docs_dir),
        "--query",
        "body",
        "--json",
        env=_env_without_pyyaml(tmp_path / "shadow-quote-search"),
    )

    assert proc.returncode == 1
    assert "Unterminated quoted scalar" in proc.stderr
    assert "bad.md" in proc.stderr


def test_validate_yaml_rejects_non_line_frontmatter_delimiter(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text("---oops\ndoc_type: learning\n---\nbody\n", encoding="utf-8")

    proc = _run_tool(VALIDATE_TOOL, "--file", str(doc))

    assert proc.returncode == 1
    assert "No opening" in proc.stdout


def test_validate_yaml_directory_required_fields_apply_to_markdown_only(tmp_path: Path) -> None:
    docs_dir = tmp_path / "feature"
    docs_dir.mkdir()
    (docs_dir / "feature-design.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: feature-design
            status: approved
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (docs_dir / "feature-checklist.yaml").write_text(
        textwrap.dedent(
            """
            steps:
              - id: implement
                status: done
            checks:
              - pytest
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(VALIDATE_TOOL, "--dir", str(docs_dir), "--require", "doc_type", "--require", "status")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "2 passed, 0 failed" in proc.stdout

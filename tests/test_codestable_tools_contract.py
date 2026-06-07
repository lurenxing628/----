"""测试：.codestable/tools 下 search-yaml.py 与 validate-yaml.py CLI 契约——两工具能在当前 Python 启动；validate 支持 --exclude-dir/--exclude-file（按扫描相对路径）排除草稿、排空全部文件时退出码 2、对 md/yaml 分别应用必填字段；search 支持 frontmatter 过滤（~=/=）、JSON 输出序列化 YAML 日期、跳过无 frontmatter 的 md；两工具对坏/未闭合/非整行分隔符的 frontmatter 报错而非回退，且在无 PyYAML 时走内建 fallback 仍能解析 block-list 并拒绝非法嵌套/未闭合引号；并核验 .codestable 实仓文档的 superseded-by 连字符字段与 issue fix-note/roadmap 关联字段可被检索。"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCH_TOOL = REPO_ROOT / ".codestable" / "tools" / "search-yaml.py"
VALIDATE_TOOL = REPO_ROOT / ".codestable" / "tools" / "validate-yaml.py"


def _run_tool(script: Path, *args: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
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


def test_validate_yaml_can_exclude_draft_dirs_from_required_field_checks(tmp_path: Path) -> None:
    roadmap_dir = tmp_path / "roadmap"
    draft_dir = roadmap_dir / "drafts"
    draft_dir.mkdir(parents=True)
    (roadmap_dir / "formal.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: roadmap
            status: draft
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (draft_dir / "scratch.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: roadmap-draft
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    failing = _run_tool(VALIDATE_TOOL, "--dir", str(roadmap_dir), "--require", "status")
    passing = _run_tool(VALIDATE_TOOL, "--dir", str(roadmap_dir), "--require", "status", "--exclude-dir", "drafts")

    assert failing.returncode == 1
    assert "scratch.md" in failing.stdout
    assert passing.returncode == 0, passing.stdout + passing.stderr
    assert "scratch.md" not in passing.stdout
    assert "formal.md" in passing.stdout


def test_validate_yaml_can_exclude_dir_by_scan_relative_path(tmp_path: Path) -> None:
    root_dir = tmp_path / "roadmap"
    draft_dir = root_dir / "feature-a" / "drafts"
    draft_dir.mkdir(parents=True)
    (root_dir / "feature-a" / "formal.md").write_text(
        textwrap.dedent(
            """
            ---
            status: draft
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (draft_dir / "scratch.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: scratch
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        VALIDATE_TOOL,
        "--dir",
        str(root_dir),
        "--require",
        "status",
        "--exclude-dir",
        "feature-a/drafts",
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "feature-a/drafts/scratch.md" not in proc.stdout
    assert "feature-a/formal.md" in proc.stdout


def test_validate_yaml_fails_clearly_when_excludes_remove_all_files(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "scratch.md").write_text(
        textwrap.dedent(
            """
            ---
            status: draft
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(VALIDATE_TOOL, "--dir", str(docs_dir), "--exclude-file", "scratch.md")

    assert proc.returncode == 2
    assert "No .md or .yaml files left after excludes" in proc.stderr


def test_validate_yaml_can_exclude_index_file_from_required_field_checks(tmp_path: Path) -> None:
    docs_dir = tmp_path / "requirements"
    docs_dir.mkdir()
    (docs_dir / "VISION.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: requirements-index
            last_reviewed: 2026-05-26
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (docs_dir / "capability.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: requirement
            status: draft
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(VALIDATE_TOOL, "--dir", str(docs_dir), "--require", "status", "--exclude-file", "VISION.md")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VISION.md" not in proc.stdout
    assert "capability.md" in proc.stdout


def test_compound_superseded_documents_use_hyphenated_field(tmp_path: Path) -> None:
    docs_dir = tmp_path / "compound"
    docs_dir.mkdir()
    (docs_dir / "superseded.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: explore
            status: superseded
            superseded-by: roadmap-target
            ---
            body
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (docs_dir / "active.md").write_text(
        textwrap.dedent(
            """
            ---
            doc_type: explore
            status: active
            ---
            body roadmap-target
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        SEARCH_TOOL,
        "--dir",
        str(docs_dir),
        "--filter",
        "superseded-by~=roadmap-target",
        "--json",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "superseded.md" in proc.stdout
    assert "active.md" not in proc.stdout


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


def test_validate_yaml_directory_yaml_required_fields_are_explicit(tmp_path: Path) -> None:
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
            """
        ).lstrip(),
        encoding="utf-8",
    )

    proc = _run_tool(
        VALIDATE_TOOL,
        "--dir",
        str(docs_dir),
        "--require",
        "doc_type",
        "--require-yaml",
        "checks",
    )

    assert proc.returncode == 1
    assert "feature-checklist.yaml" in proc.stdout
    assert "Missing required field: 'checks'" in proc.stdout

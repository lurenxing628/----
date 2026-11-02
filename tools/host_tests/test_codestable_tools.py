"""Host tests for CodeStable YAML frontmatter and validation tools."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYED_TOOLS_DIR = REPO_ROOT / ".codestable" / "tools"
TEMPLATE_TOOLS_DIR = REPO_ROOT / ".limcode" / "skills" / "cs-onboard" / "tools"
MANAGED_TOOL_FILES = ("_yaml_frontmatter.py", "search-yaml.py", "validate-yaml.py")

if str(DEPLOYED_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOYED_TOOLS_DIR))

import _yaml_frontmatter as frontmatter_mod  # noqa: E402


class CodeStableToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.tools_dir = self.root / "isolated_tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        for name in MANAGED_TOOL_FILES:
            shutil.copy2(DEPLOYED_TOOLS_DIR / name, self.tools_dir / name)

    def _run_tool(self, script_name: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.tools_dir / script_name), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_managed_three_files_are_byte_identical_between_template_and_deployed(self) -> None:
        for name in MANAGED_TOOL_FILES:
            deployed_path = DEPLOYED_TOOLS_DIR / name
            template_path = TEMPLATE_TOOLS_DIR / name
            self.assertTrue(deployed_path.is_file(), f"Missing deployed tool: {deployed_path}")
            self.assertTrue(template_path.is_file(), f"Missing template tool: {template_path}")
            deployed_bytes = deployed_path.read_bytes()
            self.assertEqual(
                deployed_bytes,
                template_path.read_bytes(),
                f"Template and deployed copies drifted for {name}",
            )

    def test_delimiters_and_pyyaml_fail_closed_contracts(self) -> None:
        with self.assertRaisesRegex(frontmatter_mod.FrontmatterError, "opening"):
            frontmatter_mod.parse_markdown_frontmatter("---oops\ntitle: bad\n---\nbody\n")

        with self.assertRaisesRegex(frontmatter_mod.FrontmatterError, "closing"):
            frontmatter_mod.parse_markdown_frontmatter("---\ntitle: unclosed\nbody\n")

        # Inline '---' in frontmatter values and horizontal rules in body must not confuse delimiter matching
        meta, body = frontmatter_mod.parse_markdown_frontmatter(
            '---\ntitle: "alpha --- beta"\nsummary: gamma --- delta\n---\nParagraph 1\n\n---\n\nParagraph 2\n'
        )
        self.assertEqual(meta, {"title": "alpha --- beta", "summary": "gamma --- delta"})
        self.assertEqual(body, "Paragraph 1\n\n---\n\nParagraph 2")

        # Markdown without frontmatter (even with horizontal rule in body) returns (None, text)
        plain_text = "# Heading\n\nSome text\n\n---\n\nMore text\n"
        plain_meta, plain_body = frontmatter_mod.parse_markdown_frontmatter(plain_text)
        self.assertIsNone(plain_meta)
        self.assertEqual(plain_body, plain_text)

        # PyYAML syntax errors and non-mapping top-level values fail closed without fallback
        with self.assertRaisesRegex(frontmatter_mod.FrontmatterError, "YAML syntax error"):
            frontmatter_mod.parse_markdown_frontmatter("---\nstatus: [broken\n---\nbody\n")
        with self.assertRaisesRegex(frontmatter_mod.FrontmatterError, "Expected a mapping"):
            frontmatter_mod.parse_markdown_frontmatter("---\n- a\n- b\n---\nbody\n")

    def test_builtin_fallback_parser_preserves_none_lists_and_quoted_commas(self) -> None:
        with patch.object(frontmatter_mod, "_yaml_module", None):
            self.assertFalse(frontmatter_mod.has_pyyaml())
            meta, body = frontmatter_mod.parse_markdown_frontmatter(
                "---\n"
                "empty_field:\n"
                "indented_list:\n"
                "  - first\n"
                "  - 'second, item'\n"
                "flat_list:\n"
                "- alpha\n"
                "- beta\n"
                'inline_list: [a, b, "c, d", \'e, f\']\n'
                "flag: true\n"
                "---\n"
                "Body content\n"
            )
            self.assertEqual(
                meta,
                {
                    "empty_field": None,
                    "indented_list": ["first", "second, item"],
                    "flat_list": ["alpha", "beta"],
                    "inline_list": ["a", "b", "c, d", "e, f"],
                    "flag": True,
                },
            )
            self.assertEqual(body, "Body content")

            # Pure YAML must be rejected when PyYAML is unavailable
            with self.assertRaisesRegex(frontmatter_mod.FrontmatterError, "PyYAML is required"):
                frontmatter_mod.parse_yaml_mapping("steps:\n  - name: build\n", allow_builtin_fallback=False)

    def test_search_yaml_skips_plain_markdown_rejects_empty_filters_and_serializes_dates(self) -> None:
        docs_dir = self.root / "docs"
        (docs_dir / "nested").mkdir(parents=True, exist_ok=True)
        (docs_dir / "README.md").write_text("# Plain README without frontmatter\n\n---\nFooter\n", encoding="utf-8")
        (docs_dir / "nested" / "note.md").write_text(
            "---\n"
            "doc_type: learning\n"
            "date: 2026-07-15\n"
            'tags: [aps, " comma, tag "]\n'
            "---\n"
            "Body with keyword shadow-db.\n",
            encoding="utf-8",
        )

        # JSON output with date serialization and POSIX relative path
        ok_proc = self._run_tool("search-yaml.py", "--dir", str(docs_dir), "--filter", "doc_type=learning", "--json")
        self.assertEqual(ok_proc.returncode, 0, ok_proc.stderr)
        rows = json.loads(ok_proc.stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file"], "nested/note.md")
        self.assertEqual(rows[0]["meta"]["date"], "2026-07-15")

        # 0 matches in --json mode still outputs valid JSON []
        empty_proc = self._run_tool("search-yaml.py", "--dir", str(docs_dir), "--filter", "doc_type=missing", "--json")
        self.assertEqual(empty_proc.returncode, 0, empty_proc.stderr)
        self.assertEqual(json.loads(empty_proc.stdout), [])

        # Empty filters must be rejected with non-zero exit code
        for bad_filter in ("=", "doc_type=", "=learning", "~=", "doc_type~=", "doc_type=|"):
            bad_proc = self._run_tool("search-yaml.py", "--dir", str(docs_dir), "--filter", bad_filter)
            self.assertNotEqual(bad_proc.returncode, 0, f"Filter {bad_filter!r} should have failed")

    def test_validate_yaml_options_empty_required_field_and_posix_paths(self) -> None:
        scan_dir = self.root / "scan"
        (scan_dir / "sub").mkdir(parents=True, exist_ok=True)
        (scan_dir / "drafts").mkdir(parents=True, exist_ok=True)

        (scan_dir / "sub" / "valid.md").write_text(
            "---\ndoc_type: feature-design\nstatus: approved\n---\nValid doc\n",
            encoding="utf-8",
        )
        (scan_dir / "README.md").write_text("# Index without frontmatter\n", encoding="utf-8")
        (scan_dir / "drafts" / "draft.md").write_text("---\ndoc_type: draft\n---\nMissing status\n", encoding="utf-8")
        (scan_dir / "sub" / "items.yaml").write_text("roadmap: r1\nitems:\n  - id: 1\n", encoding="utf-8")

        proc = self._run_tool(
            "validate-yaml.py",
            "--dir",
            str(scan_dir),
            "--require",
            "doc_type",
            "--require",
            "status",
            "--require-yaml",
            "roadmap",
            "--require-yaml",
            "items",
            "--exclude-dir",
            "drafts",
            "--exclude-file",
            "README.md",
            "--json",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["passed"], 2)
        self.assertEqual([r["file"] for r in payload["results"]], ["sub/valid.md", "sub/items.yaml"])

        # Markdown-only mode ignores YAML files
        md_only = self._run_tool(
            "validate-yaml.py",
            "--dir",
            str(scan_dir),
            "--markdown-only",
            "--require",
            "doc_type",
            "--require",
            "status",
            "--exclude-dir",
            "drafts",
            "--exclude-file",
            "README.md",
            "--json",
        )
        self.assertEqual(md_only.returncode, 0, md_only.stderr)
        self.assertEqual([r["file"] for r in json.loads(md_only.stdout)["results"]], ["sub/valid.md"])

        # Bare key: (None) must fail --require check
        empty_req_md = self.root / "empty_req.md"
        empty_req_md.write_text("---\ndoc_type: feature-design\nstatus:\n---\nBody\n", encoding="utf-8")
        fail_proc = self._run_tool(
            "validate-yaml.py",
            "--file",
            str(empty_req_md),
            "--require",
            "doc_type",
            "--require",
            "status",
            "--json",
        )
        self.assertEqual(fail_proc.returncode, 1)
        fail_payload = json.loads(fail_proc.stdout)
        self.assertEqual(fail_payload["failed"], 1)
        self.assertIn("Missing required field: 'status'", fail_payload["results"][0]["errors"])


if __name__ == "__main__":
    unittest.main()

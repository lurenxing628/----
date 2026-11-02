#!/usr/bin/env python3
"""
validate-yaml.py — Validate YAML frontmatter syntax in markdown files or pure YAML files.

Scans markdown files for YAML frontmatter (--- ... ---) and checks:
  1. Frontmatter block is properly delimited (opening and closing ---)
  2. YAML syntax is valid (parseable without errors)
  3. (Optional) Required fields are present (--require / --require-yaml flags)

Designed for AI agent use: structured output, exit code reflects pass/fail.
If PyYAML is unavailable, the builtin parser only supports simple Markdown
frontmatter and fails closed for pure YAML files.

Usage examples:
  # Validate all .md and .yaml/.yml files under .codestable/features
  python .codestable/tools/validate-yaml.py --dir .codestable/features

  # Validate a single file
  python .codestable/tools/validate-yaml.py --file .codestable/features/2026-04-11-auth/auth-design.md

  # Check that required fields exist in Markdown frontmatter
  python .codestable/tools/validate-yaml.py --dir .codestable/features --require doc_type --require status

  # Check that required fields exist in pure YAML files inside a directory
  python .codestable/tools/validate-yaml.py --dir .codestable/features --require-yaml steps

  # Validate only markdown files in a mixed docs directory
  python .codestable/tools/validate-yaml.py --dir docs/api --markdown-only --require doc_type --require status

  # Validate only pure YAML files in a mixed docs directory
  python .codestable/tools/validate-yaml.py --dir docs/api --yaml-only

  # Skip draft folders or specific files when checking required fields
  python .codestable/tools/validate-yaml.py --dir .codestable/roadmap --require status --exclude-dir drafts --exclude-file README.md

  # JSON output for programmatic consumption
  python .codestable/tools/validate-yaml.py --dir docs/api --json

  # Validate the libdoc manifest
  python .codestable/tools/validate-yaml.py --file docs/api/manifest.yaml --yaml-only
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from _yaml_frontmatter import (  # noqa: E402
    FrontmatterError,
    has_pyyaml,
    parse_yaml_mapping,
    split_frontmatter,
)

for _stream in (sys.stdout, sys.stderr):
    if isinstance(_stream, io.TextIOWrapper):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------


class ValidationResult:
    def __init__(self, file_path: str):
        self.file = file_path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.fields: List[str] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"file": self.file, "status": "pass" if self.ok else "fail"}
        if self.errors:
            d["errors"] = self.errors
        if self.warnings:
            d["warnings"] = self.warnings
        if self.fields:
            d["fields"] = self.fields
        return d


def _check_required(
    parsed: Dict[str, Any],
    required_fields: Optional[List[str]],
    result: ValidationResult,
) -> None:
    if not required_fields:
        return
    for field in required_fields:
        if field not in parsed or parsed[field] is None:
            result.errors.append(f"Missing required field: '{field}'")


def _warn_if_builtin(result: ValidationResult) -> None:
    if not has_pyyaml():
        result.warnings.append(
            "PyYAML not installed — using builtin fallback parser "
            "(may miss some syntax errors). Install with: pip install pyyaml"
        )


def _validate_file(
    file_path: Path,
    required_fields: Optional[List[str]],
    base_dir: Optional[Path],
    mode: str,  # "markdown" | "yaml"
) -> ValidationResult:
    display_path = file_path.relative_to(base_dir).as_posix() if base_dir else str(file_path)
    result = ValidationResult(display_path)

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"Cannot read file: {exc}")
        return result

    if mode == "markdown":
        try:
            split = split_frontmatter(text, require_frontmatter=True)
        except FrontmatterError as exc:
            result.errors.append(str(exc))
            return result
        assert split is not None
        yaml_text = split[0]
    else:
        yaml_text = text

    try:
        parsed = parse_yaml_mapping(yaml_text, allow_builtin_fallback=(mode == "markdown"))
    except FrontmatterError as exc:
        err_msg = str(exc)
        if mode == "yaml" and err_msg == "PyYAML is required to validate pure YAML files":
            result.errors.append(err_msg)
        else:
            result.errors.append(err_msg if err_msg.startswith("YAML syntax error:") else f"YAML syntax error: {err_msg}")
        return result

    result.fields = list(parsed.keys())
    _check_required(parsed, required_fields, result)
    _warn_if_builtin(result)
    return result


def validate_markdown_file(
    file_path: Path,
    required_fields: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
) -> ValidationResult:
    """Validate YAML frontmatter in a single markdown file."""
    return _validate_file(file_path, required_fields, base_dir, "markdown")


def validate_yaml_file(
    file_path: Path,
    required_fields: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
) -> ValidationResult:
    """Validate a pure YAML file (not markdown with frontmatter)."""
    return _validate_file(file_path, required_fields, base_dir, "yaml")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_text_results(results: List[ValidationResult]) -> None:
    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed

    print(f"Validated {len(results)} file(s): {passed} passed, {failed} failed.\n")

    for r in results:
        icon = "✓" if r.ok else "✗"
        print(f"  {icon} {r.file}")
        for err in r.errors:
            print(f"      ERROR: {err}")
        for warn in r.warnings:
            print(f"      WARN:  {warn}")

    if failed > 0:
        print(f"\n{failed} file(s) have YAML errors.")
    else:
        print("\nAll files valid.")


def print_json_results(results: List[ValidationResult]) -> None:
    output = {
        "total": len(results),
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "results": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate YAML frontmatter in markdown files or pure YAML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dir", type=str, help="Directory to scan recursively for .md and .yaml/.yml files")
    source.add_argument("--file", type=str, help="Single file to validate")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="FIELD",
        help="Require this field in Markdown frontmatter (repeatable)",
    )
    parser.add_argument(
        "--require-yaml",
        action="append",
        default=[],
        metavar="FIELD",
        help="Require this field in pure YAML files during directory scans (repeatable)",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output results as JSON")
    parser.add_argument(
        "--yaml-only",
        action="store_true",
        help="With --file, treat input as pure YAML. With --dir, validate only .yaml/.yml files.",
    )
    parser.add_argument(
        "--markdown-only",
        action="store_true",
        help="When scanning a directory, validate only .md files and ignore .yaml/.yml files.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        metavar="DIR",
        help="Skip matching directory names or paths relative to the scanned --dir.",
    )
    parser.add_argument(
        "--exclude-file",
        action="append",
        default=[],
        metavar="FILE",
        help="Skip matching file names or paths relative to the scanned --dir.",
    )
    return parser


def _validate_single(
    path_str: str,
    require: List[str],
    require_yaml: List[str],
    yaml_only: bool,
) -> List[ValidationResult]:
    fp = Path(path_str)
    if not fp.exists():
        print(f"Error: File not found: {fp}", file=sys.stderr)
        sys.exit(2)
    if yaml_only or fp.suffix in (".yaml", ".yml"):
        return [validate_yaml_file(fp, require_yaml or require)]
    return [validate_markdown_file(fp, require)]


def _normalize_exclude(value: str) -> str:
    return str(value or "").strip().strip("/\\").replace("\\", "/")


def _is_excluded_path(file_path: Path, base_dir: Path, exclude_dirs: List[str], exclude_files: List[str]) -> bool:
    rel_path = file_path.relative_to(base_dir).as_posix()
    rel_parts = rel_path.split("/")
    parent_path = "/".join(rel_parts[:-1])
    file_name = rel_parts[-1]

    for raw_dir in exclude_dirs:
        excluded = _normalize_exclude(raw_dir)
        if not excluded:
            continue
        if "/" in excluded and (parent_path == excluded or parent_path.startswith(excluded + "/")):
            return True
        if "/" not in excluded and excluded in rel_parts[:-1]:
            return True

    for raw_file in exclude_files:
        excluded = _normalize_exclude(raw_file)
        if not excluded:
            continue
        if "/" in excluded and rel_path == excluded:
            return True
        if "/" not in excluded and file_name == excluded:
            return True
    return False


def _filter_excluded_files(
    files: List[Path],
    base_dir: Path,
    exclude_dirs: List[str],
    exclude_files: List[str],
) -> List[Path]:
    return [fp for fp in files if not _is_excluded_path(fp, base_dir, exclude_dirs, exclude_files)]


def _validate_directory(
    dir_str: str,
    require: List[str],
    require_yaml: List[str],
    exclude_dirs: List[str],
    exclude_files: List[str],
    markdown_only: bool = False,
    yaml_only: bool = False,
) -> List[ValidationResult]:
    dp = Path(dir_str)
    if not dp.is_dir():
        print(f"Error: Directory not found: {dp}", file=sys.stderr)
        sys.exit(2)

    md_files = [] if yaml_only else sorted(dp.rglob("*.md"))
    yaml_files = [] if markdown_only else sorted(dp.rglob("*.yaml")) + sorted(dp.rglob("*.yml"))

    if not md_files and not yaml_files:
        if markdown_only:
            wanted = ".md"
        elif yaml_only:
            wanted = ".yaml"
        else:
            wanted = ".md or .yaml"
        print(f"No {wanted} files found under {dp}", file=sys.stderr)
        sys.exit(2)

    md_files = _filter_excluded_files(md_files, dp, exclude_dirs, exclude_files)
    yaml_files = _filter_excluded_files(yaml_files, dp, exclude_dirs, exclude_files)
    if not md_files and not yaml_files:
        print(f"No .md or .yaml files left after excludes under {dp}", file=sys.stderr)
        sys.exit(2)

    effective_yaml_require = (require_yaml or require) if yaml_only else require_yaml
    results = [validate_markdown_file(md, require, dp) for md in md_files]
    results += [validate_yaml_file(yf, effective_yaml_require, dp) for yf in yaml_files]
    return results


def main() -> None:
    args = _build_parser().parse_args()
    if args.yaml_only and args.markdown_only:
        print("Error: --yaml-only and --markdown-only cannot be used together.", file=sys.stderr)
        sys.exit(2)
    if args.file and args.markdown_only:
        print("Error: --markdown-only can only be used with --dir.", file=sys.stderr)
        sys.exit(2)

    if args.file:
        results = _validate_single(args.file, args.require, args.require_yaml, args.yaml_only)
    else:
        results = _validate_directory(
            args.dir,
            args.require,
            args.require_yaml,
            args.exclude_dir,
            args.exclude_file,
            args.markdown_only,
            args.yaml_only,
        )

    if args.json_output:
        print_json_results(results)
    else:
        print_text_results(results)

    sys.exit(0 if all(r.ok for r in results) else 1)


if __name__ == "__main__":
    main()

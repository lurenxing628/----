#!/usr/bin/env python3
"""
validate-yaml.py — Validate YAML frontmatter syntax in markdown files.

Scans markdown files for YAML frontmatter (--- ... ---) and checks:
  1. Frontmatter block is properly delimited (opening and closing ---)
  2. YAML syntax is valid (parseable without errors)
  3. (Optional) Required fields are present (--require flag)

Designed for AI agent use: structured output, exit code reflects pass/fail,
PyYAML is provided by requirements-dev.txt. If PyYAML is unavailable,
the builtin parser only supports simple Markdown frontmatter and fails
closed for pure YAML files.

Usage examples:
  # Validate all .md files under .codestable/features
  python .codestable/tools/validate-yaml.py --dir .codestable/features

  # Validate a single file
  python .codestable/tools/validate-yaml.py --file .codestable/features/2026-04-11-auth/auth-design.md

  # Check that required fields exist in frontmatter
  python .codestable/tools/validate-yaml.py --dir .codestable/features --require doc_type --require status

  # Check that required fields exist in pure YAML files inside a directory
  python .codestable/tools/validate-yaml.py --dir .codestable/features --require-yaml steps

  # Skip draft folders when checking required fields for formal documents
  python .codestable/tools/validate-yaml.py --dir .codestable/roadmap --require status --exclude-dir drafts

  # JSON output for programmatic consumption
  python .codestable/tools/validate-yaml.py --dir docs/api --json

  # Validate the libdoc manifest
  python .codestable/tools/validate-yaml.py --file docs/api/manifest.yaml --yaml-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Force UTF-8 stdout/stderr on Windows where default codepage (e.g. GBK / cp936)
# can't encode the ✓ / ✗ icons used in text output. Safe no-op on POSIX.
# Streams that aren't a real TextIOWrapper (e.g. captured by pytest, redirected
# through some IDEs) raise io.UnsupportedOperation — a ValueError + OSError
# subclass — and we just leave the original encoding in place.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        try:
            _reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------

_HAS_PYYAML = False
try:
    import yaml  # type: ignore
    _HAS_PYYAML = True
except ImportError:
    pass


def _parse_scalar_value(val: str):
    val = val.strip()
    if (val.startswith("[") and not val.endswith("]")) or (val.endswith("]") and not val.startswith("[")):
        raise ValueError("Malformed inline YAML list")
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1]
        return [_parse_scalar_value(item.strip()) for item in inner.split(",") if item.strip()]
    if not val:
        return ""
    if val[0] in {"'", '"'}:
        if len(val) < 2 or val[-1] != val[0]:
            raise ValueError("Unterminated quoted scalar")
        return val[1:-1]
    if val[-1:] in {"'", '"'}:
        raise ValueError("Unmatched closing quote in scalar")
    return val


def _builtin_parse_yaml(text: str) -> dict:
    """Minimal YAML parser for flat mappings with scalar values and block lists."""
    result: dict = {}
    current_list_key: Optional[str] = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace():
            if stripped.startswith("- "):
                if current_list_key is None:
                    raise ValueError(f"List item without list field at line {line_number}")
                result[current_list_key].append(_parse_scalar_value(stripped[2:]))
                continue
            raise ValueError(f"Unsupported nested YAML at line {line_number}")
        current_list_key = None
        if stripped.startswith("- "):
            raise ValueError(f"List item without list field at line {line_number}")
        if ":" not in stripped:
            raise ValueError(f"Malformed YAML line {line_number}")
        key, _, raw = stripped.partition(":")
        val = raw.strip()
        key = key.strip()
        if not key:
            raise ValueError(f"Empty YAML key at line {line_number}")
        if val == "":
            result[key] = []
            current_list_key = key
        else:
            result[key] = _parse_scalar_value(val)
    return result


def parse_yaml_text(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse a YAML string. Returns (parsed_dict, None) on success,
    or (None, error_message) on failure.
    """
    if _HAS_PYYAML:
        try:
            result = yaml.safe_load(text)
            if result is None:
                return {}, None
            if not isinstance(result, dict):
                return None, f"Expected a mapping, got {type(result).__name__}"
            return result, None
        except yaml.YAMLError as exc:
            return None, str(exc)
    else:
        # Builtin fallback — can only detect gross syntax issues
        try:
            result = _builtin_parse_yaml(text)
            return result, None
        except Exception as exc:
            return None, str(exc)


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------

def extract_frontmatter(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract YAML frontmatter from a markdown file.
    Returns (frontmatter_text, None) on success,
    or (None, error_message) if frontmatter is missing or malformed.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, "No opening '---' delimiter found"

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return None, "No closing '---' delimiter found (frontmatter block not terminated)"

    fm_text = "".join(lines[1:closing_index]).strip()
    if not fm_text:
        return None, "Frontmatter block is empty"

    return fm_text, None


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self, file_path: str):
        self.file = file_path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.fields: List[str] = []  # fields found in frontmatter

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
    parsed: Optional[Dict[str, Any]],
    required_fields: Optional[List[str]],
    result: ValidationResult,
) -> None:
    if not required_fields:
        return
    for field in required_fields:
        if field not in (parsed or {}):
            result.errors.append(f"Missing required field: '{field}'")


def _warn_if_builtin(result: ValidationResult) -> None:
    if not _HAS_PYYAML:
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
    display_path = str(file_path.relative_to(base_dir)) if base_dir else str(file_path)
    result = ValidationResult(display_path)

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"Cannot read file: {exc}")
        return result

    if mode == "markdown":
        yaml_text, extract_err = extract_frontmatter(text)
        if extract_err:
            result.errors.append(extract_err)
            return result
    else:
        yaml_text = text

    if mode == "yaml" and not _HAS_PYYAML:
        result.errors.append("PyYAML is required to validate pure YAML files")
        return result

    assert yaml_text is not None
    parsed, parse_err = parse_yaml_text(yaml_text)
    if parse_err:
        result.errors.append(f"YAML syntax error: {parse_err}")
        return result

    result.fields = list(parsed.keys()) if parsed else []
    _check_required(parsed, required_fields, result)
    _warn_if_builtin(result)
    return result


def validate_markdown_file(file_path, required_fields=None, base_dir=None):
    """Validate YAML frontmatter in a single markdown file."""
    return _validate_file(file_path, required_fields, base_dir, "markdown")


def validate_yaml_file(file_path, required_fields=None, base_dir=None):
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
    source.add_argument("--dir", type=str, help="Directory to scan recursively for .md files")
    source.add_argument("--file", type=str, help="Single file to validate")
    parser.add_argument("--require", action="append", default=[], metavar="FIELD",
                        help="Require this field in Markdown frontmatter (repeatable)")
    parser.add_argument("--require-yaml", action="append", default=[], metavar="FIELD",
                        help="Require this field in pure YAML files during directory scans (repeatable)")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output results as JSON")
    parser.add_argument("--yaml-only", action="store_true",
                        help="Treat input as pure YAML (not markdown with frontmatter). "
                             "Use for .yaml/.yml files like manifest.yaml.")
    parser.add_argument("--exclude-dir", action="append", default=[], metavar="DIR",
                        help="Skip matching directory names or paths relative to the scanned --dir.")
    parser.add_argument("--exclude-file", action="append", default=[], metavar="FILE",
                        help="Skip matching file names or paths relative to the scanned --dir.")
    return parser


def _validate_single(path_str: str, require: List[str], require_yaml: List[str], yaml_only: bool) -> List[ValidationResult]:
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


def _filter_excluded_files(files: List[Path], base_dir: Path, exclude_dirs: List[str], exclude_files: List[str]) -> List[Path]:
    return [fp for fp in files if not _is_excluded_path(fp, base_dir, exclude_dirs, exclude_files)]


def _validate_directory(
    dir_str: str,
    require: List[str],
    require_yaml: List[str],
    exclude_dirs: List[str],
    exclude_files: List[str],
) -> List[ValidationResult]:
    dp = Path(dir_str)
    if not dp.is_dir():
        print(f"Error: Directory not found: {dp}", file=sys.stderr)
        sys.exit(2)

    md_files = sorted(dp.rglob("*.md"))
    yaml_files = sorted(dp.rglob("*.yaml")) + sorted(dp.rglob("*.yml"))

    if not md_files and not yaml_files:
        print(f"No .md or .yaml files found under {dp}", file=sys.stderr)
        sys.exit(2)

    md_files = _filter_excluded_files(md_files, dp, exclude_dirs, exclude_files)
    yaml_files = _filter_excluded_files(yaml_files, dp, exclude_dirs, exclude_files)
    if not md_files and not yaml_files:
        print(f"No .md or .yaml files left after excludes under {dp}", file=sys.stderr)
        sys.exit(2)

    results = [validate_markdown_file(md, require, dp) for md in md_files]
    results += [validate_yaml_file(yf, require_yaml, dp) for yf in yaml_files]
    return results


def main() -> None:
    args = _build_parser().parse_args()

    if args.file:
        results = _validate_single(args.file, args.require, args.require_yaml, args.yaml_only)
    else:
        results = _validate_directory(args.dir, args.require, args.require_yaml, args.exclude_dir, args.exclude_file)

    if args.json_output:
        print_json_results(results)
    else:
        print_text_results(results)

    sys.exit(0 if all(r.ok for r in results) else 1)


if __name__ == "__main__":
    main()

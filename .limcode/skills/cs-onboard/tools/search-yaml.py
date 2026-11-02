#!/usr/bin/env python3
"""
search-yaml.py — Generic YAML-frontmatter search tool for markdown document directories.

Works on any directory of .md files that use YAML frontmatter (--- ... ---).
Designed for AI agent use: fast, structured output. When PyYAML is installed,
full YAML syntax is parsed and invalid frontmatter fails closed; when PyYAML is
missing, the builtin parser handles simple scalar and list frontmatter.
Markdown files without YAML frontmatter are skipped.

Filter syntax (--filter flag, repeatable, AND logic):
  key=value     Exact match on a scalar field (case-insensitive)
  key=a|b       Exact match against any candidate value (OR)
  key~=value    Substring match on a string field, or element-in for list fields
  key~=a|b      Substring/list match against any candidate value (OR)

Usage examples:
  # Search .codestable/compound (learning / trick / decision / explore docs share this dir)
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --filter track=pitfall
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter "doc_type=decision|explore|learning"
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter tags~=prisma
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter status=active --full

  # Full-text search in body + frontmatter values
  python .codestable/tools/search-yaml.py --dir .codestable/compound --query "shadow database"

  # JSON output for AI agent consumption
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --filter track=knowledge --json

  # Sort by a frontmatter date field (works on any ISO-8601 date string, YAML date, or sortable value)
  python .codestable/tools/search-yaml.py --dir docs/api --sort-by last_reviewed --order asc       # oldest API docs first
  python .codestable/tools/search-yaml.py --dir .codestable/compound --sort-by date --order desc   # newest first

  # Works on any non-CodeStable yaml-frontmatter markdown directory too
  python .codestable/tools/search-yaml.py --dir docs/release-notes --filter status=published
  python .codestable/tools/search-yaml.py --dir content/posts --filter tags~=python --query "asyncio"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from _yaml_frontmatter import (  # noqa: E402
    FrontmatterError,
    parse_markdown_frontmatter,
)

# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------


def load_documents(directory: Path) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for md_file in sorted(directory.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[warn] Cannot read {md_file.name}: {exc}", file=sys.stderr)
            continue
        rel_file = md_file.relative_to(directory).as_posix()
        try:
            meta, body = parse_markdown_frontmatter(text)
        except FrontmatterError as exc:
            raise FrontmatterError(f"{rel_file}: {exc}") from exc
        if meta is None:
            continue
        docs.append(
            {
                "file": rel_file,
                "path": str(md_file),
                "meta": meta,
                "body": body,
            }
        )
    return docs


# ---------------------------------------------------------------------------
# Filter parsing and evaluation
# ---------------------------------------------------------------------------


def _split_filter_values(value: str) -> List[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


class Filter:
    """Parsed representation of a single --filter expression."""

    def __init__(self, raw: str):
        if "~=" in raw:
            key, _, value = raw.partition("~=")
            self.key = key.strip()
            self.value = value.strip()
            self.values = _split_filter_values(self.value)
            self.operator = "contains"
        elif "=" in raw:
            key, _, value = raw.partition("=")
            self.key = key.strip()
            self.value = value.strip()
            self.values = _split_filter_values(self.value)
            self.operator = "exact"
        else:
            raise argparse.ArgumentTypeError(
                f"Invalid filter expression {raw!r}. "
                "Use 'key=value' for exact match or 'key~=value' for substring/list-contains match. "
                "Use pipes for OR values, e.g. 'doc_type=decision|explore|learning'."
            )
        if not self.key:
            raise argparse.ArgumentTypeError(f"Invalid filter expression {raw!r}: key cannot be empty.")
        if not self.value or not self.values:
            raise argparse.ArgumentTypeError(f"Invalid filter expression {raw!r}: value cannot be empty.")

    def matches(self, meta: Dict[str, Any]) -> bool:
        field_val = meta.get(self.key)
        if field_val is None:
            return False

        if self.operator == "exact":
            return any(str(field_val).lower() == value.lower() for value in self.values)

        # contains: substring for strings, element-in for lists
        if isinstance(field_val, list):
            return any(
                value.lower() == str(item).lower()
                for value in self.values
                for item in field_val
            )
        return any(value.lower() in str(field_val).lower() for value in self.values)

    def __repr__(self) -> str:
        op = "~=" if self.operator == "contains" else "="
        return f"Filter({self.key}{op}{self.value})"


def _sort_key(doc: Dict[str, Any], field: str) -> str:
    """
    Sort key for --sort-by on docs where `field` is present and non-None.
    Dates (datetime.date / datetime.datetime) and strings are both normalized
    to their string form — ISO 8601 date strings sort the same lexicographically
    as YAML-parsed date objects' isoformat().
    """
    val = doc["meta"][field]
    return val.isoformat() if isinstance(val, (date, datetime)) else str(val)


def doc_matches(doc: Dict[str, Any], filters: List[Filter], query: Optional[str]) -> bool:
    meta = doc["meta"]

    for f in filters:
        if not f.matches(meta):
            return False

    if query:
        needle = query.lower()
        haystack = doc["body"].lower() + " " + " ".join(str(v) for v in meta.values()).lower()
        if needle not in haystack:
            return False

    return True


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _meta_summary(meta: Dict[str, Any]) -> str:
    """One-line summary of frontmatter fields, skipping slug/date for brevity."""
    skip = {"slug"}
    parts = []
    for k, v in meta.items():
        if k in skip:
            continue
        if isinstance(v, list):
            parts.append(f"{k}=[{', '.join(str(i) for i in v)}]")
        else:
            parts.append(f"{k}={v}")
    return "  ".join(parts)


def format_summary(doc: Dict[str, Any]) -> str:
    return f"### {doc['file']}\n{_meta_summary(doc['meta'])}"


def format_full(doc: Dict[str, Any]) -> str:
    return format_summary(doc) + "\n\n" + doc["body"]


def print_text(results: List[Dict[str, Any]], full: bool) -> None:
    print(f"Found {len(results)} document(s).\n")
    sep = "\n" + "─" * 60 + "\n"
    chunks = [format_full(d) if full else format_summary(d) for d in results]
    print(sep.join(chunks))


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def print_json(results: List[Dict[str, Any]], full: bool) -> None:
    output = []
    for doc in results:
        body = doc["body"]
        if not full and len(body) > 400:
            body = body[:400] + "…"
        output.append({"file": doc["file"], "meta": doc["meta"], "body": body})
    print(json.dumps(output, ensure_ascii=False, indent=2, default=_json_default))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generic YAML-frontmatter search across a directory of markdown files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dir",
        metavar="DIR",
        required=True,
        help="Directory of .md files to search.",
    )
    parser.add_argument(
        "--filter",
        "-f",
        metavar="EXPR",
        dest="filters",
        type=Filter,
        action="append",
        default=[],
        help="Frontmatter filter expression. Repeatable (AND logic). "
        "key=value for exact match; key~=value for substring (strings) or element-in (lists). "
        "Use pipes for OR values, e.g. key=a|b.",
    )
    parser.add_argument(
        "--query",
        "-q",
        metavar="TEXT",
        help="Full-text search in document body and frontmatter values.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print full document body instead of just the frontmatter summary.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output results as a JSON array.",
    )
    parser.add_argument(
        "--sort-by",
        metavar="FIELD",
        dest="sort_by",
        help="Sort results by a frontmatter field (e.g. last_reviewed, date, updated_at). "
        "ISO-8601 date strings and YAML-parsed dates both sort correctly. "
        "Docs missing the field are pushed to the end.",
    )
    parser.add_argument(
        "--order",
        choices=("asc", "desc"),
        default="desc",
        help="Sort order when --sort-by is set. Default: desc (newest first).",
    )
    return parser


def _resolve_directory(dir_arg: str) -> Path:
    directory = Path(dir_arg)
    if not directory.exists():
        print(f"[error] Directory not found: {directory}", file=sys.stderr)
        sys.exit(1)
    if not directory.is_dir():
        print(f"[error] Not a directory: {directory}", file=sys.stderr)
        sys.exit(1)
    return directory


def _sort_results(results: List[Dict[str, Any]], sort_by: str, order: str) -> List[Dict[str, Any]]:
    def has_field(d: Dict[str, Any]) -> bool:
        return sort_by in d["meta"] and d["meta"][sort_by] is not None

    present = [d for d in results if has_field(d)]
    missing = [d for d in results if not has_field(d)]
    present.sort(key=lambda d: _sort_key(d, sort_by), reverse=(order == "desc"))
    return present + missing


def main() -> None:
    args = _build_parser().parse_args()
    directory = _resolve_directory(args.dir)

    try:
        docs = load_documents(directory)
    except FrontmatterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
    if not docs:
        if args.as_json:
            print_json([], full=args.full)
        else:
            print(f"No YAML-frontmatter markdown documents found in {directory}")
        return

    results = [d for d in docs if doc_matches(d, args.filters, args.query)]
    if not results:
        if args.as_json:
            print_json([], full=args.full)
        else:
            print("No matching documents found.")
        return

    if args.sort_by:
        results = _sort_results(results, args.sort_by, args.order)

    if args.as_json:
        print_json(results, full=args.full)
    else:
        print_text(results, full=args.full)


if __name__ == "__main__":
    main()

"""Shared YAML frontmatter and mapping parser for CodeStable CLI tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml as _yaml_module  # type: ignore[import-untyped]
except ImportError:
    _yaml_module = None  # type: ignore[assignment]


class FrontmatterError(RuntimeError):
    """Raised when Markdown frontmatter or YAML mapping syntax is invalid."""


def has_pyyaml() -> bool:
    return _yaml_module is not None


def _split_inline_list_items(inner: str) -> List[str]:
    items: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    escape = False
    for ch in inner:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == "\\" and quote == '"':
            buf.append(ch)
            escape = True
            continue
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch in ("[", "]", "{", "}"):
            raise FrontmatterError("Malformed or nested inline YAML collection")
        if ch == ",":
            item = "".join(buf).strip()
            if not item:
                raise FrontmatterError("Empty item in inline YAML list")
            items.append(item)
            buf = []
            continue
        buf.append(ch)
    if quote is not None or escape:
        raise FrontmatterError("Unterminated quoted scalar in inline YAML list")
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    elif items:
        raise FrontmatterError("Trailing comma in inline YAML list")
    return items


def parse_yaml_scalar(val: str) -> Any:
    val = val.strip()
    if (val.startswith("[") and not val.endswith("]")) or (val.endswith("]") and not val.startswith("[")):
        raise FrontmatterError("Malformed inline YAML list")
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [parse_yaml_scalar(item) for item in _split_inline_list_items(inner)]
    if val[:1] in {"'", '"'}:
        if len(val) < 2 or val[-1] != val[0]:
            raise FrontmatterError("Unterminated quoted scalar")
        return val[1:-1]
    if val[-1:] in {"'", '"'}:
        raise FrontmatterError("Unmatched closing quote in scalar")
    lower = val.lower()
    if lower in ("true", "yes"):
        return True
    if lower in ("false", "no"):
        return False
    if lower in ("null", "~", ""):
        return None
    return val


def parse_builtin_yaml_mapping(fm_text: str) -> Dict[str, Any]:
    """Minimal YAML parser for Markdown frontmatter when PyYAML is not installed."""
    meta: Dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for line_number, raw_line in enumerate(fm_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        is_indented = raw_line[:1].isspace()
        if stripped == "-" or stripped.startswith("- "):
            if current_list_key is None:
                raise FrontmatterError(f"List item without list field at line {line_number}")
            existing = meta[current_list_key]
            if existing is None:
                existing = []
                meta[current_list_key] = existing
            item_raw = "" if stripped == "-" else stripped[2:]
            existing.append(parse_yaml_scalar(item_raw))
            continue
        if is_indented:
            raise FrontmatterError(f"Unsupported nested YAML at line {line_number}")
        current_list_key = None
        if ":" not in stripped:
            raise FrontmatterError(f"Malformed YAML line {line_number}")
        key, _, raw = stripped.partition(":")
        key = key.strip()
        if not key:
            raise FrontmatterError(f"Empty YAML key at line {line_number}")
        if raw.strip() == "":
            meta[key] = None
            current_list_key = key
        else:
            meta[key] = parse_yaml_scalar(raw)
    return meta


def split_frontmatter(text: str, *, require_frontmatter: bool = False) -> Optional[Tuple[str, str]]:
    """Split Markdown text into (frontmatter_text, body_text)."""
    lines = text.splitlines(keepends=True)
    if not lines:
        if require_frontmatter:
            raise FrontmatterError("No opening '---' delimiter found")
        return None
    first_stripped = lines[0].strip()
    if first_stripped != "---":
        if lines[0].startswith("---"):
            raise FrontmatterError("No opening '---' delimiter found (opening line must be only '---')")
        if require_frontmatter:
            raise FrontmatterError("No opening '---' delimiter found")
        return None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            fm_text = "".join(lines[1:index]).strip()
            body = "".join(lines[index + 1 :]).strip()
            if require_frontmatter and not fm_text:
                raise FrontmatterError("Frontmatter block is empty")
            return fm_text, body

    raise FrontmatterError("No closing '---' delimiter found (frontmatter block not terminated)")


def parse_yaml_mapping(yaml_text: str, *, allow_builtin_fallback: bool = True) -> Dict[str, Any]:
    """Parse YAML text into a mapping dict, failing closed on syntax errors."""
    if has_pyyaml():
        assert _yaml_module is not None
        try:
            meta = _yaml_module.safe_load(yaml_text)
        except _yaml_module.YAMLError as exc:
            raise FrontmatterError(f"YAML syntax error: {exc}") from exc
        if meta is None:
            return {}
        if not isinstance(meta, dict):
            raise FrontmatterError(f"Expected a mapping, got {type(meta).__name__}")
        return meta

    if not allow_builtin_fallback:
        raise FrontmatterError("PyYAML is required to validate pure YAML files")

    return parse_builtin_yaml_mapping(yaml_text)


def parse_markdown_frontmatter(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Split a Markdown document into (frontmatter_dict_or_None, body_text)."""
    split = split_frontmatter(text, require_frontmatter=False)
    if split is None:
        return None, text
    fm_text, body = split
    if not fm_text:
        return {}, body
    return parse_yaml_mapping(fm_text, allow_builtin_fallback=True), body

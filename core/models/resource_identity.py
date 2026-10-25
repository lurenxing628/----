from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean_repeated_id_prefix(rid: str, name: str) -> str:
    if not rid or not name or not name.startswith(rid):
        return name
    remainder = name[len(rid) :]
    if remainder and remainder[0].isspace():
        return remainder.strip()
    return name


def resource_display_label(resource_id: Any, resource_name: Any) -> str:
    """Name first (without a repeated id prefix), else the id; empty when both are missing."""
    rid = _text(resource_id)
    return _clean_repeated_id_prefix(rid, _text(resource_name)) or rid


__all__ = ["resource_display_label"]

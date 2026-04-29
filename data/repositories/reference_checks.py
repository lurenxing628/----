from __future__ import annotations

import re
from typing import Any

from .base_repo import BaseRepository

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(value: str) -> str:
    text = str(value or "").strip()
    if not _IDENTIFIER_RE.match(text):
        raise ValueError("invalid SQL identifier")
    return text


def exists_value_reference(
    repo: BaseRepository,
    *,
    table: str,
    column: str,
    value: Any,
) -> bool:
    safe_table = _identifier(table)
    safe_column = _identifier(column)
    return (
        repo.fetchvalue(
            f"SELECT 1 FROM {safe_table} WHERE {safe_column} = ? LIMIT 1",
            (value,),
            default=None,
        )
        is not None
    )


def exists_any_nonblank_reference(
    repo: BaseRepository,
    *,
    table: str,
    column: str,
) -> bool:
    safe_table = _identifier(table)
    safe_column = _identifier(column)
    return (
        repo.fetchvalue(
            f"SELECT 1 FROM {safe_table} "
            f"WHERE {safe_column} IS NOT NULL AND TRIM({safe_column}) <> '' LIMIT 1",
            default=None,
        )
        is not None
    )

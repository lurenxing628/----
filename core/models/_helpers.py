from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional, Union


RowLike = Union[sqlite3.Row, Dict[str, Any]]


def as_dict(row: Optional[RowLike]) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


def get(row: Optional[RowLike], key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


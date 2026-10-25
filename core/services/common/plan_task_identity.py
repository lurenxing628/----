from __future__ import annotations

from typing import Any, Mapping


def public_task_id(normalized: Mapping[str, Any]) -> str:
    """Read an assigned public identity; never derive one from a hidden row ID."""
    for key in ("task_id", "public_task_id"):
        value = normalized.get(key)
        if type(value) is str and value:
            return value
    task_ref = normalized.get("task_ref")
    if type(task_ref) is str and task_ref:
        return "task_" + task_ref
    raise ValueError("Plan task identity is missing; load the complete original plan before filtering")

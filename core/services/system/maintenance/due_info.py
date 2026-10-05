"""The shared maintenance callback result, including older two-field callbacks."""

from typing import Any, Tuple, Union

IsDueResult = Union[Tuple[bool, Any], Tuple[bool, Any, str, Any]]


def unpack_due_info(result) -> Tuple[bool, Any, str, Any]:
    if not isinstance(result, tuple):
        return bool(result), None, "missing", None
    due = bool(result[0]) if len(result) >= 1 else False
    last_run = result[1] if len(result) >= 2 else None
    last_run_state = str(result[2]).strip() if len(result) >= 3 else ""
    last_run_raw = result[3] if len(result) >= 4 else None
    if last_run_state not in {"valid", "missing", "invalid"}:
        last_run_state = "missing" if last_run is None else "valid"
    return due, last_run, last_run_state, last_run_raw

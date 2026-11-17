"""Key-set conformance of request objects: one predicate for every "required keys, optional keys, nothing else" rule.

``keys_conform`` only decides the shape; each entry keeps its own error type, status and message. It
neither normalizes nor rejects, so a route, a request model and a navigation reader all ask the same
question and answer it in their own words.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Iterable

if TYPE_CHECKING:
    from typing_extensions import TypeGuard


def keys_conform(value: object, required: Iterable[str], optional: Iterable[str] = ()) -> TypeGuard[Dict[str, Any]]:
    """``value`` is a dict holding every ``required`` key and otherwise only ``optional`` ones."""
    if type(value) is not dict:
        return False
    keys, needed = set(value), set(required)
    return needed <= keys and keys <= needed | set(optional)

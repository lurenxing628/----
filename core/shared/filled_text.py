"""Hand-filled text such as a declared operator or a reason: one predicate for "a non-blank string within a limit".

``is_filled_text`` only decides the form; each entry keeps its own limit, error type, status and message, and
stores ``value.strip()``. The limits are business values of each domain and are not unified here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import TypeGuard


def is_filled_text(value: object, limit: int) -> TypeGuard[str]:
    """``value`` is a string that is not blank, has no NUL character and is at most ``limit`` characters long."""
    return type(value) is str and bool(value.strip()) and "\x00" not in value and len(value) <= limit

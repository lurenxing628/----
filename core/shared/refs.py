"""Permanent entity refs: 48 lowercase hex characters, the form every ref column's CHECK pins.

``is_ref`` only decides the form; each entry keeps its own error type, status and message. Stored ref columns
already carry the CHECK, so their readers do not call it. 32-character receipt and job refs, 64-character cell
keys and composite history entry refs are other forms and stay with their own rules.
"""

from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import TypeGuard

_REF = re.compile(r"[0-9a-f]{48}")


def is_ref(value: object) -> TypeGuard[str]:
    return type(value) is str and _REF.fullmatch(value) is not None


def new_ref() -> str:
    return secrets.token_hex(24)

"""Strict rules for stored factory-local calendar days and ISO timestamps."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_LOCAL_DT_PATTERNS = {
    (False, False): re.compile(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9]):([0-5][0-9])(?:\.([0-9]{1,6}))?\Z"
    ),
    (True, False): re.compile(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}[T ](?:[01][0-9]|2[0-3]):[0-5][0-9]):([0-5][0-9])(?:\.([0-9]{1,6}))?\Z"
    ),
    (False, True): re.compile(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9])(?::([0-5][0-9])(?:\.([0-9]{1,6}))?)?\Z"
    ),
    (True, True): re.compile(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}[T ](?:[01][0-9]|2[0-3]):[0-5][0-9])(?::([0-5][0-9])(?:\.([0-9]{1,6}))?)?\Z"
    ),
}


def stored_day(text: object) -> Optional[date]:
    """The day a stored ``YYYY-MM-DD`` text names exactly, or None for any other value or spelling.

    The shape is matched here rather than left to ``date.fromisoformat``, whose accepted forms widen on
    newer Pythons (``20260520``, ``2026-W21-3``); unpadded, slashed and impossible dates all fall to None.
    """
    if type(text) is not str or _DAY.match(text) is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def stored_date(value: object) -> Optional[str]:
    """Canonical ``YYYY-MM-DD`` text for a stored ``date`` or valid ``YYYY-MM-DD`` ``str``, else None."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and stored_day(value) is not None:
        return value
    return None


def stored_local_iso_datetime(
    text: object,
    *,
    allow_space: bool = False,
    allow_minutes_only: bool = False,
) -> Optional[datetime]:
    """Parse a zero-padded factory-local ISO datetime consistently across Python 3.8..3.14."""
    if type(text) is not str:
        return None
    match = _LOCAL_DT_PATTERNS[bool(allow_space), bool(allow_minutes_only)].match(text)
    if match is None:
        return None
    head, sec, frac = match.groups()
    normalized = f"{head}:{sec}.{frac.ljust(6, '0')}" if frac is not None and len(frac) < 6 else text
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None

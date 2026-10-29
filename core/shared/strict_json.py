"""Strict JSON documents: one reader for request bodies, query or form arguments and stored text.

Duplicate object keys, ``NaN``/``Infinity`` literals and numbers that overflow to infinity are
rejected before any caller sees a value; bytes are decoded as UTF-8 only. Every rejection belongs
to the caller: storage readers raise their own corrupt/inconsistent errors and routes raise their
own ``WorkbenchCommandRejected`` texts. Hooks escape the decoder through a private exception that is
not a ``ValueError``, so a caller's rejection is never mistaken for, or absorbed by, a syntax error.
``canonical_json`` is the one writer: sorted keys, compact separators, non-ASCII kept, non-finite
numbers refused.
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable, NoReturn, Optional, Tuple

Reject = Callable[[], NoReturn]


class _DuplicateKey(Exception):
    pass


class _NonFinite(Exception):
    pass


def _unique(pairs: Any) -> dict:
    value = dict(pairs)
    if len(value) != len(pairs):
        raise _DuplicateKey()
    return value


def _finite(text: str) -> float:
    number = float(text)
    if not math.isfinite(number):
        raise _NonFinite()
    return number


def _constant(_text: str) -> NoReturn:
    raise _NonFinite()


_STRICT_DECODER = json.JSONDecoder(object_pairs_hook=_unique, parse_float=_finite, parse_constant=_constant)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def clone_json(value: Any) -> Any:
    kind = type(value)
    if kind is dict:
        return {k: clone_json(v) for k, v in value.items()}
    if kind is list:
        return [clone_json(v) for v in value]
    return value


def load_strict_json(
    raw: Any,
    *,
    on_malformed: Reject,
    on_duplicate: Optional[Reject] = None,
    on_nonfinite: Optional[Reject] = None,
    expected: Optional[type] = None,
    on_unexpected: Optional[Reject] = None,
    limit: Optional[Tuple[int, Reject]] = None,
) -> Any:
    """Decode one JSON document from ``str`` or UTF-8 ``bytes``.

    ``on_malformed`` handles non-text input and anything that is not JSON. Duplicate keys,
    non-finite numbers and a top-level value whose type is not exactly ``expected`` use their own
    handlers when given and ``on_malformed`` otherwise. ``limit`` is ``(max_bytes, on_too_large)``,
    measured in UTF-8 bytes before decoding.
    """
    duplicate = on_duplicate or on_malformed
    nonfinite = on_nonfinite or on_malformed
    if type(raw) is not str and type(raw) is not bytes:
        on_malformed()
    if limit is not None:
        max_bytes, on_too_large = limit
        if len(raw if isinstance(raw, bytes) else raw.encode("utf-8", "surrogatepass")) > max_bytes:
            on_too_large()
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if text.startswith("\ufeff"):
            raise ValueError("Unexpected UTF-8 BOM")
        value = _STRICT_DECODER.decode(text)
    except _DuplicateKey:
        rejected = duplicate
    except _NonFinite:
        rejected = nonfinite
    except (ValueError, RecursionError):
        on_malformed()
    else:
        if expected is not None and type(value) is not expected:
            (on_unexpected or on_malformed)()
        return value
    rejected()
